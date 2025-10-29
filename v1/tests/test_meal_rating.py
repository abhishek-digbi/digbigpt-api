import os
import asyncio

from orchestrator.api.controllers.meal_rating_controller import process_meal_image_task, enrich_with_description_task
from utils.env_loader import get_meal_rating_slack_channel


def get_updated_analysis_result():
    return """{
        "foodCategories": [
            {
                "foodCategory": "High Glucose Carbs - Refined flours",
                "description": "Burger Bun",
                "novaClassification": "4"
            },
            {
                "foodCategory": "Proteins - High SFA",
                "description": "Beef Patty",
                "novaClassification": "3"
            },
            {
                "foodCategory": "Fats - Nuts",
                "description": "Sesame Seeds",
                "novaClassification": "1",
                "quantity": "<1/4 TBSP"
            },
            {
                "foodCategory": "Vegetables - Group 2",
                "description": "Lettuce",
                "novaClassification": "1",
                "quantity": "<1/4 cup"
            },
            {
                "foodCategory": "Vegetables - Group 2",
                "description": "Tomato",
                "novaClassification": "1",
                "quantity": "<1/4 cup"
            },
            {
                "foodCategory": "Beverage - Level 1",
                "description": "Beer",
                "novaClassification": "4"
            },
            {
                "foodCategory": "Vegetables - Group 3",
                "description": "French Fries",
                "novaClassification": "4",
                "quantity": "<1/4 cup"
            }
        ],
        "foodType": "Meal",
        "mealTime": "Dinner",
        "ingredients": [
            "Burger Bun",
            "Beef Patty",
            "Sesame Seeds(<1/4 TBSP)",
            "Lettuce(<1/4 cup)",
            "Tomato(<1/4 cup)",
            "Beer",
            "French Fries(<1/4 cup)"
        ],
        "ultraProcessed": true,
        "Fruits - Group 1 (Above Threshold: 1 cup)": false,
        "Fruits - Group 2 (Above Threshold: 1/2 cup)": false,
        "Vegetables - Group 3 (Above Threshold: 1/4 cup)": false,
        "Fats - Seeds (Above Threshold: 1 1/2 TBSP)": false,
        "Fats - Nuts (Above Threshold: 1 1/2 TBSP)": false,
        "Vegetables - Group 1 & 2 (Below Threshold: < 1 cups)": true
    }"""


# def test_finalize_feedback_for_diff_user_types(app, mocker):
#     mocker.patch("requests.post")
#     mocker.patch("orchestrator.api.controllers.meal_rating_controller.insert_row_meal_rating_logs", return_value=None)
#     # mocker.patch("orchestrator.api.controllers.meal_rating_controller.calculate_meal_score", return_value={"score": 5})
#
#     request_context = get_sample_request_context(app)
#     request_context["updated_analysis_result"] = get_updated_analysis_result()
#     request_context["agents"]["nutrition_agent"].finalize_feedback_task(request_context)
#     assert "calculate_nd_score" in request_context["agent_interactions"]
#     assert "response" in request_context["agent_interactions"]["calculate_nd_score"]
#     assert "generate_feedback" in request_context["agent_interactions"]
#     assert request_context["agent_interactions"]["generate_feedback"]["ctx.data"]["nd_score"] == 5
#
#     request_context = get_sample_request_context(app)
#     request_context["payload"]["meta_data"]["feature_tag"] = "PRODUCTION"
#     request_context["updated_analysis_result"] = get_updated_analysis_result()
#     request_context["agents"]["nutrition_agent"].finalize_feedback_task(request_context)
#     assert "calculate_nd_score" in request_context["agent_interactions"]
#     assert "response" in request_context["agent_interactions"]["calculate_nd_score"]
#     assert "generate_feedback" in request_context["agent_interactions"]
#     assert request_context["agent_interactions"]["generate_feedback"]["ctx.data"]["nd_score"] == 5


def get_sample_request_context(app):
    return {
        "payload": {
            "meal_info": {
                "image_id": 12209,
                "food_post_id": 6069,
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/0/0b/RedDot_Burger.jpg",
                "cgm_meal_context": {
                    "cgm_bad_peak": True,
                    "cgm_bad_recovery": True,
                    "meal_time": ""
                },
                "meal_description": "burgers"
            },
            "meta_data": {
                "feature_tag": "BETA"
            },
            "user_info": {
                "user_token": f"{os.getenv('TEST_USER_ID_TOKEN')}",
                "user_type": "TEST"
            }
        },
        "agents": app.state.AGENTS,
        "channel": get_meal_rating_slack_channel(),
        "meal_id_msg": "Testing",
        "logs": {},
        "errors": [],
        "agent_interactions": {},
        "db": None
    }


