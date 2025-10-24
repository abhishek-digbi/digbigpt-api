import json
import os
from typing import Any, Dict, Optional

import httpx
from httpx import Response

from agent_core.config.logging_config import logger

BASE_URL = "https://api.typeform.com"
TYPEFORM_TOKEN = os.getenv("TYPEFORM_TOKEN", "YOUR_TYPEFORM_TOKEN_HERE")
HEADERS = {
    "Authorization": f"Bearer {TYPEFORM_TOKEN}",
    "Content-Type": "application/json"
}


async def call_typeform(endpoint: str, data: Dict[str, Any], method: str = "POST") -> Response:
    """Make an async request to the Typeform API."""
    url = BASE_URL + endpoint
    pretty_payload = json.dumps(data, indent=2, default=str)
    logger.info("Typeform API Request - %s:\n%s", endpoint, pretty_payload)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                url,
                headers=HEADERS,
                json=data
            )

        # Log the response status
        logger.info("Typeform API Response - %s: %d", endpoint, response.status_code)

        response.raise_for_status()

        # Log the complete response with pretty-printed JSON
        response_data = response.json()
        pretty_response = json.dumps(response_data, indent=2, default=str)
        logger.info("Typeform API Response Data - %s:\n%s",
                    endpoint,
                    pretty_response)

        return response

    except httpx.HTTPStatusError as e:
        body = e.response.text
        logger.error(
            "Typeform API HTTP Error - %s: %d - %s",
            endpoint,
            e.response.status_code,
            body,
        )
        raise httpx.HTTPStatusError(
            f"HTTP {e.response.status_code}: {body}",
            request=e.request,
            response=e.response,
        ) from e
    except Exception as e:
        logger.error("Typeform API Error - %s: %s", endpoint, str(e))
        raise


async def create_typeform_quiz(payload):
    return await call_typeform("/forms", payload)


async def register_typeform_webhook(
    form_id: str,
    webhook_url: str,
    tag: str = "submission"
):
    payload = {"url": webhook_url, "enabled": True}
    endpoint = f"/forms/{form_id}/webhooks/{tag}"
    return await call_typeform(endpoint, payload, method="PUT")
