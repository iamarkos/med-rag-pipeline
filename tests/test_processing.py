"""Tests for what happens to a document after upload (app/processing.py).

The heavy models are replaced by instant stand-ins, so these tests are fast and
need no downloads. All text is synthetic.
"""

import pytest
from sqlalchemy.exc import OperationalError

from app.models import ClinicalDocument
from app.processing import mark_failed, process_document
from app.status import DocumentStatus, ErrorCode

NOTE = "John Smith has chest pain"


@pytest.fixture
def fake_models(monkeypatch):
    """Replace the redaction and embedding models with instant stand-ins."""
    monkeypatch.setattr(
        "app.processing.redact_pii", lambda text: text.replace("John Smith", "<PERSON>")
    )
    monkeypatch.setattr("app.processing.embed_text", lambda text: [0.1] * 384)


def _reload(db, document_id):
    """Read a document again, to see what the code under test saved."""
    db.expire_all()
    return db.get(ClinicalDocument, document_id)


def test_a_document_is_redacted_embedded_and_completed(db, add_document, fake_models):
    document_id = add_document()

    result = process_document(document_id, NOTE)

    assert result == {"status": "completed", "doc_id": document_id}
    document = _reload(db, document_id)
    assert document.status == DocumentStatus.COMPLETED
    assert document.error_code is None
    assert document.extracted_data["redacted_text"] == "<PERSON> has chest pain"
    assert document.extracted_data["symptoms"] == ["cardiac distress"]
    assert len(document.embedding) == 384


def test_a_redaction_failure_is_recorded_and_leaks_no_text(
    db, add_document, fake_models, monkeypatch, capsys
):
    def broken(text):
        raise ValueError(f"cannot parse: {text}")

    monkeypatch.setattr("app.processing.redact_pii", broken)
    document_id = add_document()

    result = process_document(document_id, NOTE)

    assert result == {
        "status": "failed",
        "doc_id": document_id,
        "error_code": ErrorCode.REDACTION_FAILED,
    }
    document = _reload(db, document_id)
    assert document.status == DocumentStatus.FAILED
    assert document.error_code == ErrorCode.REDACTION_FAILED
    logged = capsys.readouterr().out
    assert "ValueError" in logged
    assert "John Smith" not in logged


def test_an_embedding_failure_is_recorded(db, add_document, fake_models, monkeypatch):
    def broken(text):
        raise RuntimeError("model crashed")

    monkeypatch.setattr("app.processing.embed_text", broken)
    document_id = add_document()

    result = process_document(document_id, NOTE)

    assert result["error_code"] == ErrorCode.EMBEDDING_FAILED
    document = _reload(db, document_id)
    assert document.status == DocumentStatus.FAILED
    assert document.error_code == ErrorCode.EMBEDDING_FAILED


def test_a_missing_document_is_reported_as_failed(fake_models):
    result = process_document(999999, NOTE)

    assert result == {
        "status": "failed",
        "doc_id": 999999,
        "error_code": ErrorCode.DOCUMENT_NOT_FOUND,
    }


def _database_is_down():
    raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_a_database_outage_is_not_swallowed(fake_models, monkeypatch):
    # The caller (the Celery task) needs to see it, so it can retry later.
    monkeypatch.setattr("app.processing.SessionLocal", _database_is_down)

    with pytest.raises(OperationalError):
        process_document(1, NOTE)


def test_recording_a_failure_survives_a_database_outage(monkeypatch):
    monkeypatch.setattr("app.processing.SessionLocal", _database_is_down)

    result = mark_failed(1, ErrorCode.DATABASE_UNAVAILABLE)

    assert result == {
        "status": "failed",
        "doc_id": 1,
        "error_code": ErrorCode.DATABASE_UNAVAILABLE,
    }
