from datetime import datetime, date, timedelta

import numpy as np

from agent_core.config.logging_config import logger
from tools.services.digbi_service import get_meal_ids

from utils import db_ops
from utils.db import DBClient
from utils.json_util import prune_empty
from datetime import datetime, date


def default_processor(data, mapping_info, var):
    """
    Extracts a value using the key_path defined in mapping_info.
    - If key_path is None, return the data as-is.
    - While traversing, only call `.get` when the current value is a dict.
      If the current value is not a dict (e.g., list/str/number), return the
      original API data as-is to avoid type errors.
    """
    if not data:
        logger.warning("no data for default processor")
        return None

    key_path = mapping_info.get("key_path", [var])

    # If key_path is None, return the data as is
    if key_path is None:
        return data

    value = data
    for key in key_path:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            # Do not attempt .get on non-dicts; return original API data
            return data

    return value


def process_last_meal_nd_scoring_details(data):
    """
    Custom processor for processing last meal ND scoring details.
    """
    if not data:
        logger.warning("no data for last_meal_nd_scoring_details")
        return None
    last_meal = data.get("lastMealNdScoringDetails", {})
    if not last_meal:
        return None

    feedbacks = last_meal.get("feedbacks", [])
    extracted_feedback = None

    if feedbacks:
        extracted_feedback = {
            "message": None,
            "nd_score": None,
            "rated_by": None,
            "infractions": [],
            "ingredients": [],
        }
        for feedback in feedbacks:
            if feedback.get("message") and feedback.get("totalScore") is not None:
                extracted_feedback["message"] = feedback["message"]
                extracted_feedback["nd_score"] = feedback["totalScore"]
                if feedback.get("type") is not None:
                    extracted_feedback["rated_by"] = feedback["type"]

            if feedback.get("ingredients") is not None:
                ing = feedback["ingredients"]
                if isinstance(ing, list):
                    extracted_feedback["ingredients"].extend(ing)
                else:
                    extracted_feedback["ingredients"].append(ing)

            for category in ["inflammation", "insulin", "fiberDiversity"]:
                if feedback.get(category) and "infractions" in feedback[category]:
                    for infraction in feedback[category]["infractions"]:
                        if (
                            infraction.get("title")
                            and infraction.get("score") is not None
                        ):
                            extracted_feedback["infractions"].append(
                                {
                                    "title": infraction["title"],
                                    "score": infraction["score"],
                                }
                            )

        if not extracted_feedback.get("message"):
            extracted_feedback = None

    return {
        "user_description": last_meal.get("foodDescription"),
        "posted_At": last_meal.get("postedAt"),
        "coach_feedback": extracted_feedback,
    }


def process_gut_report(data):
    """Processes gut risk data and extracts relevant traits."""
    try:
        if not data:
            logger.warning("no data for gut_report")
            return None
        traits_list = data.get("traits", [])
        report_categories = data.get("reportCategories", [])
        overall_score = data.get("overallScore") or {}

        traits = [
            {"name": trait["name"], "advise_description": trait["riskDescription"]}
            for trait in traits_list
            if trait.get("riskDescription")
        ]
        categories = [
            {"name": category["name"], "advise_description": category["categoryRisk"]}
            for category in report_categories
            if category.get("categoryRisk")
        ]

        if overall_score.get("samples"):
            overall_entry = {
                "name": "Overall Score",
                "advise_description": overall_score["samples"][0]["adviseType"],
            }
            categories.append(overall_entry)

        # Combine entries uniquely by name.
        combined_traits = {entry["name"]: entry for entry in (traits + categories)}
        return {"traits": list(combined_traits.values())}
    except Exception as e:
        logger.error(f"Error processing gut data: {e}")
        return None


def process_genetic_report(data):
    """Processes genetic risk data and extracts report categories, SNPs, and genes."""
    try:

        if not data:
            logger.warning("no data for genetic_report")
            return None

        report_categories = data["nutrition"].get("reportCategories", [])
        updated_data = []
        unique_genes = set()

        for category in report_categories:
            category_name = category.get("name", "Unknown Category")
            for trait in category.get("traits", []):
                trait_name = trait.get("name", "Unknown Trait")
                genetic_info = trait.get("genetic", {})
                advise_description = genetic_info.get("adviseDescription", "No Info")
                user_genes = trait.get("userGenes", [])
                snps_list = [gene["snps"] for gene in user_genes if "snps" in gene]
                genes_list = [gene["genes"] for gene in user_genes if "genes" in gene]

                unique_genes.update(genes_list)
                updated_data.append(
                    {
                        "report category": category_name,
                        "name": trait_name,
                        "risk description": advise_description,
                        "snps": snps_list,
                        "genes": genes_list,
                    }
                )

        return updated_data
    except Exception as e:
        logger.error(f"Error processing genetic data: {e}")
        return None


