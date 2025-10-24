import json

# from agent_core.services.api_data_processors import process_recent_meals_history


# def test_process_recent_meals_history():
#     result = process_recent_meals_history(get_test_data())
#     print(result["meals_feedback_summary"][0]['coach_feedback']['infractions'][0]['score'])
#     assert result["meals_feedback_summary"][0]['coach_feedback']['infractions'][0]['score'] == -1


def get_test_data():
    return json.loads("""[
        {
            "foodPostId": 6055,
            "foodDescription": "",
            "postedDate": "2025-03-28",
            "postedTime": "01:04PM",
            "postedAt": "2025-03-28 13:04:00",
            "imageUrl": "some url",
            "mealType": "OTHER",
            "imageGalleryId": 12095,
            "insulinResistant": false,
            "feedbacks": [
                {
                    "ndscoreId": 2448,
                    "type": "AI",
                    "coachId": -1,
                    "message": "Some feedback",
                    "totalScore": 13,
                    "infractionCategoryScores": {
                        "insulin": 0,
                        "inflammation": 0,
                        "fibreDiversity": -1
                    },
                    "infractionTitlesToScores": {
                        "High Glucose carb": null,
                        "Low glucose fruits": null,
                        "Alcohol": null,
                        "Processed with chemicals additives": null,
                        "High-glucose fruits": null,
                        "Resistant Starch": null,
                        "Lactose": null,
                        "Starch-rich veggies, grains, or beans": null,
                        "No probiotics": -1,
                        "Sugar or Sugar substitute or Synthetic sweeteners": null,
                        "<2 types of veggies": null,
                        "Gluten": null,
                        "Nuts/seeds/dried fruit": null,
                        "<2 cups of veggies": null,
                        "Caffeine": null
                    },
                    "feedbackStatus": "COMPLETED",
                    "created_at": "2025-03-28 07:35:06.322",
                    "ingredients": [],
                    "cgmDataAvailable": true
                }
            ],
            "isCgmActive": false
        }
    ]""")


def test_process_high_risk_traits_new_format():
    from tools.services.api_data_processors import process_high_risk_traits

    data = {"HIGH_RISK": ["trait_a", "trait_b"]}
    assert process_high_risk_traits(data) == ["trait_a", "trait_b"]


def test_process_high_risk_traits_old_format():
    from tools.services.api_data_processors import process_high_risk_traits

    data = {"high_risk_genetic_traits": ["trait_old"]}
    assert process_high_risk_traits(data) == ["trait_old"]


def test_calculate_age_from_dob(monkeypatch):
    """Ensure age calculation uses current date correctly."""
    from datetime import date as real_date
    from tools.services.api_data_processors import calculate_age_from_dob

    fixed_today = real_date(2025, 8, 20)

    class FixedDate(real_date):
        @classmethod
        def today(cls):
            return fixed_today

    monkeypatch.setattr("tools.services.api_data_processors.date", FixedDate)
    data = {"dateOfBirth": "1991-08-09T00:00:00.000+00:00"}
    assert calculate_age_from_dob(data) == 34
