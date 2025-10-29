from typing import Dict, Any

from agent_core.config.logging_config import logger
from tools import tool
from utils.env_loader import *
from datetime import date, timedelta, datetime

from utils.cache import cached

from tools.utils.digbi_api_util import post_digbi_data, make_digbi_api_call, put_digbi_data, post_html_file
from utils.env_loader import get_barcodes_scanned_url

import asyncio

# TTL for user health snapshot data used by locale tool
USER_HEALTH_SNAPSHOT_CACHE_TTL = 180

USER_FORM_RESPONSES_CACHE_TTL = 1296000
USER_PROFILE_CACHE_TTL = 1296000

def get_meal_ids_url():
    digbi_url = get_env_var("DIGBI_URL")
    resource_path = get_env_var("GET_MEAL_IDS_PATH")

    if not digbi_url or not resource_path:
        raise ValueError(
            "Missing required environment variables for Digbi get meal ids URL"
        )

    return digbi_url + resource_path


def get_meal_score_url():
    digbi_url = get_env_var("DIGBI_URL")
    resource_path = get_env_var("CALCULATE_MEAL_SCORE_API_PATH")

    if not digbi_url or not resource_path:
        raise ValueError(
            "Missing required environment variables for Digbi meal rating calculate score URL"
        )

    return digbi_url + resource_path


def get_meal_scores_url():
    digbi_url = get_env_var("DIGBI_URL")
    resource_path = get_env_var("CALCULATE_MEAL_SCORES_API_PATH")

    if not digbi_url or not resource_path:
        raise ValueError(
            "Missing required environment variables for Digbi meal rating calculate scores URL"
        )

    return digbi_url + resource_path


def get_journey_events_url():
    digbi_url = get_env_var("DIGBI_URL")
    resource_path = get_env_var("JOURNEY_EVENTS_PATH")

    if not digbi_url or not resource_path:
        raise ValueError(
            "Missing required environment variables for Digbi journey events URL"
        )

    return digbi_url + resource_path

async def get_meal_ids_last_7_days(user_token):
    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    # The API excludes the end date; pass end_date + 1 to include today
    inclusive_end = end_date + timedelta(days=1)
    return await get_meal_ids(user_token, start_date, inclusive_end, 30)


async def get_meal_ids(user_token, start_date: date, end_date: date, max_meals):
    api_endpoint = get_meal_ids_url()

    logger.info(
        f"Fetching user meal ids between {start_date} and {end_date} for: {user_token}"
    )
    additional_headers = {"user-id": user_token}

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query_string = f"?startDate={start_str}&endDate={end_str}&maxMeals={max_meals}"

    response = await make_digbi_api_call(
        "GET", api_endpoint + query_string, additional_headers=additional_headers
    )
    if response:
        logger.info(f"Successfully sent get meal ids request with response {response}")
    else:
        logger.error(f"Failed to send get meal ids request with response {response}")

    return response


async def get_barcodes_scanned_last_7_days(user_token):
    """Fetch barcode scan IDs for the last 7 days (up to 100 by default)."""
    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    return await get_barcodes_scanned(user_token, start_date, end_date, 100)


async def get_barcodes_scanned(user_token, start_date: date, end_date: date, max_results: int = 100):
    """Fetch barcode scan IDs between start_date and end_date for a user.

    Parameters
    ----------
    user_token : str
        Encrypted user id to be passed in header 'user-id'.
    start_date : date
        Start date inclusive.
    end_date : date
        End date inclusive. (The API treats endDate as exclusive; we add 1 day.)
    max_results : int
        Maximum number of results to request from Digbi API.
    """
    api_endpoint = get_barcodes_scanned_url()

    logger.info(
        f"Fetching barcodes scanned IDs between {start_date} and {end_date} for: {user_token}"
    )
    additional_headers = {"user-id": user_token}

    start_str = start_date.strftime("%Y-%m-%d")
    # The API excludes the end date; add 1 day to make it inclusive
    api_end_date = end_date + timedelta(days=1)
    end_str = api_end_date.strftime("%Y-%m-%d")

    query_string = f"?startDate={start_str}&endDate={end_str}&maxResults={max_results}"

    response = await make_digbi_api_call(
        "GET", api_endpoint + query_string, additional_headers=additional_headers
    )
    if response:
        logger.info(
            f"Successfully fetched {len(response) if isinstance(response, list) else 'N/A'} barcodes scanned IDs"
        )
    else:
        logger.error("Failed to fetch barcodes scanned IDs: response was None")

    return response


