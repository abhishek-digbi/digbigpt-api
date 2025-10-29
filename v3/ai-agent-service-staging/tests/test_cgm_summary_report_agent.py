import html
import json
import re
import textwrap
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent_core.services.model_context import BaseModelContext
from orchestrator.orchestrators.cgm_summary_report_agent import CGMSummaryReportAgent
from tools import ToolService
from tools.registry import Tool
from tools.definitions import cgm_service as cgm_module


@pytest.mark.asyncio
async def test_get_user_cgm_stats_accepts_date_objects(mocker):
    mocker.patch(
        "tools.services.digbi_service.get_cgm_stats_url",
        return_value="https://digbi.example/cgm_stats",
    )
    api_call_mock = mocker.patch(
        "tools.services.digbi_service.make_digbi_api_call",
        new_callable=AsyncMock,
        return_value={},
    )

    from tools.services.digbi_service import get_user_cgm_stats

    await get_user_cgm_stats(
        "user-123",
        start_date=date(2024, 7, 1),
        end_date=date(2024, 7, 7),
    )

    api_call_mock.assert_awaited_once_with(
        "GET",
        "https://digbi.example/cgm_stats?date=2024/07/01&endDate=2024/07/07",
        additional_headers={"user-id": "user-123"},
    )


VALID_AGENT_HTML = textwrap.dedent(
    """
    <section class="report-card" id="overview">
      <div class="card-title">A Personalized Look at Your Glucose Patterns</div>
    </section>
    <section class="report-card" id="summary">
      <div class="card-title">Glucose Summary</div>
    </section>
    <section class="report-card" id="tir">
      <div class="card-title">Blood Sugar in Range</div>
    </section>
    <section class="report-card" id="daily">
      <div class="card-title">Daily Glucose Patterns</div>
    </section>
    <section class="report-card" id="meals">
      <div class="card-title">Meal Time Consistency</div>
    </section>
    <section class="report-card" id="response">
      <div class="card-title">Response Patterns</div>
    </section>
    <section class="report-card" id="champion">
      <div class="card-title">Champion Day & Challenge Day</div>
    </section>
    <section class="report-card" id="learn-from">
      <div class="card-title">Meals You Can Learn From</div>
    </section>
    <section class="report-card" id="takeaways">
      <div class="card-title">Smart Takeaways</div>
    </section>
    <section class="report-card" id="next-steps">
      <div class="card-title">Next Steps</div>
    </section>
    """
).strip()


