"""Tests that the uploaded filename is never kept or shown."""

from unittest.mock import patch

from sqlalchemy import inspect

from app.database import engine
from app.models import ClinicalDocument
from app.status import DocumentStatus

# A filename that gives away a patient, as real ones often do.
SECRET_FILENAME = "John_Smith_labs.txt"


def _upload(client):
    files = {
        "file": (SECRET_FILENAME, b"Patient complains of chest pain.", "text/plain")
    }
    with patch("app.main.celery_app.send_task") as mock_celery_task:
        mock_celery_task.return_value.id = "test-task-uuid"
        return client.post("/upload", files=files, data={"patient_ref": "P-0042"})


def test_the_documents_table_has_no_filename_column():
    columns = {c["name"] for c in inspect(engine).get_columns("clinical_documents")}

    assert "filename" not in columns
    assert "source_ref" in columns


def test_upload_does_not_return_the_filename(client):
    response = _upload(client)

    assert response.status_code == 202
    assert "John_Smith" not in response.text
    assert response.json()["source_ref"].startswith("src-")


def test_each_upload_gets_its_own_source_reference(client):
    first = _upload(client).json()["source_ref"]
    second = _upload(client).json()["source_ref"]

    assert first != second


def test_search_does_not_reveal_the_filename(client, db, monkeypatch):
    _upload(client)
    document = db.query(ClinicalDocument).one()
    vector = [1.0] + [0.0] * 383
    document.status = DocumentStatus.COMPLETED
    document.embedding = vector
    document.extracted_data = {"redacted_text": "<PERSON> complains of chest pain."}
    db.commit()
    monkeypatch.setattr("app.main.embed_text", lambda query: vector)

    response = client.get("/search", params={"query": "chest pain"})

    result = response.json()["results"][0]
    assert "John_Smith" not in response.text
    assert result["name"] == f"document-{document.id}"
    assert result["source_ref"] == document.source_ref
