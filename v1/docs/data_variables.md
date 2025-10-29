# Data Variables Reference

The AI Agent Service relies on many user-specific data points when generating prompts. These values can be injected into LangFuse templates or retrieved through built‑in tools.

## Using Variables in LangFuse

When defining a prompt in LangFuse, reference variables using curly braces. For example:

```jinja
Your ND score is {{ nd_score_average }}.
```

During `run_agent`, the service fetches every variable mentioned in the prompt. The [ToolService](../tools/services/tool_service.py) handles these lookups so prompt authors do not need to write code.

## Fetching Variables with Tools

Each variable also has a helper tool named `get_<variable>` (for example `get_gut_report_data`). Tools can be listed in an agent configuration or supplied programmatically. Some tools support an optional `last_num_days` argument when their configuration allows a date range; other tools have no time parameters. Calling the tool returns just that value for the current user.

```yaml
MY_AGENT:
  langfuse_prompt_key: my_prompt
  tools:
    - get_weight_data
```

## Available Variables

The table below summarises all variables defined in `tools/config/api_data_config.py` and what they represent.

| Variable | Description                                                             |
| --- |-------------------------------------------------------------------------|
| `gut_report_data` | Processed results from the user's gut microbiome report                 |
| `genetic_report_data` | Insights from the user's genetic report                                 |
| `digestive_report_data` | Combined genetic and gut information ("hybrid" report)                  |
| `coach_added_exclusions` | Foods or ingredients a Digbi coach has flagged to avoid                 |
| `has_eligible_dependents_to_enroll` | Boolean flag indicating if the member has eligible dependents to enroll |
| `primary_motivation` | The member's stated primary motivation for using the program            |
| `locale` | Preferred language/locale code                                          |
| `user_device_type` | The user's mobile device type from Health Snapshot                      |
| `ibs_score` | Current Irritable Bowel Syndrome score                                  |
| `ibs_score_change` | Change in IBS score based on historical logs                            |
| `last_meal_nd_scoring_details` | Feedback and ND score details for the most recent meal                  |
| `meal_ids_last_seven_days` | Meal identifiers from the last seven days                               |
| `ingredients_to_avoid` | Ingredient list that the member should avoid                            |
| `nd_scores_last_n_days` | Mean and median ND scores over a recent period                          |
| `nd_score_average` | Overall average ND score                                                |
| `meal_logs` | Historical ND scores for individual meals                               |
| `allergies_and_intolerances` | Known allergies or intolerances                                         |
| `weight_data` | Raw weight data including BMI                                           |
| `weight_change` | Difference between first and last recorded weight                       |
| `weight_loss_percentage` | Percentage weight change from the starting weight                       |
| `weight_logs` | Number of weight log entries                                            |
| `prescription_medicine` | Prescription medications listed by the member                           |
| `BMI` | Body Mass Index value                                                   |
| `dietary_restrictions` | Any dietary restrictions the user follows                               |
| `recent_meals_history` | Summary of recent meals with coach feedback                             |
| `high_risk_traits` | Genetic traits flagged as high risk                                     |
| `product_name` | Name of the Digbi product the user is enrolled in                       |
| `partner_name` | Associated partner or employer name                                     |
| `variant_name` | example Partner_Gene+2Gut+CGM                                                                |
| `solera_program_id` | Program identifier from Solera integration                              |
| `date_of_enrollment` | Date the user enrolled in Digbi                                         |
| `user_enrollment_status` | Current enrollment status (e.g., enrolled)                              |
| `days_in_current_enrollment` | Number of days in the current enrollment period                         |
| `days_in_program` | Total number of days since initial program enrollment                   |
| `total_food_posted_count` | Cumulative count of food posts logged by the user                       |
| `glp_eligible` | Whether the user is eligible for GLP‑1                                  |
| `eligible_kits` | Transit audit kits the user is eligible to receive                    |
| `first_year_report_status` | Status of the user's first-year transit audit report                |
| `transit_audit_shipments` | Shipment history for the member's transit audit kits               |
| `user_health_metrics` | Additional health metrics collected from the API                        |
| `journey_events` | Timeline events associated with the user's program progress             |
| `day_of_the_week` | The current day of the week (generated at runtime)                      |
| `waist_circumference` | Waist circumference measurement from form responses                     |
| `cholesterol` | HDL and LDL cholesterol values                                          |
| `triglyceride` | Triglyceride level from form responses                                  |
| `hba1c` | HbA1c lab value                                                         |
| `c_reactive_protein` | C-reactive protein level                                                |
| `fasting_glucose` | Fasting blood glucose value                                             |
| `substance_usage_smoking` | Smoking status information                                              |
| `substance_usage_drinking` | Drinking habits information                                             |
| `gender` | User's gender                                                           |
| `height` | User's height and measurement unit                                      |
| `age` | User's age derived from date of birth                                   |
| `vo2Max` | VO₂ max measurement                                                     |
| `recent_meal_logs` | Recent meal log entries with ND scores and metadata                     |
| `barcodes_scanned` | IDs for scanned barcodes resolved to ASK_EVALUATION_AGENT logs          |
| `user_coach_info` | Assigned coach details for the user (name and about text)               |

Each variable can be referenced directly in a LangFuse prompt or accessed via its corresponding tool. When a tool is invoked or a prompt is generated, the values are fetched from Digbi APIs and cached for performance.
