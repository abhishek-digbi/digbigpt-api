import json

def test_ask_digbi_success(client, mocker):
    """Test async ask-digbi request handling with new JSON format and unique screen_info"""
    mocker.patch("requests.post")  # Mock external callback request

    payload = {
        "user_token": "user_001",
        "user_type": "PRODUCTION",
        "query_id": "123",
        "query": "What are the best exercises for diabetes?",
        "context": {
            "app": {
                "screen_info": "Dashboard->Fitness->Overview",
                "entity_id": "entity-001"
            },
            "conversation": {
                "summary": "User is interested in fitness.",
                "recent_messages": []
            }
        }
    }
    response = client.post("/api/ask-digbi", json=payload)
    data = response.json()

    assert response.status_code == 202
    assert data["message"] == "Request accepted"


def test_ask_digbi_missing_query(client):
    """Test missing query input with new JSON format and unique screen_info"""
    payload = {
        "user_token": "user_001",
        "user_type": "PRODUCTION",
        "query_id": "123",
        # "query" key is intentionally omitted
        "context": {
            "app": {
                "screen_info": "Dashboard",
                "entity_id": "entity-001"
            },
            "conversation": {
                "summary": "User is interested in fitness.",
                "recent_messages": []
            }
        }
    }
    response = client.post("/api/ask-digbi", json=payload)
    data = response.json()

    assert response.status_code == 422
    # assert "Invalid input data" in data["message"]

def test_ask_digbi_missing_timestamp_recent_messages(client):
    """Test missing query input with new JSON format and unique screen_info.
    Also ensure that a recent message is missing the timestamp field."""
    payload = {
        "user_token": "user_001",
        "user_type": "PRODUCTION",
        "query_id": "123",
        # "query" key is intentionally omitted to simulate missing query input.
        "context": {
            "app": {
                "screen_info": "Dashboard",
                "entity_id": "entity-001"
            },
            "conversation": {
                "summary": "User is interested in fitness.",
                "recent_messages": [
                    {
                        "sender": "user",
                        "content": "Please suggest exercises"  # timestamp intentionally missing
                    }
                ]
            }
        }
    }
    response = client.post("/api/ask-digbi", json=payload)
    data = response.json()

    assert response.status_code == 422
    # assert "Invalid input data" in data["message"]

# def test_ops_support(client, mocker, caplog):
#     """Test sync ask-digbi request for ops support with new JSON format and unique screen_info"""
#     mocker.patch("requests.post")
#
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "How do i set up my cgm?",
#         "context": {
#             "app": {
#                 "screen_info": "DashBoard"
#             },
#             "conversation": {
#                 "summary": "",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     assert data["result"]["response"]["status"] == "completed"
#     # assert "ops_support_agent" in caplog.text or "ops_agent" in caplog.text
#     # assert "cgm_agent" in caplog.text

# def test_ask_digbi_sync_bmi(client, mocker, caplog):
#     """Test sync ask-digbi request for BMI with new JSON format and unique screen_info"""
#     mocker.patch("requests.post")
#
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "What is my BMI?",
#         "context": {
#             "app": {
#                 "screen_info": "DashBoard"
#             },
#             "conversation": {
#                 "summary": "User wants to check their BMI.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     assert data["result"]["response"]["status"] == "completed"
#     assert "personalization_agent" in caplog.text


# def test_agent_names_in_logs(client, mocker, caplog):
#     """Test that agent names appear in logs for combined routing with new JSON format and unique screen_info"""
#     mocker.patch("requests.post")
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "What is GLP-1? Recommend me with alternatives if im lactose intolerant",
#         "context": {
#             "app": {
#                 "screen_info": "Dashboard->Reports"
#             },
#             "conversation": {
#                 "summary": "Test conversation.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     assert data["result"]["response"]["status"] == "completed"
#     assert "health_insights_agent" in caplog.text
#     assert "nutrition_agent" in caplog.text


# def test_health_insights_agent(client, mocker, caplog):
#     """Test that a health insights query routes only to the health_insights_agent with new JSON format and unique screen_info"""
#     mocker.patch("requests.post")  # Mock external callback request
#
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "Can you provide insights on my genetic predisposition for Lactose Intolerance?",
#         "context": {
#             "app": {
#                 "screen_info": "Dashboard->Reports->GeneNutrition"
#             },
#             "conversation": {
#                 "summary": "User is inquiring about genetic markers related to blood pressure.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     # Verify that only the health_insights_agent is involved in routing
#     assert "health_insights_agent" in caplog.text
#     assert "nutrition_agent" not in caplog.text