@pytest.mark.asyncio
async def test_cgm_summary_agent_renders_template_and_calls_digbi(mocker, monkeypatch):
    ai_core = AsyncMock()
    ai_core.run_agent.return_value = VALID_AGENT_HTML

    mocker.patch(
        "orchestrator.orchestrators.cgm_summary_report_agent.get_agent_cfg",
        return_value=SimpleNamespace(tools=["cgm_glucose_summary", "cgm_meals_summary"]),
    )

    expected_grp = {
        "time_in_range_percent": 68.2,
        "time_in_low_percent": 12.0,
        "time_very_low_percent": 0.0,
        "time_in_high_percent": 15.7,
        "time_in_very_high_percent": 0.0,
    }
    expected_tbp = [
        {"time_block": "Midnight", "mean_glucose": 0.0},
        {"time_block": "Morning", "mean_glucose": 104.3},
        {"time_block": "Afternoon", "mean_glucose": 117.0},
        {"time_block": "Evening", "mean_glucose": 0.0},
    ]

    async def glucose_tool(user_token: str, start_date, end_date):
        return json.dumps(
            {
                "glucose_range_percentages": expected_grp,
                "time_block_patterns": expected_tbp,
                "glucose_summary_metrics": {"min_glucose": 80.0},
            }
        )

    async def meals_tool(user_token: str, start_date, end_date, **_kwargs):
        return json.dumps({"champion_day": {"date": "2024-06-03"}})

    data_core = mocker.Mock()
    data_core.get_tool.side_effect = lambda name: {
        "cgm_glucose_summary": Tool("cgm_glucose_summary", "", glucose_tool),
        "cgm_meals_summary": Tool("cgm_meals_summary", "", meals_tool),
    }.get(name)
    ai_core.data_core = data_core

    # Ensure template is loaded from repository path
    repo_root = Path(__file__).resolve().parents[1]
    template_path = (
        repo_root / "orchestrator" / "templates" / "cgm_summary_report_template.html"
    )
    assert template_path.exists(), "Template file should exist"

    upload_mock = mocker.patch(
        "orchestrator.orchestrators.cgm_summary_report_agent.upload_summary_report",
        new_callable=AsyncMock,
        return_value={"status": "uploaded"},
    )
    update_mock = mocker.patch(
        "orchestrator.orchestrators.cgm_summary_report_agent.update_user_report_context",
        new_callable=AsyncMock,
        return_value={"status": "updated"},
    )

    ctx = BaseModelContext(
        context_id="ctx-1",
        query_id="query-1",
        query="Generate report",
        user_token="user-123",
        data={
            "report_id": "report-456",
            "report_code": "CGM_WEEKLY",
            "report_filename": "weekly_cgm.html",
            "start_date": "2024-06-01",
            "end_date": "2024-06-07",
            "template_variables": {
                "report_title": "Weekly CGM Summary",
                "report_subtitle": "A detailed look at your glucose trends",
                "report_period": "June 1 - June 7",
                "report_generated_on": "Generated on Jun 8",
            },
        },
    )

    monkeypatch.setenv("CGM_SUMMARY_REPORT_CODE", "CGM_WEEKLY")
    monkeypatch.setenv("CGM_SUMMARY_REPORT_ID", "REPORT-123")

    agent = CGMSummaryReportAgent(ai_core)
    result = await agent.ask(ctx)

    ai_core.run_agent.assert_awaited_once_with(
        "CGM_SUMMARY_REPORT_AGENT", ctx, output_type=str
    )
    upload_mock.assert_awaited_once()
    update_mock.assert_awaited_once()

    rendered_html = result["report_html"]

    assert re.search(r"<title>\s*Your Glucose &amp; Meal Story\s*</title>", rendered_html)
    titles = [
        html.unescape(title.strip())
        for title in re.findall(
            r'<div class="card-title">(.*?)</div>', rendered_html, flags=re.DOTALL
        )
    ]
    assert titles == [
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
    ]

    assert (
        f"const glucoseRangePercentages = {json.dumps(expected_grp, ensure_ascii=False)};"
        in rendered_html
    )
    assert (
        f"const timeBlockPatterns = {json.dumps(expected_tbp, ensure_ascii=False)};"
        in rendered_html
    )

    assert ctx.data["glucose_range_percentages"] == expected_grp
    assert ctx.data["time_block_patterns"] == expected_tbp
    assert ctx.data["glucose_summary_metrics"] == {"min_glucose": 80.0}

    assert result["upload_result"] == {"status": "uploaded"}
    assert result["context_update_result"] == {"status": "updated"}

    # Context passed to update should include template payload data
    _, _, payload_dict = update_mock.await_args[0]
    assert payload_dict["template_variables"]["report_title"] == "Weekly CGM Summary"
    assert payload_dict["glucose_range_percentages"] == expected_grp
    assert payload_dict["time_block_patterns"] == expected_tbp
    assert payload_dict["report_code"] == "CGM_WEEKLY"