async def calculate_meal_score(request, user_token):
    api_endpoint = get_meal_score_url()
    logger.info(
        "Sending meal scoring request to %s with payload %s", api_endpoint, request
    )
    response = await post_digbi_data(api_endpoint, request, {"user-id": user_token})
    if response:
        logger.info(f"Successfully sent meals scoring request with response {response}")
    else:
        logger.error(f"Failed to send meals scoring request with response {response}")

    return response


async def calculate_meal_scores(request, user_token) -> Dict[str, Any]:
    api_endpoint = get_meal_scores_url()
    logger.info(
        "Sending meal scoring request to %s with payload %s", api_endpoint, request
    )
    response = await post_digbi_data(api_endpoint, request, {"user-id": user_token})
    if response:
        logger.info(f"Successfully sent meals scoring request with response {response}")
    else:
        logger.error(f"Failed to send meals scoring request with response {response}")

    return response


async def send_meal_rating_response(response_data, user_token):
    """
    Sends the processed ask-digbi response to the Digbi API.
    """

    # Handle any coroutines in the response data
    if hasattr(response_data, "__await__"):
        response_data = await response_data

    # Check if any values in the response data are coroutines
    if isinstance(response_data, dict):
        for key, value in list(response_data.items()):
            if hasattr(value, "__await__"):
                response_data[key] = await value

    callback_url = get_meal_rating_callback_url()
    logger.info("Sending meal rating response to %s", callback_url)

    success = await post_digbi_data(
        callback_url, response_data, {"user-id": user_token}
    )

    if success:
        logger.info("Successfully sent meal rating response")
    else:
        logger.error("Failed to send meal rating response")

    return success


async def send_ask_digbi_response(response_data):
    """
    Sends the processed ask-digbi response to the Digbi API.
    """
    callback_url = get_ask_digbi_callback_url()
    logger.info("Sending ask-digbi response to %s", callback_url)

    success = await post_digbi_data(callback_url, response_data)

    if success:
        logger.info("Successfully sent ask-digbi response")
    else:
        logger.error("Failed to send ask-digbi response")

    return success


async def get_user_genetic_report(user_token):
    """
    Gets the user genetic report if available
    """
    url = get_genetic_report_url()
    logger.info(
        f"Fetching user genetic report for user token: {user_token} using url: {url}"
    )
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


async def get_user_gut_report(user_token):
    """
    Gets the user gut report if available
    """
    url = get_gut_report_url()
    logger.info(
        f"Fetching user gut report for user token: {user_token} using url: {url}"
    )
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


async def get_user_digestive_report(user_token):
    """
    Gets the user digestive report if available
    """
    url = get_digestive_report_url()
    logger.info(
        f"Fetching user digestive report for user token: {user_token} using url: {url}"
    )
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


async def get_nd_score_infractions():
    url = get_nd_score_infractions_url()
    return await make_digbi_api_call("GET", url)


@tool
async def get_user_locale(user_token):
    """Return the preferred locale for the given user."""
    data = await get_user_health_snapshot(user_token)
    return data.get("preferred_locale")


@cached(ttl=USER_HEALTH_SNAPSHOT_CACHE_TTL)
async def get_user_health_snapshot(user_token):
    """Gets the user health snapshot data"""
    url = get_user_health_snapshot_url()
    logger.info(f"Fetching user Health profile snapshot: {user_token} using url: {url}")
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


@cached(ttl=USER_HEALTH_SNAPSHOT_CACHE_TTL)
async def get_user_health_metrics(user_token):
    """Gets the user health metrics api data"""
    url = get_user_health_metrics_url()
    logger.info(f"Fetching user health metrics data: {user_token} using url: {url}")
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


