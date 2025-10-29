import os
from datetime import date, timedelta


def get_env_flag(var_name: str, default: str = "false") -> bool:
    """Return True if the environment variable is set to a truthy value."""
    return str(os.getenv(var_name, default)).strip().lower() in {"1", "true", "yes"}


def get_env_var(var_name, default=None):
    """Fetches environment variable with optional default value."""
    return os.getenv(var_name, default)


def get_digbi_auth_token():
    return os.getenv('DIGBI_USER_AUTH_TOKEN')


def get_support_assistant_id():
    return os.getenv('SUPPORT_CLASSIFIER_ASSISTANT_ID')


def should_enable_unified_support_agent() -> bool:
    return get_env_flag("ENABLE_UNIFIED_SUPPORT_AGENT", default="false")


def get_health_insights_assistant_id():
    return os.getenv('DIGBI_REPORT_METADATA_ASSISTANT_ID')


def get_meal_rating_assistant_id():
    return os.getenv('MEAL_RATING_ASSISTANT_ID')


def get_ask_digbi_assistant_id():
    return os.getenv('ASK_DIGBI_ASSISTANT_ID')


def get_digbi_guide_assistant_id():
    return os.getenv('DIGBI_GUIDE_ASSISTANT_ID')


def get_user_profile_assistant_id():
    return os.getenv('USER_PROFILE_ASSISTANT_ID')


def get_ask_digbi_callback_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    callback_path = get_env_var("ASK_DIGBI_RESPONSE_PATH")

    if not digbi_url or not callback_path:
        raise ValueError("Missing required environment variables for Digbi callback URL")

    return digbi_url + callback_path


def get_calculate_meal_score_url():
    digbi_url = get_env_var("DIGBI_URL")
    callback_path = get_env_var("MEAL_RATING_RESPONSE_PATH")

    if not digbi_url or not callback_path:
        raise ValueError("Missing required environment variables for Digbi meal rating callback URL")

    return digbi_url + callback_path


def get_meal_rating_callback_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    callback_path = get_env_var("MEAL_RATING_RESPONSE_PATH")

    if not digbi_url or not callback_path:
        raise ValueError("Missing required environment variables for Digbi meal rating callback URL")

    return digbi_url + callback_path


def get_genetic_report_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("GENE_REPORT_URL")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Digbi genetic report URL")

    return digbi_url + url_path + "?showGeneDetailsWithTraits=true"


def get_gut_report_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("GUT_REPORT_URL")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Digbi gut report URL")

    return digbi_url + url_path + "?reportId=1439235900775311410"


def get_digestive_report_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("DIGESTIVE_REPORT_URL")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Digbi digestive report URL")

    return digbi_url + url_path + "?reportId=1029404602988890053"


def get_nd_score_infractions_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("ND_SCORE_INFRACTIONS_PATH")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Digbi nd score infractions URL")

    return digbi_url + url_path


def get_slack_token():
    return get_env_var("SLACK_BOT_TOKEN")


def get_ask_digbi_slack_channel():
    return get_env_var("ASK_DIGBI_SLACK_CHANNEL")


def get_meal_rating_slack_channel():
    return get_env_var("MEAL_RATING_SLACK_CHANNEL")


def get_ask_digbi_request_response_channel():
    return get_env_var("ASK_DIGBI_REQUEST_RESPONSE_CHANNEL", "#audit-ask-digbi-staging")

def get_user_health_snapshot_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_HEALTH_SNAPSHOT_PATH")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Health Snapshot records infractions URL")

    return digbi_url + url_path


def get_user_health_metrics_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_HEALTH_METRICS_PATH")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Health Snapshot records infractions URL")

    return digbi_url + url_path

def get_user_form_responses_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_FORM_RESPONSES_PATH")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Form responses URL")

    return digbi_url + url_path


def get_user_profile_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_PROFILE_PATH")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Form responses URL")

    return digbi_url + url_path

def get_user_vo2max_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_VO2MAX_PATH")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Form responses URL")

    return digbi_url + url_path

def get_cgm_tir_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("CGM_TIR_PATH")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Form responses URL")

    return digbi_url + url_path

def get_cgm_stats_url():
    """Returns the full Digbi callback URL."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("CGM_STATS_PATH")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Form responses URL")

    return digbi_url + url_path


def get_user_meal_history_url():
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_LAST_MEALS")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Last Meal URL")

    return digbi_url + url_path


def get_nd_score_details_url(image_id):
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("ND_SCORE_DETAILS")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for nd score details URL")

    return digbi_url + url_path + "?imageGalleryId=" + image_id


def get_user_genetic_traits_url():
    """Returns the full Digbi URL for genetic traits."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_GENETIC_TRAITS_PATH")

    if not digbi_url or not url_path:
        raise ValueError(
            "Missing required environment variables for user genetic traits URL"
        )

    return digbi_url + url_path


def get_user_weight_logs_url():
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_WEIGHT_LOGS_URL")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for Weight Logs URL")

    return digbi_url + url_path


def get_user_ibs_logs_url():
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_IBS_LOGS_URL")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for IBS Logs URL")

    return digbi_url + url_path


def get_user_nd_score_stats_url():
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("USER_ND_SCORE_STATS_URL")

    if not digbi_url or not url_path:
        raise ValueError("Missing required environment variables for ND Score Stats URL")

    return digbi_url + url_path


def get_bar_code_slack_channel():
    return get_env_var("BAR_CODE_SLACK_CHANNEL")


def get_barcodes_scanned_url():
    """Return the full Digbi URL for the barcodes scanned endpoint."""
    digbi_url = get_env_var("DIGBI_URL")
    url_path = get_env_var("BARCODES_SCANNED_PATH")

    if not digbi_url or not url_path:
        raise ValueError(
            "Missing required environment variables for barcodes scanned URL"
        )

    return digbi_url + url_path

def get_user_summary_report_context_url():
    digbi_url = get_env_var("DIGBI_URL")
    resource_path = get_env_var("USER_SUMMARY_REPORT_CONTEXT_PATH")

    if not digbi_url or not resource_path:
        raise ValueError(
            "Missing required environment variables for Digbi journey events URL"
        )

    return digbi_url + resource_path


def get_upload_summary_file_url():
    digbi_url = get_env_var("DIGBI_URL")
    resource_path = get_env_var("SUMMARY_REPORT_FILE_UPLOAD_PATH")

    if not digbi_url or not resource_path:
        raise ValueError(
            "Missing required environment variables for Digbi journey events URL"
        )

    return digbi_url + resource_path