@pytest.mark.asyncio
async def test_hydrate_ctx_with_registered_cgm_tools_populates_context(mocker):
    mocker.patch(
        "orchestrator.orchestrators.cgm_summary_report_agent.get_agent_cfg",
        return_value=SimpleNamespace(tools=["cgm_glucose_summary", "cgm_meals_summary"]),
    )

    tool_service = ToolService(db_client=SimpleNamespace())

    async def fake_glucose_tool(
        user_token: str,
        start_date,
        end_date,
    ) -> str:
        assert user_token == "user-456"
        assert start_date.isoformat() == "2024-06-01"
        assert end_date.isoformat() == "2024-06-07"
        return json.dumps(
            {
                "cgm_start_date": "2024-06-01",
                "cgm_end_date": "2024-06-07",
                "glucose_total_readings": 42,
                "glucose_range_percentages": {"time_in_range_percent": 80.0},
                "time_block_patterns": [
                    {"time_block": "Morning", "mean_glucose": 100.0},
                ],
                "glucose_summary_metrics": {"min_glucose": 70.0},
            }
        )

    async def fake_meals_tool(
        user_token: str,
        start_date,
        end_date,
        **_: dict,
    ) -> str:
        assert user_token == "user-456"
        assert start_date.isoformat() == "2024-06-01"
        assert end_date.isoformat() == "2024-06-07"
        return json.dumps(
            {
                "champion_day": {"date": "2024-06-01", "meals": []},
                "challenge_day": {"date": "2024-06-02", "meals": []},
                "meal_type_summary": {"breakfast": {"average_glucose": 95.0}},
                "best_performing_meals": ["Spinach omelette"],
                "least_helpful_meals": ["Sugary cereal"],
                "meal_glucose_response_patterns": [
                    {"pattern": "High", "meals": ["Sugary cereal"]}
                ],
            }
        )

    tool_service.tool_map["cgm_glucose_summary"] = Tool(
        name="cgm_glucose_summary",
        description="",
        func=fake_glucose_tool,
    )
    tool_service.tool_map["cgm_meals_summary"] = Tool(
        name="cgm_meals_summary",
        description="",
        func=fake_meals_tool,
    )

    ai_core = SimpleNamespace(data_core=tool_service)
    agent = CGMSummaryReportAgent(ai_core)

    ctx = BaseModelContext(
        context_id="ctx-registered",
        query_id="query-registered",
        query="Generate report",
        user_token="user-456",
        data={
            "start_date": "2024-06-01",
            "end_date": "2024-06-07",
            "cgm_start_date": "2000-01-01",
            "cgm_end_date": "2000-01-02",
            "glucose_total_readings": -1,
            "champion_day": "sentinel",
            "challenge_day": "sentinel",
            "meal_type_summary": "sentinel",
            "best_performing_meals": "sentinel",
            "least_helpful_meals": "sentinel",
            "meal_glucose_response_patterns": "sentinel",
        },
    )

    await agent._hydrate_ctx_with_tool_data(ctx)

    assert ctx.data["glucose_range_percentages"] == {"time_in_range_percent": 80.0}
    assert ctx.data["time_block_patterns"] == [
        {"time_block": "Morning", "mean_glucose": 100.0}
    ]
    assert ctx.data["glucose_summary_metrics"] == {"min_glucose": 70.0}
    assert ctx.data["cgm_start_date"] == "2024-06-01"
    assert ctx.data["cgm_end_date"] == "2024-06-07"
    assert ctx.data["glucose_total_readings"] == 42
    assert ctx.data["champion_day"] == {"date": "2024-06-01", "meals": []}
    assert ctx.data["challenge_day"] == {"date": "2024-06-02", "meals": []}
    assert ctx.data["meal_type_summary"] == {
        "breakfast": {"average_glucose": 95.0}
    }
    assert ctx.data["best_performing_meals"] == ["Spinach omelette"]
    assert ctx.data["least_helpful_meals"] == ["Sugary cereal"]
    assert ctx.data["meal_glucose_response_patterns"] == [
        {"pattern": "High", "meals": ["Sugary cereal"]}
    ]
    assert set(ctx.data.keys()) >= {
        "glucose_range_percentages",
        "time_block_patterns",
        "glucose_summary_metrics",
        "champion_day",
        "challenge_day",
        "meal_type_summary",
        "best_performing_meals",
        "least_helpful_meals",
        "meal_glucose_response_patterns",
    }


