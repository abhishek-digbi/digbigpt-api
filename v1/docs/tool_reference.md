# Tool Reference

This document lists all tools available in the AI Agent Service. Tools are Python functions that can be invoked by the agent during a run.

## Data Variable Tools

For every variable defined in `tools/config/api_data_config.py` there is a corresponding tool named `get_<variable>` that returns that value for the current user.

| Tool | Description |
| --- | --- |
| `get_gut_report_data` | Processed results from the user's gut microbiome report |
| `get_genetic_report_data` | Insights from the user's genetic report |
| `get_digestive_report_data` | Combined genetic and gut information ("hybrid" report) |
| `get_coach_added_exclusions` | Foods or ingredients a Digbi coach has flagged to avoid |
| `get_primary_motivation` | The member's stated primary motivation for using the program |
| `get_locale` | Preferred language/locale code |
| `get_ibs_score` | Current Irritable Bowel Syndrome score |
| `get_ibs_score_change` | Change in IBS score based on historical logs |
| `get_last_meal_nd_scoring_details` | Feedback and ND score details for the most recent meal |
| `get_meal_ids_last_seven_days` | Meal identifiers from the last seven days |
| `get_ingredients_to_avoid` | Ingredient list that the member should avoid |
| `get_nd_scores_last_n_days` | Mean and median ND scores over a recent period |
| `get_nd_score_average` | Overall average ND score |
| `get_meal_logs` | Historical ND scores for individual meals |
| `get_allergies_and_intolerances` | Known allergies or intolerances |
| `get_weight_data` | Raw weight data including BMI |
| `get_weight_change` | Difference between first and last recorded weight |
| `get_weight_loss_percentage` | Percentage weight change from the starting weight |
| `get_weight_logs` | Number of weight log entries |
| `get_prescription_medicine` | Prescription medications listed by the member |
| `get_BMI` | Body Mass Index value |
| `get_dietary_restrictions` | Any dietary restrictions the user follows |
| `get_recent_meals_history` | Summary of recent meals with coach feedback |
| `get_high_risk_traits` | Genetic traits flagged as high risk |
| `get_product_name` | Name of the Digbi product the user is enrolled in |
| `get_partner_name` | Associated partner or employer name |
| `get_solera_program_id` | Program identifier from Solera integration |
| `get_date_of_enrollment` | Date the user enrolled in Digbi |
| `get_total_food_posted_count` | Cumulative count of food posts logged by the user |
| `get_glp_eligible` | Whether the user is eligible for GLP‑1 |
| `get_eligible_kits` | Transit audit kits the user is eligible to receive |
| `get_first_year_report_status` | Status of the user's first-year transit audit report |
| `get_transit_audit_shipments` | Shipment history for the member's transit audit kits |
| `get_user_health_metrics` | Additional health metrics collected from the API |
| `get_journey_events` | Timeline events associated with the user's program progress |
| `get_day_of_the_week` | The current day of the week (generated at runtime) |
| `get_waist_circumference` | Waist circumference measurement from form responses |
| `get_cholesterol` | HDL and LDL cholesterol values |
| `get_triglyceride` | Triglyceride level from form responses |
| `get_hba1c` | HbA1c lab value |
| `get_c_reactive_protein` | C-reactive protein level |
| `get_fasting_glucose` | Fasting blood glucose value |
| `get_substance_usage_smoking` | Smoking status information |
| `get_substance_usage_drinking` | Drinking habits information |
| `get_gender` | User's gender |
| `get_height` | User's height and measurement unit |
| `get_age` | User's age derived from date of birth |
| `get_vo2Max` | VO₂ max measurement |
| `get_recent_meal_logs` | Recent meal log entries with ND scores and metadata |
| `get_barcodes_scanned` | Recent barcode scan entries resolved from agent logs |
| `fetch_cgm_report_context` | Users's Recent CGM Summary Report Context |
| `get_user_cgm_stats` | Users's CGM Entries |

## Utility Tools

These tools live under `tools/definitions/` and provide additional functionality beyond data lookups.

| Tool | Description |
| --- | --- |
| `get_user_locale` | Return the preferred locale for the given user |
| `get_cgm_tir_by_date` | Gets the user's CGM time-in-range for a given date (YYYY-MM-DD) |
| `cgm_score_report` | Build a CGM Time-in-Range (TIR) report from a percentage |
| `vo2_score_report` | Calculate a VO₂ max score and provide a guidance report |
| `get_meal_feedback` | Fetch meal feedback data for the given entity IDs |
| `full_bioage_report` | Generate a full bio-age report |
| `cgm_meals_summary` | Generate meal summaries based on CGM response patterns for the given user within given date range |
| `cgm_glucose_summary` | Generate a Glucose Summary for the given user within given date range |
