from unittest.mock import patch


def test_upload_document(client):
    # We 'patch' the Celery task. Instead of sending data to Redis,
    # it intercepts the call and returns a fake task ID.
    with patch("app.main.process_clinical_note.delay") as mock_celery_task:
        # Setup the mock return value to mimic Celery's behavior
        mock_celery_task.return_value.id = "test-task-uuid-1234"

        # 1. Prepare the mock file and form data
        files = {
            "file": (
                "sample_clinical.txt",
                b"Patient complains of chest pain.",
                "text/plain",
            )
        }
        data = {"patient_name": "Test Patient"}

        # 2. Execute the request
        response = client.post("/upload", files=files, data=data)

        # 3. Assert the API behaves exactly as expected
        assert response.status_code == 202

        response_data = response.json()
        assert (
            response_data["message"] == "Document received and queued for processing."
        )
        assert response_data["task_id"] == "test-task-uuid-1234"
        assert "database_id" in response_data
        assert "patient_uuid" in response_data

        # 4. Verify the API actually tried to trigger the background worker
        mock_celery_task.assert_called_once()
