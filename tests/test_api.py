from unittest.mock import MagicMock, patch

from kombu.exceptions import OperationalError as BrokerError

from app.database import SessionLocal
from app.models import ClinicalDocument
from app.status import DocumentStatus, ErrorCode


def test_upload_document(client):
    # We 'patch' the call that sends the job to Celery. Instead of sending data
    # to Redis, it intercepts the call and returns a fake task ID.
    with patch("app.main.celery_app.send_task") as mock_celery_task:
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


def _sample_upload():
    files = {"file": ("note.txt", b"Patient complains of chest pain.", "text/plain")}
    return files, {"patient_name": "Test Patient"}


def test_upload_when_queue_is_down(client):
    files, data = _sample_upload()
    with patch("app.main.celery_app.send_task", side_effect=BrokerError("down")):
        response = client.post("/upload", files=files, data=data)

    assert response.status_code == 503

    # The document must say it failed, instead of staying "pending" forever.
    with SessionLocal() as db:
        latest = db.query(ClinicalDocument).order_by(ClinicalDocument.id.desc()).first()
        assert latest is not None
        assert latest.status == DocumentStatus.FAILED
        assert latest.error_code == ErrorCode.QUEUE_UNAVAILABLE


def test_document_status_after_upload(client):
    files, data = _sample_upload()
    with patch("app.main.celery_app.send_task") as mock_celery_task:
        mock_celery_task.return_value.id = "test-task-uuid-5678"
        upload = client.post("/upload", files=files, data=data)

    document_id = upload.json()["database_id"]
    response = client.get(f"/documents/{document_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": document_id,
        "status": DocumentStatus.PENDING,
        "error_code": None,
    }


def test_document_not_found(client):
    response = client.get("/documents/2147483647")
    assert response.status_code == 404


def _fake_task_result(state, result=None):
    fake = MagicMock()
    fake.state = state
    fake.status = state
    fake.result = result
    return fake


def test_task_status_completed(client):
    outcome = {"status": "completed", "doc_id": 1}
    fake = _fake_task_result("SUCCESS", outcome)
    with patch("app.main.celery_app.AsyncResult", return_value=fake):
        response = client.get("/task/some-task-id")

    assert response.json() == {"status": "completed", "result": outcome}


def test_task_status_reports_a_failed_outcome(client):
    outcome = {
        "status": "failed",
        "doc_id": 1,
        "error_code": ErrorCode.REDACTION_FAILED,
    }
    fake = _fake_task_result("SUCCESS", outcome)
    with patch("app.main.celery_app.AsyncResult", return_value=fake):
        response = client.get("/task/some-task-id")

    assert response.json() == {"status": "failed", "result": outcome}


def test_task_status_crash_does_not_leak_exception_text(client):
    crash = ValueError("patient John Smith has chest pain")
    fake = _fake_task_result("FAILURE", crash)
    with patch("app.main.celery_app.AsyncResult", return_value=fake):
        response = client.get("/task/some-task-id")

    assert response.json() == {
        "status": "failed",
        "result": {"error_code": ErrorCode.TASK_CRASHED},
    }
    assert "John Smith" not in response.text


def test_task_status_while_waiting(client):
    fake = _fake_task_result("PENDING")
    with patch("app.main.celery_app.AsyncResult", return_value=fake):
        response = client.get("/task/some-task-id")

    assert response.json() == {"status": "PENDING"}
