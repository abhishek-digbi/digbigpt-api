from __future__ import annotations

import inspect
import json
import re
from utils.env_loader import *
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_core.config.logging_config import logger
from agent_core.config.loader import get_agent_cfg
from agent_core.services.model_context import ModelContext
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from tools.services.digbi_service import (
    update_user_report_context,
    upload_summary_report
)
from tools import Tool, get_registered_tool, with_user_token

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from agent_core.services.ai_core_service import AiCoreService


class CGMSummaryReportAgent(AskDigbiBaseAgent):
    """Runs the CGM summary report workflow."""

    _template_path = Path(__file__).resolve().parent.parent / "templates" / "cgm_summary_report_template.html"

    def __init__(self, ai_core: "AiCoreService") -> None:
        self.ai = ai_core

    async def ask(self, ctx: ModelContext) -> dict[str, Any]:  # type: ignore[override]
        """Generate a CGM report, upload it, and persist the context."""

        logger.info("Generating CGM summary report for user=%s qid=%s", ctx.user_token, ctx.query_id)

        await self._hydrate_ctx_with_tool_data(ctx)

        # Abort early if hydration resulted in missing/empty data
        optional_fields = {
            "champion_day",
            "challenge_day",
            "best_performing_meals",
            "least_helpful_meals",
        }

        if not ctx.data:
            raise ValueError(
                f"Missing ctx.data for user={ctx.user_token}, context_id={ctx.context_id}. "
                "Regenerate the report after data check."
            )

        # Only validate required fields (everything except optional)
        invalid_fields = [
            k for k, v in ctx.data.items()
            if k not in optional_fields and v in (None, "", [], {}, ())
        ]

        if invalid_fields:
            raise ValueError(
                f"Incomplete required tool data for user={ctx.user_token}, context_id={ctx.context_id}. "
                f"Missing or empty values in fields: {invalid_fields}. "
                "Regenerate the report after data check."
            )

        retries = 2
        last_error = None
        rendered_html = None

        for attempt in range(1 + retries):  # initial + retries
            try:
                # regenerate agent_html each time
                agent_html = await self.ai.run_agent(
                    "CGM_SUMMARY_REPORT_AGENT",
                    ctx,
                    output_type=str,
                )

                template_source = self._template_path.read_text(encoding="utf-8")
                preloaded_template = self._prepare_template_context(template_source, ctx)

                rendered_html = self._render_template(agent_html, preloaded_template)
                break  #success, stop retry loop

            except ValueError as e:
                # Only retry if the error is due to missing .card-title
                if "Missing .card-title section" in str(e) and attempt < retries:
                    logger.warning("Report render failed, retrying (%s/%s)...", attempt + 1, retries)
                    last_error = e
                    continue
                raise  # bubble up if out of retries or unrelated error

        if rendered_html is None:
            raise last_error or RuntimeError("Report rendering failed unexpectedly")

        upload_result, upload_error = await self._attempt_upload(ctx, rendered_html)
        context_update_result, context_error = await self._attempt_context_update(ctx)

        response: dict[str, Any] = {
            "query_id":ctx.query_id,
            "user_token":ctx.user_token,
            "report_html": rendered_html,
            "upload_result": upload_result if upload_error is None else {"error": upload_error},
            "context_update_result": (
                context_update_result if context_error is None else {"error": context_error}
            ),
        }

        logger.info(
            "CGM summary report generation finished for user=%s qid=%s",
            ctx.user_token,
            ctx.query_id,
        )
        return response

    def _prepare_template_context(
        self,
        template_html: str,
        ctx: ModelContext,
    ) -> str:
        """
        Fill chart placeholders in the template with actual render_data values.
        """

        def normalize_glucose_range_percentages(data: dict) -> dict:
            base = {
                "time_in_range_percent": 0.0,
                "time_in_low_percent": 0.0,
                "time_very_low_percent": 0.0,
                "time_in_high_percent": 0.0,
                "time_in_very_high_percent": 0.0,
            }
            if isinstance(data, dict):
                for k in base.keys():
                    try:
                        base[k] = float(data.get(k, base[k]) or 0.0)
                    except Exception:
                        base[k] = 0.0
            return base

        def normalize_time_block_patterns(rows: list) -> list:
            order = ["Midnight", "Morning", "Afternoon", "Evening"]
            means = {}
            if isinstance(rows, list):
                for r in rows:
                    tb = str(r.get("time_block", ""))
                    try:
                        mg = float(r.get("mean_glucose", 0.0))
                    except Exception:
                        mg = 0.0
                    if tb in order:
                        means[tb] = mg
            return [
                {"time_block": tb, "mean_glucose": float(means.get(tb, 0.0))}
                for tb in order
            ]

        grp = normalize_glucose_range_percentages(ctx.data.get("glucose_range_percentages", {}))
        tbp = normalize_time_block_patterns(ctx.data.get("time_block_patterns", []))
        grp_json = json.dumps(grp, ensure_ascii=False)
        tbp_json = json.dumps(tbp, ensure_ascii=False)

        html_str, grp_subs = re.subn(
            r"const\s+glucoseRangePercentages\s*=\s*\{[\s\S]*?\};",
            f"const glucoseRangePercentages = {grp_json};",
            template_html,
        )
        html_str, tbp_subs = re.subn(
            r"const\s+timeBlockPatterns\s*=\s*\[[\s\S]*?\];",
            f"const timeBlockPatterns = {tbp_json};",
            html_str,
        )

        if grp_subs == 0 or tbp_subs == 0:
            raise ValueError("Failed to inject chart values into template.")

        return html_str

    def _render_template(self, agent_html: str, preloaded_template: str) -> str:
        """
        Inject AI-generated HTML into the <body> section inside the template,
        prettify only the AI-injected HTML, and keep the rest of the template intact.

        Args:
            agent_html (str): Valid HTML string from agent
            preloaded_template (str): The base HTML template

        Returns:
            str: HTML document with prettified AI content injected
        """

        required_titles = {
            "A Personalized Look at Your Glucose Patterns",
            "Glucose Summary",
            "Blood Sugar in Range",
            "Daily Glucose Patterns",
            "Meal Time Consistency",
            "Response Patterns",
            "Champion Day & Challenge Day",
            "Meals You Can Learn From",
            "Smart Takeaways",
            "Next Steps",
        }

        content_soup = BeautifulSoup(agent_html, "html.parser")
        found_titles = {tag.get_text(strip=True) for tag in content_soup.select(".card-title")}
        missing = required_titles - found_titles
        if missing:
            raise ValueError(
                f"Missing .card-title section(s): {', '.join(sorted(missing))}. "
                "Regenerate the report."
            )

        soup = BeautifulSoup(preloaded_template, "html.parser")
        body = soup.body
        if body is None:
            raise ValueError("Template does not contain a <body> element.")

        body.clear()

        ai_pretty_html = BeautifulSoup(agent_html, "html.parser").prettify()
        body.append(BeautifulSoup(ai_pretty_html, "html.parser"))

        return str(soup)

    async def _attempt_upload(self, ctx: ModelContext, rendered_html: str) -> tuple[Any, str | None]:
        report_code = get_env_var("CGM_SUMMARY_REPORT_CODE")
        start_date = ctx.data.get("cgm_start_date") or ctx.data.get("start_date")
        end_date = ctx.data.get("cgm_end_date") or ctx.data.get("end_date")
        filename = f"cgm_summary_report_{ctx.user_token}_{start_date}_{end_date}.html"

        if not ctx.user_token:
            logger.error("CGM summary upload skipped: missing user token")
            return None, "Missing user token"
        if not report_code:
            logger.error("CGM summary upload skipped: missing report code")
            return None, "Missing report_code in context data"

        try:
            result = await upload_summary_report(
                ctx.user_token,
                report_code,
                filename,
                rendered_html,
            )
            return result, None
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to upload CGM summary report: %s", exc)
            return None, str(exc)

    async def _attempt_context_update(
        self,
        ctx: ModelContext) -> tuple[Any, str | None]:

        report_id = get_env_var("CGM_SUMMARY_REPORT_ID")
        if not ctx.user_token:
            logger.error("CGM summary context update skipped: missing user token")
            return None, "Missing user token"
        if not report_id:
            logger.error("CGM summary context update skipped: missing report id")
            return None, "Missing report_id in context data"

        try:
            # filter redundant variables ctx.data before passing it
            filtered_data = {
                k: v for k, v in ctx.data.items()
                if k not in {"start_date", "end_date", "run_data"}
            }

            result = await update_user_report_context(
                ctx.user_token,
                report_id,
                filtered_data,
            )
            return result, None
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to update CGM summary report context: %s", exc)
            return None, str(exc)

    async def _hydrate_ctx_with_tool_data(self, ctx: ModelContext) -> None:
        """Populate context data using configured CGM summary tools."""

        if not ctx.user_token:
            logger.warning("Skipping CGM tool hydration: missing user token")
            return

        start_date, end_date = self._resolve_reporting_window(ctx.data or {})
        if not start_date or not end_date:
            logger.info(
                "Skipping CGM tool hydration: reporting window missing for context_id=%s",
                ctx.context_id,
            )
            return

        tool_service = getattr(self.ai, "data_core", None)
        if not tool_service or not hasattr(tool_service, "get_tool"):
            logger.warning("Tool service unavailable; CGM context hydration skipped")
            return

        configured_tools = self._get_configured_tool_names()
        if not configured_tools:
            return

        payloads: dict[str, Any] = {}
        for tool_name in configured_tools:
            tool = tool_service.get_tool(tool_name)
            if tool is None:
                tool = get_registered_tool(tool_name)
            if not isinstance(tool, Tool):
                logger.debug("CGM hydration tool %s not found", tool_name)
                continue

            bound_tool = with_user_token(tool, ctx.user_token)
            try:
                raw_payload = await self._invoke_tool(bound_tool, start_date, end_date)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("CGM hydration tool %s failed: %s", tool_name, exc)
                continue

            parsed_payload = self._parse_tool_payload(raw_payload)
            payloads[tool_name] = parsed_payload

        if isinstance(payloads, dict):
            for tool_key, tool_payload in payloads.items():
                if isinstance(tool_payload, dict):
                    for key, value in tool_payload.items():
                        ctx.data[key] = value

    @staticmethod
    def _get_configured_tool_names() -> list[str]:
        try:
            cfg = get_agent_cfg("CGM_SUMMARY_REPORT_AGENT")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unable to load CGM agent configuration: %s", exc)
            return []
        return list(cfg.tools or [])

    @staticmethod
    async def _invoke_tool(tool: Tool, start_date: date, end_date: date) -> Any:
        func = tool.func
        signature = inspect.signature(func)
        kwargs: dict[str, Any] = {}
        if "start_date" in signature.parameters:
            kwargs["start_date"] = start_date
        if "end_date" in signature.parameters:
            kwargs["end_date"] = end_date
        if "from_date" in signature.parameters:
            kwargs.setdefault("from_date", start_date)
        if "to_date" in signature.parameters:
            kwargs.setdefault("to_date", end_date)

        result = func(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

    @staticmethod
    def _parse_tool_payload(payload: Any) -> Any:
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return payload
        return payload

    @staticmethod
    def _resolve_reporting_window(data: dict[str, Any]) -> tuple[date | None, date | None]:
        def _parse(value: Any) -> date | None:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value).date()
                except ValueError:
                    try:
                        return date.fromisoformat(value)
                    except ValueError:
                        return None
            return None

        candidate_keys = [
            ("start_date", "end_date"),
            ("report_start_date", "report_end_date"),
            ("from_date", "to_date"),
            ("startDate", "endDate"),
        ]

        for start_key, end_key in candidate_keys:
            start_val = _parse(data.get(start_key))
            end_val = _parse(data.get(end_key))
            if start_val and end_val:
                return start_val, end_val

        return None, None