# def test_nutrition_agent_routing(client, caplog):
#     """Test that a nutrition query routes only to the nutrition_agent with new JSON format and unique screen_info"""
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "Can you suggest some meal plans for a lactose intolerant person?",
#         "context": {
#             "app": {
#                 "screen_info": "Dashboard->Reports->GeneNutrition->MealPlans"
#             },
#             "conversation": {
#                 "summary": "Nutrition query.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     assert data["result"]["response"]["status"] == "completed"
#     # Assert that only the nutrition_agent is involved in routing
#     assert "nutrition_agent" in caplog.text
#     assert "health_insights_agent" not in caplog.text


# def test_ambiguous_query_clarification(client, caplog):
#     """Test that an ambiguous query triggers a clarification request with new JSON format and unique screen_info"""
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "I'm not sure what I need help with",
#         "context": {
#             "app": {
#                 "screen_info": "DashBoard"
#             },
#             "conversation": {
#                 "summary": "Ambiguous query.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     status = data.get("result", {}).get("response", {}).get("status")
#     assert status in {"reject", "request_clarification", "respond_directly"}
#     assert "request_clarification" in caplog.text


# def test_support_query(client, caplog):
#     """Test that non-health related queries are properly rejected with new JSON format and unique screen_info"""
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "How do I update my shipping address?",
#         "context": {
#             "app": {
#                 "screen_info": "DashBoard"
#             },
#             "conversation": {
#                 "summary": "Non-health related query.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     assert data["result"]["response"]["status"] == "reject"
#     log_text = caplog.text.lower()
#     # Accept either "your digbi coach" or "your digbi health coach" in the logs
#     assert ("your digbi coach" in log_text or "your digbi health coach" in log_text)
#     assert "nutrition_agent" not in caplog.text


# def test_update_personal_data_query(client, mocker, caplog):
#     """Test that a personal data update query is rejected with an instruction to contact the coach (new JSON format and unique screen_info)"""
#     mocker.patch("requests.post")  # Mock external callback request
#
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "Update my weight to 180 lbs.",
#         "context": {
#             "app": {
#                 "screen_info": ""
#             },
#             "conversation": {
#                 "summary": "User attempting to update personal info.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     assert data["result"]["response"]["status"] == "reject"
#     log_text = caplog.text.lower()
#     assert ("your digbi coach" in log_text or "your digbi health coach" in log_text)


# def test_no_agent_names_in_final_response(client, mocker):
#     """Test that the final JSON response does not include any agent names with new JSON format and unique screen_info"""
#     mocker.patch("requests.post")  # Mock external callback request
#
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "Can you suggest a healthy meal plan for dinner?",
#         "context": {
#             "app": {
#                 "screen_info": "Meal Plans"
#             },
#             "conversation": {
#                 "summary": "User asking for a meal plan.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#     assert response.status_code == 200
#     assert data["result"]["response"]["status"] == "completed"
#     response_str = str(data)
#     assert "nutrition_agent" not in response_str
#     assert "health_insights_agent" not in response_str


# def test_response_tone_simple_friendly_and_direct(client, mocker, caplog):
#     """Test that the final response message is simple, friendly, direct, and empathetic in tone (new JSON format and unique screen_info)"""
#     mocker.patch("requests.post")  # Mock external callback request
#
#     payload = {
#         "user_token": "user_001",
#         "user_type": "PRODUCTION",
#         "query_id": "123",
#         "query": "What is my IBS Score?",
#         "context": {
#             "app": {
#                 "screen_info": "DashBoard"
#             },
#             "conversation": {
#                 "summary": "User wants to check BMI in a friendly manner.",
#                 "recent_messages": []
#             }
#         }
#     }
#     response = client.post("/api/ask-digbi-sync", json=payload)
#     data = response.get_json()
#     assert response.status_code == 200
#     assert data["message"] == "Success"
#     assert data["result"]["response"]["status"] == "completed"
#     assert "personalization_agent" in caplog.text
#     message = data.get("result", {}).get("response", {}).get("message", "")
#     friendly_phrases = [
#         "please", "thank", "i understand", "i'm sorry",
#         "based on your profile", "here's", "could you provide"
#     ]
#     assert any(phrase in message.lower() for phrase in friendly_phrases), (
#         f"Response message does not contain expected friendly phrases: {message}"
#     )