@cached(ttl=USER_FORM_RESPONSES_CACHE_TTL)
async def get_user_form_responses(user_token):
    """Gets the user form response data"""
    url = get_user_form_responses_url()
    logger.info(f"Fetching user form responses data: {user_token} using url: {url}")
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)

@cached(ttl=USER_PROFILE_CACHE_TTL)
async def get_user_profile(user_token):
    """Gets the user profile data"""
    url = get_user_profile_url()
    logger.info(f"Fetching user profile data: {user_token} using url: {url}")
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)

@cached(ttl=USER_HEALTH_SNAPSHOT_CACHE_TTL)
async def get_user_vo2max(user_token):
    """Gets the user vo2Max data"""
    url = get_user_vo2max_url()
    logger.info(f"Fetching user vo2max data: {user_token} using url: {url}")
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


async def get_user_cgm_stats(
    user_token: str,
    start_date: date | datetime | str | None = None,
    end_date: date | datetime | str | None = None,
):
    """Gets the user CGM TIR for a given date range (YYYY/MM/DD).

    Parameters
    ----------
    user_token : str
        Encrypted user id to be passed in header 'user-id'.
    start_date, end_date : date | datetime | str | None
        Optional date values to filter the CGM stats. Strings are expected in
        either ``YYYY-MM-DD`` or ``YYYY/MM/DD`` format and are normalized to
        ``YYYY/MM/DD``.
    """
    url = get_cgm_stats_url()

    query_parts = []
    if start_date:
        query_parts.append(f"date={_format_date(start_date)}")
    if end_date:
        query_parts.append(f"endDate={_format_date(end_date)}")
    query_string = f"?{'&'.join(query_parts)}" if query_parts else ""

    return await make_digbi_api_call(
        "GET", url + query_string, additional_headers={"user-id": user_token}
    )


@tool
async def get_cgm_tir_by_date(user_token: str, date: str | None = None):
    """Gets the user CGM TIR for a given date (YYYY-MM-DD)."""
    url = get_cgm_tir_url()
    query_string = f"?date={date}" if date else ""
    return await make_digbi_api_call(
        "GET", url + query_string, additional_headers={"user-id": user_token}
    )

async def get_nd_score_details(user_token, image_id):
    """
    Gets the nd score details
    """
    url = get_nd_score_details_url(image_id)
    logger.info(f"Fetching nd score details for user: {user_token} endpoint: {url}")
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


async def get_user_genetic_traits(user_token, risks=None):
    """Fetches the user's genetic traits.

    Parameters
    ----------
    user_token : str
        Digbi user token used for authentication.
    risks : list[str] | None
        Optional list of risk categories to request. Defaults to ["HIGH_RISK"].
    """

    if risks is None:
        risks = ["HIGH_RISK"]

    url = get_user_genetic_traits_url()

    if risks:
        query = "&".join([f"risks={risk}" for risk in risks])
        url = f"{url}?{query}"

    logger.info(
        "Fetching user genetic traits for user token: %s using url: %s", user_token, url
    )

    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


async def get_user_meal_history(user_token, time_range_in_days=7, max_count=10):
    """
    Gets the user gut report if available
    """
    url = get_user_meal_history_url()
    logger.info(f"Fetching user Health profile snapshot: {user_token} using url: {url}")
    additional_headers = {"user-id": user_token}

    end_date = date.today()
    start_date = end_date - timedelta(days=time_range_in_days)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query_string = f"?startDate={start_str}&endDate={end_str}&maxMeals={max_count}"

    return await make_digbi_api_call(
        "GET", url + query_string, additional_headers=additional_headers
    )

async def get_user_meal_history_chunked(
        user_token, start_date: date, end_date: date):
    """
    Fetches the user meal history by splitting the range into day-long windows.
    Runs all daily requests concurrently for speed.
    """
    tasks = []
    current_date = start_date

    while current_date <= end_date:
        day_end = current_date + timedelta(days=1)

        tasks.append(
            get_user_meal_history_in_date_range(
                user_token=user_token,
                start_date=current_date,
                end_date=day_end,
                max_meals=50,
            )
        )

        current_date += timedelta(days=1)

    results = await asyncio.gather(*tasks)

    # flatten results, skipping None
    all_meals = []
    for meals in results:
        if meals:
            all_meals.extend(meals)

    return all_meals