def process_hybrid_report(data):
    try:
        # Check if data is None or doesn't contain the required key
        if not data or "reportCategories" not in data:
            logger.warning("No valid 'reportCategories' found in data")
            return None  # Return None if no valid data

        report_categories = data.get("reportCategories")

        result = []
        for category in report_categories:
            # Check if category is None or doesn't have the "category" key
            if not category or "category" not in category:
                logger.warning(f"Invalid category data: {category}")
                continue  # Skip invalid category

            category_data = {"Category": category.get("category"), "Traits": []}

            for trait in category.get("traits", []):
                # Check if trait is None or doesn't have the "name" key
                if not trait or "name" not in trait:
                    logger.warning(f"Invalid trait data: {trait}")
                    continue  # Skip invalid trait

                trait_data = {"name": trait.get("name")}

                # Add genetic adviseDescription if present
                if trait.get("genetic") and "risk" in trait["genetic"]:
                    trait_data["genetic"] = {
                        "adviseDescription": trait["genetic"]["risk"]
                    }

                # Add gut adviseDescription if present
                if trait.get("gut") and "risk" in trait["gut"]:
                    trait_data["gut"] = {"adviseDescription": trait["gut"]["risk"]}

                category_data["Traits"].append(trait_data)

            result.append(category_data)

        # Call prune_empty on the final result to remove null/empty values
        return prune_empty(result)
    except Exception as e:
        logger.error(f"Error processing hybrid data: {e}")
        return None


def process_ibs_score(data):
    """Extracts the IBS score from the response data."""
    return data.get("ibsInfo", {})


def process_ibs_score_change(data):
    """
    Extracts IBS symptom scores and calculates score change.

    Returns: ibs_score_change (float, str, or None)
    """
    ibs_score_change = None
    scores = data.get("symptomScores")

    if isinstance(scores, list):
        if len(scores) >= 2:
            first, last = scores[-1].get("score"), scores[0].get("score")
            if first is not None and last is not None:
                ibs_score_change = round(last - first, 2)
        elif len(scores) == 1:
            ibs_score_change = "No change (only 1 score)"
        else:
            ibs_score_change = "No data"

    return ibs_score_change


def process_primary_motivation(data):
    """Extracts the primary motivation."""
    return data.get("primary_motivation")


def process_dietary_restrictions(data):
    """Extracts dietary restrictions."""
    return data.get("dietary_restrictions", data.get("dietaryRestrictions", []))


def process_weight_data(data):
    """
    Extracts weight data and separates BMI.

    Returns:
        dict: Contains both the weight data (with BMI removed) and the BMI value.
    """
    weight_data = data.get("weightData")
    return weight_data


def process_weight_change(data):
    """
    Extracts weight data.

    Returns: weight_change
    """
    weight_data = data.get("weightData")
    first_weight = weight_data.get("first_weight")
    last_weight = weight_data.get("last_weight")
    weight_change = (
        round(last_weight - first_weight, 2) if first_weight and last_weight else None
    )
    return weight_change


def process_weight_loss_percentage(data):
    """
    Extracts weight data.

    Returns: weight_loss_percentage.
    """
    weight_data = data.get("weightData")
    first_weight = weight_data.get("first_weight")
    last_weight = weight_data.get("last_weight")
    weight_loss_percentage = (
        round((last_weight - first_weight) / first_weight * 100, 2)
        if first_weight and last_weight
        else None
    )
    return weight_loss_percentage


def process_weight_logs(data):
    """
    Extracts weight logs.

    Returns: weight_logs_count.
    """
    weight_logs_count = len(data)
    return weight_logs_count


def process_prescription_medications(data):
    """
    Extracts prescription medications.

    Returns: prescription_medications.
    """
    meds = data.get("prescriptionMedicines")
    prescription_medications = (
        ", ".join(m.strip().strip("'\"") for m in meds.split(",") if m.strip())
        if isinstance(meds, str) and meds
        else None
    )
    return prescription_medications


def process_allergies_and_intolerances(data):
    """Extracts allergies and intolerances."""
    return data.get(
        "allergies_and_intolerances", data.get("allergiesAndIntolerances", [])
    )


def process_nd_scores_last_n_days(data):
    """
    Processes ND scores over the last 7 days.

    Filters out None values and computes the mean and median.
    """
    nd_scores = data.get("ndScoresLast7days")
    if nd_scores:
        valid_scores = [score for score in nd_scores if score is not None]
        mean_score = np.mean(valid_scores) if valid_scores else None
        median_score = np.median(valid_scores) if valid_scores else None
    else:
        mean_score, median_score = None, None
    return {"mean": mean_score, "median": median_score}


def process_coach_added_exclusions(data):
    """Extracts coach added exclusions."""
    return data.get("coach_added_exclusions", data.get("coachAddedExclusions", []))