# def test_proper_image_empty_description(app, mocker):
#     mocker.patch("requests.post")
#     submit_mock = mocker.patch("orchestrator.api.services.async_executor.executor.submit")
#     insert_log_mock = mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.insert_row_meal_rating_logs", return_value=None
#     )
#     send_response_mock = mocker.patch(
#         "orchestrator.api.controllers.meal_rating_controller.send_meal_rating_response", return_value=None
#     )
#     # mocker.patch("orchestrator.api.controllers.meal_rating_controller.calculate_meal_score", return_value={"score": 5})
#     request_context = get_sample_request_context(app)
#     request_context["payload"]["meal_info"]["meal_description"] = ""
#     process_meal_image_task(request_context)
#     assert not request_context["errors"]
#     assert "image_analysis_result" in request_context
#     assert "analyze_image_v2" in request_context["agent_interactions"]
#     assert "foodCategories" in request_context["agent_interactions"]["analyze_image_v2"]["response"]
#     assert "ingredients" in request_context["agent_interactions"]["analyze_image_v2"]["response"]
#     # assert request_context["agent_interactions"]["analyze_image_v2"]["response"]["foodType"] == "Meal"
#     submit_mock.assert_called_once_with(enrich_with_description_task, request_context)
#     submit_mock.reset_mock()
#     enrich_with_description_task(request_context)
#     assert "updated_analysis_result" in request_context
#     submit_mock.assert_called_once_with(request_context["agents"]["nutrition_agent"].finalize_feedback_task, request_context)
#     request_context["agents"]["nutrition_agent"].finalize_feedback_task(request_context)
#     assert "calculate_nd_score" in request_context["agent_interactions"]
#     assert "response" in request_context["agent_interactions"]["calculate_nd_score"]
#     assert "generate_feedback" in request_context["agent_interactions"]
#     # assert request_context["agent_interactions"]["generate_feedback"]["ctx.data"]["nd_score"] == 5
#
#     insert_log_mock.assert_called_once_with(request_context)
#     send_response_mock.assert_called_once()
#     args, kwargs = send_response_mock.call_args
#     assert isinstance(args[0], dict)
#     assert args[0].get("status") == 200


# def test_bad_or_missing_image_and_empty_description_case(app, mocker):
#     mocker.patch("requests.post")
#     insert_log_mock = mocker.patch(
#         "orchestrator.orchestrators.nutrition_agent.insert_row_meal_rating_logs", return_value=None
#     )
#     send_response_mock = mocker.patch(
#         "orchestrator.api.controllers.meal_rating_controller.send_meal_rating_response", return_value=None
#     )
#     submit_mock = mocker.patch("orchestrator.api.services.async_executor.executor.submit")
#
#     request_context = get_sample_request_context(app)
#     request_context["payload"]["meal_info"]["image_url"] = ""
#     request_context["payload"]["meal_info"]["meal_description"] = ""
#
#     process_meal_image_task(request_context)
#
#     assert "image_analysis_result" not in request_context
#     submit_mock.assert_called_once_with(enrich_with_description_task, request_context)
#
#     enrich_with_description_task(request_context)
#
#     assert "errors" in request_context
#     assert isinstance(request_context["errors"], list)
#     assert len(request_context["errors"]) == 1
#     assert "BadImageAndEmptyDescription" in str(request_context["errors"])
#
#     insert_log_mock.assert_called_once_with(request_context)
#     send_response_mock.assert_called_once()
#     args, kwargs = send_response_mock.call_args
#     assert isinstance(args[0], dict)
#     assert args[0].get("status") == 400


def test_bad_or_missing_image_proper_description_case(app, mocker):
    mocker.patch("requests.post")
    mocker.patch("orchestrator.api.controllers.meal_rating_controller.insert_row_meal_rating_logs", return_value=None)
    mocker.patch("orchestrator.api.controllers.meal_rating_controller.send_meal_rating_message")
    mocker.patch("orchestrator.api.controllers.meal_rating_controller.send_meal_rating_response")
    mocker.patch("asyncio.create_task")

    # 1. Case: Missing image_url
    request_context_missing = get_sample_request_context(app)
    request_context_missing["payload"]["meal_info"]["image_url"] = ""
    asyncio.run(process_meal_image_task(request_context_missing))

    assert "image_analysis_result" not in request_context_missing

    # 2. Case: Bad image_url
    request_context_bad = get_sample_request_context(app)
    request_context_bad["payload"]["meal_info"]["image_url"] = "someBadUrl"
    asyncio.run(process_meal_image_task(request_context_bad))

    assert "image_analysis_result" not in request_context_bad
    assert "errors" in request_context_bad