# New function that takes explicit date range
async def get_user_meal_history_in_date_range(
    user_token, start_date: date, end_date: date, max_meals
):
    """
    Gets the user meal history between provided start and end dates.
    """
    url = get_user_meal_history_url()
    logger.info(
        f"Fetching user meal history between {start_date} and {end_date} for: {user_token}"
    )
    additional_headers = {"user-id": user_token}

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query_string = f"?startDate={start_str}&endDate={end_str}&maxMeals={max_meals}"

    return await make_digbi_api_call(
        "GET", url + query_string, additional_headers=additional_headers
    )


async def get_user_weight_logs(user_token):
    """
    Gets the user weight logs if available
    """
    url = get_user_weight_logs_url()
    logger.info(f"Fetching user weight logs: {user_token} using url: {url}")
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


async def get_user_ibs_logs(user_token):
    """
    Gets the user ibs logs if available
    """
    url = get_user_ibs_logs_url()
    logger.info(f"Fetching user IBS logs: {user_token} using url: {url}")
    additional_headers = {"user-id": user_token}

    return await make_digbi_api_call("GET", url, additional_headers=additional_headers)


async def get_user_nd_score_stats(
    user_token, start_date: date = None, end_date: date = None
):
    """
    Gets the user ND score stats between provided start and end dates.
    """
    url = get_user_nd_score_stats_url()

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    logger.info(
        f"Fetching user ND Score Stats history between {start_date} and {end_date} for: {user_token}"
    )
    additional_headers = {"user-id": user_token}

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query_string = f"?startDate={start_str}&endDate={end_str}"

    return await make_digbi_api_call(
        "GET", url + query_string, additional_headers=additional_headers
    )


async def get_user_journey_events(user_token: str):
    """Fetch journey events for a user."""
    url = get_journey_events_url()
    logger.info(
        "Fetching journey events for user token: %s using url: %s",
        user_token,
        url,
    )
    additional_headers = {"user-id": user_token}
    return await make_digbi_api_call(
        "GET", url, additional_headers=additional_headers
    )

async def update_user_report_context(user_token: str, report_id: str, json_body: str):
    """
    Updates report context for a given report_id.

    Args:
        user_token (str): The user ID header value.
        report_id (str): The report identifier to update.
        body (str): JSON string payload for the request.
    """
    base_url = get_user_summary_report_context_url()
    url = f"{base_url}?reportId={report_id}"

    return await put_digbi_data(
        url,
        json_body,
        additional_headers={
            "user-id": user_token,
            "accept": "*/*",
            "Content-Type": "application/json",
        },
    )

@tool
async def fetch_cgm_report_context(user_token: str):
    """
    Fetches user report context with the given report_id.

    Args:
        user_token (str): The user ID header value.
        report_id (str): The report identifier to fetch.
    """
    base_url = get_user_summary_report_context_url()
    report_id=get_env_var("CGM_SUMMARY_REPORT_ID")
    url = f"{base_url}?reportId={report_id}"

    return await make_digbi_api_call(
        "GET",
        url,
        additional_headers={
            "user-id": user_token,
            "accept": "*/*",
        },
    )

async def upload_summary_report(
        user_token: str,
        report_code: str,
        filename: str,
        html_content: str
):
    base_url = get_upload_summary_file_url()
    report_type = "AI_Summary"
    url = f"{base_url}?token={get_env_var('SUMMARY_REPORT_FILE_UPLOAD_TOKEN')}&title={report_code}&reportType={report_type}"

    return await post_html_file(
        url,
        html_content,
        filename,
        headers={
            "user-id": user_token,
            "accept": "*/*",
        },
    )

def _format_date(value: date | datetime | str) -> str:
    """Normalize supported date inputs to ``YYYY/MM/DD`` format."""
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y/%m/%d")

    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y/%m/%d")
    except Exception:
        # If already in YYYY/MM/DD or invalid, just return as-is
        return value