def process_ingredients_to_avoid(data):
    """Extracts ingredients to avoid."""
    return data.get("ingredients_to_avoid", data.get("ingredientsToAvoid", []))


def process_BMI(data):
    """
    Extracts the BMI from the weightData field.
    """
    weight_data = data.get("weightData")
    if weight_data:
        return weight_data.get("BMI")
    return None


def process_high_risk_traits(data):
    """Extracts high risk genetic traits from API response."""

    if not data:
        return []

    if isinstance(data, dict):
        if "HIGH_RISK" in data:
            return data["HIGH_RISK"]
        return data.get(
            "high_risk_genetic_traits",
            data.get("highRiskGeneticTraits", []),
        )

    return []


def process_day_of_week(data):
    """
    Gets the current day of the week as a string (e.g., 'Monday', 'Tuesday', etc.).

    Args:
        data: Not used, but required for consistency with other processors.

    Returns:
        str: The current day of the week as a string.
    """
    import datetime

    return datetime.datetime.now().strftime("%A")


def process_recent_meal_logs(meal_ids_last_7_days):

    if not meal_ids_last_7_days:
        return {}

    db_client = DBClient()

    try:
        recent_meal_logs = db_ops.get_generate_feedback_logs_for_images(
            meal_ids_last_7_days, db_client
        )
        # Extract ctx_data from each meal log and sort by meal_time in descending order (newest first)
        recent_meal_logs_sorted = sorted(
            [
                {"meal_id": log["image_id"], **log["ctx_data"]}
                for log in recent_meal_logs
                if log.get("ctx_data", {}).get("meal_time")
            ],
            key=lambda x: datetime.strptime(x["meal_time"], "%B %d, %Y %H:%M %p"),
            reverse=True,
        )

        # Create a map with key as meal_time + ' ' + meal_type
        meal_map = {
            f"{meal['meal_type']} on {meal['meal_time']}": meal
            for meal in recent_meal_logs_sorted
        }
        return meal_map
    except Exception as e:
        logger.error(f"Couldn't get recent meal logs for ids: {meal_ids_last_7_days}")
        return {}
    finally:
        db_client.close()


def process_barcodes_scanned(barcode_scan_ids):
    """Process barcode scan IDs by fetching matching ASK_EVALUATION_AGENT logs from agent_logs.

    Returns a mapping similar in spirit to recent_meal_logs: a dict keyed by
    a user-friendly label including timestamp, with values containing the scan_id
    and selected details extracted from the log.
    """
    if not barcode_scan_ids:
        return {}

    db_client = DBClient()

    try:
        # The ids returned by Digbi must be prefixed before DB lookup
        prefixed_ids = [f"MEAL_RATING_{str(i)}" for i in barcode_scan_ids]
        logs = db_ops.get_agent_logs_for_context_ids(
            prefixed_ids, "ASK_EVALUATION_AGENT", db_client
        )

        # Sort by timestamp desc if present
        def _ts_val(l):
            ts = l.get("timestamp")
            if isinstance(ts, str):
                # Best-effort parse for ordering; fallback
                try:
                    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S %Z")
                except Exception:
                    return datetime.min
            return ts or datetime.min

        logs_sorted = sorted(logs, key=_ts_val, reverse=True)

        result_map = {}
        for log in logs_sorted:
            ts_raw = log.get("timestamp")
            if isinstance(ts_raw, datetime):
                ts_str = ts_raw.strftime("%B %d, %Y %I:%M %p")
            else:
                ts_str = str(ts_raw) if ts_raw else ""

            # Try to extract a product title/brand from model_context.data
            title = None
            brand = None
            upc = None
            model_ctx = log.get("model_context")
            if isinstance(model_ctx, dict):
                data = model_ctx.get("data") or {}
                if isinstance(data, dict):
                    title = data.get("title") or data.get("product_name")
                    brand = data.get("brand")
                    upc = data.get("upc")

            key_label = (
                f"{title} on {ts_str}" if title else f"scan on {ts_str}" if ts_str else f"scan {log.get('context_id')}"
            )

            result_map[key_label] = {
                "scan_id": log.get("context_id"),
                "title": title,
                "brand": brand,
                "upc": upc,
                "timestamp": ts_str,
                "agent_response": log.get("response"),
            }

        return result_map
    except Exception as e:
        logger.error(
            f"Couldn't get barcode scan logs for ids: {barcode_scan_ids}. Error: {e}",
            exc_info=True,
        )
        return {}
    finally:
        db_client.close()


