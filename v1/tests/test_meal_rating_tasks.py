import os
import asyncio

from utils.env_loader import get_meal_rating_slack_channel


UPDATED_ANALYSIS = """{
    "foodCategories": [
        {
            "foodCategory": "High Glucose Carbs - Refined flours",
            "description": "Burger Bun",
            "novaClassification": "4"
        }
    ],
    "foodType": "Meal",
    "mealTime": "Dinner",
    "ingredients": ["Burger Bun"],
    "ultraProcessed": true,
    "Fruits - Group 1 (Above Threshold: 1 cup)": false
}"""


def sample_request_context(app):
    return {
        "payload": {
            "meal_info": {
                "image_id": 12209,
                "food_post_id": 6069,
                "image_url": "https://example.com/img.jpg",
                "cgm_meal_context": {"cgm_bad_peak": True, "cgm_bad_recovery": True, "meal_time": ""},
                "meal_description": "burgers"
            },
            "meta_data": {"feature_tag": "BETA"},
            "user_info": {"user_token": os.getenv('TEST_USER_ID_TOKEN', 'token'), "user_type": "TEST"}
        },
        "agents": app.state.AGENTS,
        "channel": get_meal_rating_slack_channel(),
        "meal_id_msg": "Testing",
        "logs": {},
        "errors": [],
        "agent_interactions": {}
    }

#
# def test_finalize_feedback_for_diff_user_types(app, mocker):
#     request_ctx = sample_request_context(app)
#     request_ctx["updated_analysis_result"] = UPDATED_ANALYSIS
#
#     agent = request_ctx["agents"]["nutrition_agent"]
#     mocker.patch.object(agent, "access_user_health_card", return_value=([], [], [], [], []))
#     mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.extract_meal_info",
#         return_value=("Meal", "", [], {}, False, {})
#     )
#     mocker.patch.object(
#         agent,
#         "calculate_nd_score",
#         new_callable=mocker.AsyncMock,
#         return_value=(5, [], [], [])
#     )
#     mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.calculate_meal_score",
#         return_value={"score": 5}
#     )
#     mocker.patch.object(
#         agent,
#         "generate_feedback",
#         new_callable=mocker.AsyncMock,
#         return_value="Good job"
#     )
#     mocker.patch("orchestrator.orchestrators.nutrition_agent.send_meal_rating_message")
#     mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.insert_row_meal_rating_logs",
#         return_value=None
#     )
#     send_resp = mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.send_meal_rating_response",
#         new_callable=mocker.AsyncMock
#     )
#     mocker.patch("orchestrator.orchestrators.nutrition_agent.generate_meal_rating_response", return_value={"status": 200})
#
#     asyncio.run(agent.finalize_feedback_task(request_ctx))
#
#     assert request_ctx["final_feedback"] == "Good job"
#     assert request_ctx["calculate_nd_score_output"][0] == 5
#     send_resp.assert_called_once()
#
#     request_ctx = sample_request_context(app)
#     request_ctx["payload"]["meta_data"]["feature_tag"] = "PRODUCTION"
#     request_ctx["updated_analysis_result"] = UPDATED_ANALYSIS
#
#     agent = request_ctx["agents"]["nutrition_agent"]
#     mocker.patch.object(agent, "access_user_health_card", return_value=([], [], [], [], []))
#     mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.extract_meal_info",
#         return_value=("Meal", "", [], {}, False, {})
#     )
#     mocker.patch.object(
#         agent,
#         "calculate_nd_score",
#         new_callable=mocker.AsyncMock,
#         return_value=(5, [], [], [])
#     )
#     mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.calculate_meal_score",
#         return_value={"score": 5}
#     )
#     mocker.patch.object(
#         agent,
#         "generate_feedback",
#         new_callable=mocker.AsyncMock,
#         return_value="Good job"
#     )
#     mocker.patch("orchestrator.orchestrators.nutrition_agent.send_meal_rating_message")
#     mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.insert_row_meal_rating_logs",
#         return_value=None
#     )
#     send_resp = mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.send_meal_rating_response",
#         new_callable=mocker.AsyncMock
#     )
#     mocker.patch("orchestrator.orchestrators.nutrition_agent.generate_meal_rating_response", return_value={"status": 200})
#
#     asyncio.run(agent.finalize_feedback_task(request_ctx))
#
#     assert request_ctx["final_feedback"] == "Good job"
#     assert request_ctx["calculate_nd_score_output"][0] == 5
#     send_resp.assert_called_once()