# def test_proper_image_proper_description(app, mocker):
#     mocker.patch("requests.post")
#     mocker.patch("orchestrator.orchestrators.nutrition_agent.insert_row_meal_rating_logs", return_value=None)
#     # mocker.patch("orchestrator.orchestrators.nutrition_agent.calculate_meal_score", return_value={"score": 5})
#     submit_mock = mocker.patch("orchestrator.api.services.async_executor.executor.submit")
#     request_context = get_sample_request_context(app)
#     process_meal_image_task(request_context)
#     assert not request_context["errors"]
#     assert "analyze_image_v2" in request_context["agent_interactions"]
#     assert "foodCategories" in request_context["agent_interactions"]["analyze_image_v2"]["response"]
#     assert "ingredients" in request_context["agent_interactions"]["analyze_image_v2"]["response"]
#     # assert request_context["agent_interactions"]["analyze_image_v2"]["response"]["foodType"] == "Meal"
#     submit_mock.assert_called_once_with(enrich_with_description_task, request_context)
#     submit_mock.reset_mock()
#     enrich_with_description_task(request_context)
#     assert not request_context["errors"]
#     assert "update_wdesc_v2" in request_context["agent_interactions"]
#     assert "foodCategories" in request_context["agent_interactions"]["update_wdesc_v2"]["response"]
#     assert "ingredients" in request_context["agent_interactions"]["update_wdesc_v2"]["response"]
#     assert request_context["agent_interactions"]["update_wdesc_v2"]["response"]["foodType"] == "Meal"
#     submit_mock.assert_called_once_with(request_context["agents"]["nutrition_agent"].finalize_feedback_task, request_context)
#     request_context["agents"]["nutrition_agent"].finalize_feedback_task(request_context)
#     assert "calculate_nd_score" in request_context["agent_interactions"]
#     assert "response" in request_context["agent_interactions"]["calculate_nd_score"]
#     assert "generate_feedback" in request_context["agent_interactions"]
#     assert request_context["agent_interactions"]["generate_feedback"]["ctx.data"]["nd_score"] == 5


def test_success_response_on_valid_request(client, mocker):
    mocker.patch("requests.post")
    mocker.patch("asyncio.create_task")
    mocker.patch("orchestrator.api.controllers.meal_rating_controller.send_meal_rating_message")
    response = client.post("/api/meal-rating", json={
        "meal_info": {
            "image_id": 12209,
            "food_post_id": 6069,
            "image_url": "",
            "cgm_meal_context": {
                "cgm_bad_peak": True,
                "cgm_bad_recovery": True,
                "meal_time": ""
            },
            "meal_description": "sushi"
        },
        "meta_data": {
            "feature_tag": "PRODUCTION"
        },
        "user_info": {
            "user_token": f"{os.getenv('TEST_USER_ID_TOKEN')}"
        }
    })
    data = response.json()
    assert response.status_code == 202
    assert data["message"] == "Request accepted"


def test_bad_request_response_on_missing_data(client, mocker):
    mocker.patch("requests.post")
    mocker.patch("asyncio.create_task")
    mocker.patch("orchestrator.api.controllers.meal_rating_controller.send_meal_rating_message")
    request = {
        "meal_info": {
            "food_post_id": 6069,
            "image_url": "",
            "cgm_meal_context": {
                "cgm_bad_peak": True,
                "cgm_bad_recovery": True,
                "meal_time": ""
            },
            "meal_description": "sushi"
        },
        "meta_data": {
            "feature_tag": "PRODUCTION"
        },
        "user_info": {
            "user_token": "580fLBabJ7aXKOIDUo/r6+aB2ju12rRV8+sq3GoC/Uc="
        }
    }
    response = client.post("/api/meal-rating", json=request)
    data = response.json()
    assert response.status_code == 400
    assert "Invalid request payload" in data["message"]


def test_get_filtered_logs_missing_image_id(client, mocker):
    mocker.patch("orchestrator.api.controllers.meal_rating_controller.get_filtered_meal_rating_logs")
    response = client.get("/api/meal-rating/logs")
    assert response.status_code == 400


def test_get_filtered_logs_success(client, mocker):
    mock_get_logs = mocker.patch(
        "orchestrator.api.controllers.meal_rating_controller.get_filtered_meal_rating_logs",
        return_value=None
    )

    response = client.get("/api/meal-rating/logs?image_id=123")
    assert response.status_code == 200
    mock_get_logs.assert_called_once()


def test_get_filtered_logs_raises_exception(client, mocker):
    mocker.patch(
        "orchestrator.api.controllers.meal_rating_controller.get_filtered_meal_rating_logs",
        side_effect=Exception("Simulated failure")
    )

    response = client.get("/api/meal-rating/logs?image_id=123")
    assert response.status_code == 500