def process_recent_meals_history(data):
    """
    Processes full meal history from 'result' list.
    Extracts coach feedback, scores, infractions, ingredients, and metadata like mealType and posted_At.
    """
    print(type(data))
    try:
        if not isinstance(data, list):
            logger.warning("Expected 'result' key with a list of meals.")
            return None

        extracted_data = {"meals_feedback_summary": []}

        for meal in data:
            if not isinstance(meal, dict):
                continue

            meal_feedback_data = {
                "user_description": (meal.get("foodDescription") or "").strip(),
                "posted_At": meal.get("postedAt"),
                "posted_date": meal.get("postedDate"),
                "meal_type": meal.get("mealType"),
                "coach_feedback": None,
            }

            feedbacks = meal.get("feedbacks", [])
            if isinstance(feedbacks, list):
                extracted_feedback = extract_data_from_feedback(feedbacks)

                if extracted_feedback.get("message"):
                    meal_feedback_data["coach_feedback"] = extracted_feedback

            extracted_data["meals_feedback_summary"].append(meal_feedback_data)

        result = (
            prune_empty(extracted_data)
            if "prune_empty" in globals()
            else extracted_data
        )
        return result

    except Exception as e:
        logger.error(f"Error processing Recent Meal History: {e}")
        return None


def extract_data_from_feedback(feedbacks):
    extracted_feedback = {
        "message": None,
        "nd_score": None,
        "rated_by": None,
        "infractions": [],
        "ingredients": [],
        "user_feedback": None,
    }

    if feedbacks and feedbacks[0].get("feedbackStatus") == "COMPLETED":
        feedback = feedbacks[0]
        if feedback.get("message") and feedback.get("totalScore") is not None:
            extracted_feedback["message"] = feedback["message"]
            extracted_feedback["nd_score"] = feedback["totalScore"]
            extracted_feedback["rated_by"] = feedback.get("type")
            extracted_feedback["user_feedback"] = feedback.get("userReviewDetails")

        ingredients = feedback.get("ingredients", [])
        if isinstance(ingredients, list):
            extracted_feedback["ingredients"].extend(ingredients)
        elif ingredients:
            extracted_feedback["ingredients"].append(ingredients)

        extracted_feedback["infractions"] = []

        for title, score in feedback["infractionTitlesToScores"].items():
            if title not in [None, "", []] and score not in [None, ""]:
                extracted_feedback["infractions"].append(
                    {"title": title, "score": score}
                )
    return extracted_feedback


def extract_waist_circumference(data):
    """
    :param data: Form Responses
    :return: waist circumference
    """
    waist_circumference_question_id = 1625844086223437824
    return find_response_by_id(data, waist_circumference_question_id)


def extract_cholesterol(data):
    """
    :param data: Form Responses
    :return: hdl and ldl cholesterol
    """

    hdl_question_id = 1625844091860582400
    ldl_question_id = 1625844091881553920
    return [
        find_response_by_id(data, hdl_question_id),
        find_response_by_id(data, ldl_question_id),
    ]


def extract_triglyceride_levels(data):
    """
    :param data: Form Responses
    :return: triglyceride
    """

    triglyceride_question_id = 1344253671189389312
    return find_response_by_id(data, triglyceride_question_id)


def extract_hba1c(data):
    """
    :param data: Form Responses
    :return: hba1c
    """

    hba1c_question_id = 1625844091978022912
    return find_response_by_id(data, hba1c_question_id)


def extract_c_reactive_protein(data):
    """
    :param data: Form Responses
    :return: crp
    """

    crp_question_id = 1625844091998994432
    return find_response_by_id(data, crp_question_id)


def extract_fasting_glucose(data):
    """
    :param data: Form Responses
    :return: fasting glucose
    """

    fasting_glucose_question_id = 1625844091948662784
    return find_response_by_id(data, fasting_glucose_question_id)


def extract_smoking_data(data):
    """
    :param data: Form Responses
    :return: smoking data
    """

    smoking_question_id = 1737092995565838336
    return find_response_by_id(data, smoking_question_id)


def extract_drinking_data(data):
    """
    :param data: Form Responses
    :return: drinking data
    """

    drinking_question_id = 1625844092087074816
    return find_response_by_id(data, drinking_question_id)


def find_response_by_id(sections, target_id):
    for section in sections:
        for response in section["responses"]:
            if response["id"] == target_id:
                return response
    return None  # not found


def extract_height(data):
    return {k: data.get(k) for k in ("height", "heightUnit")}


def calculate_age_from_dob(data):
    """
    Calculate age from a given dictionary containing 'dateOfBirth' in ISO 8601 format.

    Args:
        data (dict): Dictionary with 'dateOfBirth' key, e.g.
                     {"dateOfBirth": "1991-08-09T00:00:00.000+00:00"}

    Returns:
        int: Age in years
    """
    dob_str = data.get("dateOfBirth")
    if not dob_str:
        raise ValueError("dateOfBirth field is missing")

    # Parse ISO 8601 format
    dob = datetime.fromisoformat(dob_str).date()

    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    return age
