# config/api_data_config.py
from tools.services.api_data_processors import *
from tools.services.digbi_service import *

VALID_REPORT_DATA_CACHE_TIMEOUT = 1296000  # 15 days
VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT = 180  # 3 mins
VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT = 1296000 # 15 days
VALID_USER_PROFILE_CACHE_TIMEOUT = 1296000 # 15 days


API_DATA_CONFIG = {
    "gut_report_data": {
        "fetch": get_user_gut_report,
        "process": process_gut_report,
        "cache_timeout": VALID_REPORT_DATA_CACHE_TIMEOUT,
        "key_path": None,
    },
    "genetic_report_data": {
        "fetch": get_user_genetic_report,
        "process":process_genetic_report,
        "cache_timeout": VALID_REPORT_DATA_CACHE_TIMEOUT,
        "key_path": None,
    },
    "digestive_report_data": {
        "fetch": get_user_digestive_report,
        "process":process_hybrid_report,
        "cache_timeout": VALID_REPORT_DATA_CACHE_TIMEOUT,
        "key_path": None,
    },
    "cgm_report_data": {
        "fetch": fetch_cgm_report_context,
        "process":None,
        "cache_timeout": 60,
        "key_path": None,
    },
    "coach_added_exclusions": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["coachAddedExclusions"],
    },
    "has_eligible_dependents_to_enroll": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["hasEligibleDependentsToEnroll"],
    },
    "primary_motivation": {
        "fetch": get_user_health_snapshot,
        "process": None,  # Use default extraction
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["primary_motivation"],
    },
    "locale": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["preferred_locale"],
    },
    "ibs_score": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["ibsInfo"],
    },
    "ibs_score_change": {
        "fetch": get_user_ibs_logs,
        "process": process_ibs_score_change,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
    },
    "last_meal_nd_scoring_details": {
        "fetch": get_user_health_snapshot,
        "process": process_last_meal_nd_scoring_details,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
    },
    "meal_ids_last_seven_days": {
        "fetch": get_meal_ids_last_7_days,
        "process": None,
        "cache_timeout": 60,
        "key_path": None,
    },
    "ingredients_to_avoid": {
        "fetch": get_user_health_snapshot,
        "process": process_ingredients_to_avoid,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
    },
    "nd_scores_last_n_days": {
        "fetch": get_user_health_snapshot,
        "process": process_nd_scores_last_n_days,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
        "allow_time_range": True,
    },
    "nd_score_average": {
        "fetch": get_user_nd_score_stats,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["average"],
    },
    "meal_logs": {
        "fetch": get_user_nd_score_stats,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["scores"],
        "allow_time_range": True,
    },
    "allergies_and_intolerances": {
        "fetch": get_user_health_snapshot,
        "process": process_allergies_and_intolerances,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
    },
    "weight_data": {
        "fetch": get_user_health_snapshot,
        "process": process_weight_data,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
    },
    "weight_change": {
        "fetch": get_user_health_snapshot,
        "process": process_weight_change,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
    },
    "weight_loss_percentage": {
        "fetch": get_user_health_snapshot,
        "process": process_weight_loss_percentage,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
    },
    "weight_logs": {
        "fetch": get_user_weight_logs,
        "process": process_weight_logs,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
        "allow_time_range": True,
    },
    "prescription_medicine": {
        "fetch": get_user_health_snapshot,
        "process": process_prescription_medications,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None,
    },
    "BMI": {
        "fetch": get_user_health_snapshot,
        "process": process_BMI,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None
    },
    "dietary_restrictions": {
        "fetch": get_user_health_snapshot,
        "process": process_dietary_restrictions,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None
    },
    "recent_meals_history": {
         "fetch": get_user_meal_history,
         "process": process_recent_meals_history,
         "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
         "key_path": None
    },
    "high_risk_traits": {
        "fetch": get_user_genetic_traits,
        "process": process_high_risk_traits,
        "cache_timeout": VALID_REPORT_DATA_CACHE_TIMEOUT,
        "key_path": None
    },
    "product_name": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["product_name"]
    },
    "partner_name": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["partner_name"]
    },
    "variant_name": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["variant_name"],
    },
    "solera_program_id": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["solera_v2_program_id"]
    },
    "date_of_enrollment": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["date_of_enrollment"]
    },
    "user_enrollment_status": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["userEnrollmentStatus"],
    },
    "days_in_current_enrollment": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["daysInCurrentEnrollment"],
    },
    "days_in_program": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["daysInProgram"],
    },
    "total_food_posted_count": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["totalFoodPostedCount"],
    },
    "glp_eligible": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["glpEligible"],
    },
    "eligible_kits": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["eligibleKits"],
    },
    "first_year_report_status": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["firstYearReportStatus"],
    },
    "transit_audit_shipments": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["allShipments"],
    },
    "user_health_metrics":{
        "fetch": get_user_health_metrics,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None
    },
    "journey_events": {
        "fetch": get_user_journey_events,
        "process": None,
        "cache_timeout": 300,
        "key_path": None,
        "allow_time_range": True,
    },
    "day_of_the_week": {
        "fetch": lambda x: {},  # No fetch needed, we'll use the current time
        "process": process_day_of_week,
        "cache_timeout": 300,  # Cache for 5 mins
        "key_path": None
    },
    "waist_circumference": {
        "fetch": get_user_form_responses,
        "process": extract_waist_circumference,
        "cache_timeout": VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT,
        "key_path": None
    },
    "cholesterol":{
        "fetch": get_user_form_responses,
        "process": extract_cholesterol,
        "cache_timeout": VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT,
        "key_path": None
    },
    "triglyceride": {
        "fetch": get_user_form_responses,
        "process": extract_triglyceride_levels,
        "cache_timeout": VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT,
        "key_path": None
    },
    "hba1c":{
        "fetch": get_user_form_responses,
        "process": extract_hba1c,
        "cache_timeout": VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT,
        "key_path": None
    },
    "c_reactive_protein": {
        "fetch": get_user_form_responses,
        "process": extract_c_reactive_protein,
        "cache_timeout": VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT,
        "key_path": None
    },
    "fasting_glucose":{
        "fetch": get_user_form_responses,
        "process": extract_fasting_glucose,
        "cache_timeout": VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT,
        "key_path": None
    },
    "substance_usage_smoking": {
        "fetch": get_user_form_responses,
        "process": extract_smoking_data,
        "cache_timeout": VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT,
        "key_path": None
    },
    "substance_usage_drinking":{
        "fetch": get_user_form_responses,
        "process": extract_drinking_data,
        "cache_timeout": VALID_USER_FORM_RESPONSES_CACHE_TIMEOUT,
        "key_path": None
    },
    "gender":{
        "fetch": get_user_profile,
        "process": None,
        "cache_timeout": USER_PROFILE_CACHE_TTL,
        "key_path": ["gender"]
    },
    "height":{
        "fetch": get_user_profile,
        "process": extract_height,
        "cache_timeout": USER_PROFILE_CACHE_TTL,
        "key_path": None
    },
    "age":{
        "fetch": get_user_profile,
        "process": calculate_age_from_dob,
        "cache_timeout": USER_PROFILE_CACHE_TTL,
        "key_path": None
    },
    "vo2Max":{
        "fetch": get_user_vo2max,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": None
    },
    "recent_meal_logs": {
        "fetch": get_meal_ids_last_7_days,
        "process": process_recent_meal_logs,
        "cache_timeout": 60,  # Cache for 1 min
        "key_path": None
    },
    "barcodes_scanned": {
        "fetch": get_barcodes_scanned_last_7_days,
        "process": process_barcodes_scanned,
        "cache_timeout": 60,
        "key_path": None
    },
    "cgm_stats": {
        "fetch": get_user_cgm_stats,
        "process": None,
        "cache_timeout": 60,
        "key_path": None
    },
    "user_device_type": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["mobile_app_device"]
    },
    "user_coach_info": {
        "fetch": get_user_health_snapshot,
        "process": None,
        "cache_timeout": VALID_USER_HEALTH_SNAPSHOT_CACHE_TIMEOUT,
        "key_path": ["userCoachInfo"]
    }
    #Add more fields as necessary...
}
