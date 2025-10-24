import os

def valid_payload():
    return {
        "meal_info": {
            "image_id": 123,
            "food_post_id": 456,
            "image_url": "http://example.com/image.jpg",
            "cgm_meal_context": {
                "cgm_bad_peak": True,
                "cgm_bad_recovery": True,
                "meal_time": ""
            },
            "meal_description": "test meal"
        },
        "meta_data": {"feature_tag": "PRODUCTION"},
        "user_info": {"user_token": os.getenv('TEST_USER_ID_TOKEN', 'token')}
    }


def test_meal_rating_success(client, mocker):
    mocker.patch('asyncio.create_task')
    mocker.patch('orchestrator.api.controllers.meal_rating_controller.send_meal_rating_message')
    mocker.patch('utils.env_loader.get_meal_rating_slack_channel', return_value='#channel')
    response = client.post('/api/meal-rating', json=valid_payload())
    data = response.json()
    assert response.status_code == 202
    assert data['message'] == 'Request accepted'


def test_meal_rating_bad_request(client, mocker):
    mocker.patch('asyncio.create_task')
    mocker.patch('orchestrator.api.controllers.meal_rating_controller.send_meal_rating_message')
    mocker.patch('utils.env_loader.get_meal_rating_slack_channel', return_value='#channel')
    payload = valid_payload()
    del payload['meal_info']['image_id']
    response = client.post('/api/meal-rating', json=payload)
    data = response.json()
    assert response.status_code == 400
    assert 'Invalid request payload' in data['message']


def test_get_logs_missing_image_id(client):
    response = client.get('/api/meal-rating/logs')
    data = response.json()
    assert response.status_code == 400
    assert 'Missing image_id' in data['message']


def test_get_logs_success(client, mocker):
    mock_get = mocker.patch('orchestrator.api.controllers.meal_rating_controller.get_filtered_meal_rating_logs', return_value=[])
    response = client.get('/api/meal-rating/logs?image_id=1')
    data = response.json()
    assert response.status_code == 200
    assert data['message'] == 'Success'
    mock_get.assert_called_once()


def test_get_user_logs_missing_header(client):
    response = client.get(
        '/api/meal-rating/user-logs?start_date=2025-05-27&end_date=2025-06-03&max_meals=2'
    )
    data = response.json()
    assert response.status_code == 400
    assert 'Missing user-id header' in data['message']

def test_get_user_logs_success(client, mocker):
    mocker.patch(
        'orchestrator.api.controllers.meal_rating_controller.get_meal_ids',
        return_value=["1", "2"],  # Return list of image IDs as strings
    )
    mock_get = mocker.patch(
        'orchestrator.api.controllers.meal_rating_controller.get_generate_feedback_logs_for_images',
        return_value=[{"image_id": "1", "ctx_data": {"some": "data"}}],
    )
    response = client.get(
        '/api/meal-rating/user-logs?start_date=2025-05-27&end_date=2025-06-03&max_meals=2',
        headers={'user-id': 'token'}
    )
    data = response.json()
    assert response.status_code == 200
    assert data['message'] == 'Success'
    assert "ctx_data" in data["result"][0]
    mock_get.assert_called_once()