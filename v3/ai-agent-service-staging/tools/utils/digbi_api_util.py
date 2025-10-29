import httpx
import json
import requests
import urllib.parse
from agent_core.config.logging_config import logger
from utils.env_loader import get_digbi_auth_token


async def make_digbi_api_call(method, url, request_data=None, additional_headers=None):
    """
    Generic function to make authenticated API calls to Digbi.

    :param method: HTTP method ("GET", "POST", "PUT").
    :param url: API endpoint URL.
    :param request_data: JSON payload (only for POST/PUT).
    :param additional_headers: Dictionary of additional headers (e.g., user-id).
    :return: JSON response or None if error occurs.
    """
    auth_token = get_digbi_auth_token()

    # Base headers (Authentication & JSON content)
    headers = {
        "state-02": auth_token,
        "Content-Type": "application/json"
    }

    # Merge additional headers if provided
    if additional_headers:
        headers.update(additional_headers)
    logger.info(f"Sending request with data {request_data} {headers}")
    logger.info("Digbi request %s %s", method, url)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, json=request_data, headers=headers)
            elif method == "PUT":
                response = await client.put(url, json=request_data, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            response.raise_for_status()  # Raises an error for bad responses (4xx, 5xx)
            if response.json() is None:
                logger.error(f"No response but status {response.status_code} from {method} {url} ")
            if response.status_code < 400:
                logger.info("Successful %s request to %s, Status Code: %s", method, url, response.status_code)
            else:
                logger.error("Failed %s request to %s, Status Code: %s", method, url, response.status_code)
        resp_payload = response.json()
        if resp_payload is None:
            logger.error(f"No response but status 200 from {method} {url} ")

        if "result" in resp_payload:
            resp_data = resp_payload["result"]
        else:
            logger.warning(f"Using the whole payload, no key named result in response from {method} {url} ")
            resp_data = resp_payload
        return resp_data

    except httpx.HTTPError as req_err:
        logger.error("Failed %s request to %s: %s", method, url, str(req_err), exc_info=True)
        return None


async def get_digbi_data(url):
    """Makes a GET request to the Digbi API."""
    return await make_digbi_api_call("GET", url)


async def post_digbi_data(url, request_data, additional_headers=None):
    """Makes a POST request to the Digbi API."""
    return await make_digbi_api_call("POST", url, request_data, additional_headers)


async def put_digbi_data(url, request_data, additional_headers=None):
    """Makes a PUT request to the Digbi API."""
    return await make_digbi_api_call("PUT", url, request_data,additional_headers)

async def post_html_file(url,html_content: str, filename: str, headers=None) -> str:
    """
    Upload an HTML report file to the backend via multipart/form-data.
    """

    encoded_filename = urllib.parse.quote(filename, safe="")

    # Construct multipart form: file field carries the HTML content
    files = {
        "file": (encoded_filename, html_content, "text/html"),
    }

    # Perform POST request
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, files=files, headers=headers)

            response.raise_for_status()  # Raises an error for bad responses (4xx, 5xx)
            if response.json() is None:
                logger.error(f"No response but status {response.status_code} from {url} ")
            if response.status_code < 400:
                logger.info("Successful request to %s, Status Code: %s", url, response.status_code)
            else:
                logger.error("Failed request to %s, Status Code: %s", url, response.status_code)

        resp_payload = response.json()
        if resp_payload is None:
            logger.error(f"No response but status 200 from {url} ")

        if "result" in resp_payload:
            resp_data = resp_payload["result"]
        else:
            logger.warning(f"Using the whole payload, no key named result in response from {url} ")
            resp_data = resp_payload

        return resp_data

    except httpx.HTTPError as req_err:
        logger.error("Failed request to %s: %s", url, str(req_err), exc_info=True)
        return None