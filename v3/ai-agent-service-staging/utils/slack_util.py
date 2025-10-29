import json
import os


from utils.env_loader import (
    get_slack_token,
    get_ask_digbi_slack_channel,
    get_meal_rating_slack_channel,
    get_ask_digbi_request_response_channel
)
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import threading

import asyncio
from typing import Any, Dict

def is_dev_environment() -> bool:
    return os.getenv("ENV") == "DEVELOPMENT"


def send_slack_message(channel: str, message: str):
    if is_dev_environment():
        return

    client = WebClient(token=get_slack_token())
    try:
        client.chat_postMessage(channel=channel, text=message)
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")
    except Exception as e:  # pragma: no cover - network issues
        # Catch other exceptions (e.g. network errors) to avoid unhandled thread exceptions
        print(f"Error sending message: {e}")


def send_slack_askdigbi_log(message: str):
    thread = threading.Thread(
        target=send_slack_message, args=(get_ask_digbi_slack_channel(), message)
    )
    thread.start()


def send_slack_mealrating_log(message: str):
    """Send logs to the meal rating Slack channel asynchronously."""
    thread = threading.Thread(
        target=send_slack_message, args=(get_meal_rating_slack_channel(), message)
    )
    thread.start()


def send_slack_askdigbi_request_response_log(message: str):
    """Send ask-digbi requests and final responses to a separate Slack channel."""
    channel = get_ask_digbi_request_response_channel()
    send_message_to_channel(channel, message, None, None)


def format_prompt_variables(vars_dict: Dict[str, Any], agent_id) -> str:
    """Return variables and values as a fenced code block."""
    lines = [f"agent: {agent_id}"]
    for key, value in vars_dict.items():
        val = str(value)
        if len(val) > 200:
            val = val[:200] + "..."
        lines.append(f"{key}: {val}")
    return "```\n" + "\n".join(lines) + "```"


def send_prompt_variables_log(
    vars_dict: Dict[str, Any], feature_context: str | None = None, agent_id: str | None = None
) -> None:
    """Send hydrated prompt variables to Slack as a code block.

    The destination channel is determined by the feature context. When the
    context corresponds to meal rating, logs are routed to the meal rating
    channel; otherwise they default to the Ask Digbi channel.

    Args:
        vars_dict: Dictionary containing the prompt variables
        feature_context: Context to determine the Slack channel
        agent_id: Optional agent ID to check against allowed agents
    """
    # Get list of allowed agent IDs from environment variable
    allowed_agents = os.getenv("SLACK_PROMPT_LOGGING_ALLOWED_AGENTS", "").split(",")

    # If agent_id is provided and not in allowed agents, skip sending the message
    if agent_id and agent_id not in allowed_agents:
        return

    message = format_prompt_variables(vars_dict, agent_id)
    if feature_context == "MEAL_RATING":
        send_slack_mealrating_log(message)
    else:
        send_slack_askdigbi_log(message)


def send_message_to_channel(channel, message, attachment_block, image_context_block):
    if is_dev_environment():
        return

    client = WebClient(token=get_slack_token())
    blocks = [{"type": "divider"}]

    if message:
        section_block = {"type": "section", "text": {"type": "mrkdwn", "text": message}}

        blocks.append(section_block)

    if image_context_block:
        blocks.append(image_context_block)

    try:
        client.chat_postMessage(
            channel=channel,
            text=message,
            blocks=blocks,
            attachments=[attachment_block] if attachment_block else None,
        )
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")



def send_meal_rating_message(
    channel: str,
    message: str,
    attachment: str = None,
    attachment_title=None,
    image_url: str = None,
):
    """Send a meal rating message to Slack synchronously."""
    image_accessory_block = get_image_accessory_block(image_url)
    attachment_block = get_attachment_block(attachment, attachment_title)
    # Send the message synchronously to avoid async issues
    send_message_to_channel(channel, message, attachment_block, image_accessory_block)



def get_attachment_block(attachment, title):
    """Create a Slack attachment block."""
    if not attachment:
        return None

    try:
        parsed_json = json.loads(attachment)
        formatted_json = json.dumps(parsed_json, indent=2)
    except json.JSONDecodeError:
        formatted_json = attachment  # fallback to raw string if it's not valid JSON

    return {
        "color": "#2eb886",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*"}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```json\n{formatted_json}\n```"
                },
            },
        ],
    }



def get_image_accessory_block(image_url):
    """Create a Slack image accessory block."""
    if not image_url:
        return None

    return {
        "type": "context",
        "elements": [
            {"type": "image", "image_url": image_url, "alt_text": "Meal Image"},
            {"type": "mrkdwn", "text": f":link: <{image_url}|*Image*>"},
        ],
    }