@pytest.mark.asyncio
async def test_cgm_glucose_summary_serializes_dates_and_metrics(monkeypatch):
    import importlib

    cgm_definitions_module = importlib.reload(cgm_module)

    readings = [
        {"reading": 50, "date": "2024-01-01T00:00:00Z"},
        {"reading": 65, "date": "2024-01-01T08:00:00Z"},
        {"reading": 100, "date": "2024-01-01T13:00:00Z"},
        {"reading": 190, "date": "2024-01-01T19:00:00Z"},
        {"reading": 260, "date": "2024-01-01T22:00:00Z"},
    ]

    monkeypatch.setattr(
        cgm_definitions_module,
        "get_user_cgm_stats",
        AsyncMock(return_value={"result": {"readings": readings}}),
    )

    result_json = await cgm_definitions_module.cgm_glucose_summary.func(
        user_token="user-token",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 7),
    )

    result = json.loads(result_json)

    assert result["cgm_start_date"] == "2024-01-01"
    assert result["cgm_end_date"] == "2024-01-07"
    assert result["glucose_total_readings"] == len(readings)

    summary_metrics = result["glucose_summary_metrics"]
    assert summary_metrics["min_glucose"] == 50.0
    assert summary_metrics["max_glucose"] == 260.0
    assert summary_metrics["gmi"] == 6.49
    assert summary_metrics["coefficient_variation"] == 60.1

    expected_range_percentages = {
        "time_in_range_percent": 20.0,
        "time_in_low_percent": 20.0,
        "time_very_low_percent": 20.0,
        "time_in_high_percent": 20.0,
        "time_in_very_high_percent": 20.0,
    }
    assert result["glucose_range_percentages"] == expected_range_percentages

    patterns_by_block = {
        block["time_block"]: block for block in result["time_block_patterns"]
    }
    assert set(patterns_by_block) == {"Midnight", "Morning", "Afternoon", "Evening"}
    assert patterns_by_block["Midnight"]["mean_glucose"] == 50.0
    assert patterns_by_block["Morning"]["mean_glucose"] == 65.0
    assert patterns_by_block["Afternoon"]["mean_glucose"] == 100.0
    assert patterns_by_block["Evening"]["mean_glucose"] == 225.0
    assert patterns_by_block["Evening"]["percent_high"] == 50.0
    assert patterns_by_block["Evening"]["percent_very_high"] == 50.0


@pytest.mark.asyncio
async def test_cgm_glucose_summary_handles_unmatched_ranges(monkeypatch):
    import importlib

    cgm_definitions_module = importlib.reload(cgm_module)

    readings = [
        {"reading": 110, "date": "2024-02-01T09:00:00Z"},
        {"reading": None, "date": "2024-02-01T12:30:00Z"},
    ]

    monkeypatch.setattr(
        cgm_definitions_module,
        "get_user_cgm_stats",
        AsyncMock(return_value={"result": {"readings": readings}}),
    )

    original_dropna = cgm_definitions_module.pd.DataFrame.dropna

    def dropna_preserve_invalid(
        self, axis=0, how="any", thresh=None, subset=None, inplace=False
    ):
        if subset == ["blood_glucose_level", "timestamp"]:
            if inplace:
                return None
            return self
        return original_dropna(
            self, axis=axis, how=how, thresh=thresh, subset=subset, inplace=inplace
        )

    monkeypatch.setattr(
        cgm_definitions_module.pd.DataFrame, "dropna", dropna_preserve_invalid
    )

    result_json = await cgm_definitions_module.cgm_glucose_summary.func(
        user_token="user-token",
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 7),
    )

    result = json.loads(result_json)

    assert result["glucose_total_readings"] == 2
    assert result["glucose_range_percentages"]["time_in_range_percent"] == 100.0
    assert result["glucose_range_percentages"]["time_in_low_percent"] == 0.0
    assert result["glucose_range_percentages"]["time_in_high_percent"] == 0.0


@pytest.mark.asyncio
async def test_cgm_summary_agent_surfaces_errors(mocker, monkeypatch):
    ai_core = AsyncMock()
    ai_core.run_agent.return_value = VALID_AGENT_HTML
    ai_core.data_core = None

    monkeypatch.setenv("CGM_SUMMARY_REPORT_CODE", "CGM_WEEKLY")
    monkeypatch.setenv("CGM_SUMMARY_REPORT_ID", "REPORT-123")

    upload_mock = mocker.patch(
        "orchestrator.orchestrators.cgm_summary_report_agent.upload_summary_report",
        new_callable=AsyncMock,
        side_effect=RuntimeError("upload failed"),
    )
    update_mock = mocker.patch(
        "orchestrator.orchestrators.cgm_summary_report_agent.update_user_report_context",
        new_callable=AsyncMock,
        side_effect=RuntimeError("update failed"),
    )

    ctx = BaseModelContext(
        context_id="ctx-2",
        query_id="query-2",
        query="Generate report",
        user_token="user-789",
        data={
            "report_id": "report-789",
            "report_code": "CGM_DAILY",
        },
    )

    agent = CGMSummaryReportAgent(ai_core)
    result = await agent.ask(ctx)

    ai_core.run_agent.assert_awaited_once()
    upload_mock.assert_awaited_once()
    update_mock.assert_awaited_once()

    assert result["upload_result"] == {"error": "upload failed"}
    assert result["context_update_result"] == {"error": "update failed"}
