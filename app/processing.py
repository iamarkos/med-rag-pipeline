"""The work done for one uploaded document, as plain functions.

This is kept apart from the Celery task (app/worker.py) so it can be tested
without a queue and without loading the heavy models: tests replace
redact_pii and embed_text with instant stand-ins.
"""

from typing import Any

from sqlalchemy.exc import OperationalError

from app.crypto import decrypt_text
from app.database import SessionLocal
from app.embeddings import embed_text
from app.models import ClinicalDocument
from app.pii import redact_pii
from app.status import DocumentStatus, ErrorCode


def _set_status(document_id: int, status: str, error_code: str | None = None) -> bool:
    """Update a document's status. Returns False if the document does not exist."""
    db = SessionLocal()
    try:
        document = db.get(ClinicalDocument, document_id)
        if document is None:
            return False
        document.status = status
        document.error_code = error_code
        db.commit()
        return True
    finally:
        db.close()


def _save_result(
    document_id: int, extracted_data: dict[str, Any], embedding: list[float]
) -> bool:
    """Store the result and mark the document completed. False if it is gone."""
    db = SessionLocal()
    try:
        document = db.get(ClinicalDocument, document_id)
        if document is None:
            return False
        document.extracted_data = extracted_data
        document.embedding = embedding
        document.status = DocumentStatus.COMPLETED
        document.error_code = None
        db.commit()
        return True
    finally:
        db.close()


def mark_failed(document_id: int, error_code: str) -> dict[str, Any]:
    """Record a failure and return it as the task's result.

    Only a short error code is stored. Exception messages can contain pieces of
    the document, so they never reach the database, Redis or the logs.
    """
    try:
        _set_status(document_id, DocumentStatus.FAILED, error_code)
    except Exception as exc:
        # Best effort: the database may be the very thing that is down.
        print(
            f"Could not record the failure of document {document_id}: "
            f"{type(exc).__name__}"
        )
    return {
        "status": DocumentStatus.FAILED,
        "doc_id": document_id,
        "error_code": error_code,
    }


def _extract_data(safe_text: str) -> dict[str, Any]:
    # Dynamic NLP Extraction
    text_lower = safe_text.lower()
    detected_symptoms: list[str] = []

    if "chest" in text_lower or "breath" in text_lower:
        detected_symptoms.append("cardiac distress")
    if "ankle" in text_lower or "swelling" in text_lower:
        detected_symptoms.append("musculoskeletal injury")

    return {
        "symptoms": detected_symptoms if detected_symptoms else ["unspecified"],
        "word_count": len(safe_text.split()),
        "redacted_text": safe_text,
    }


def process_document(document_id: int, encrypted_text: str) -> dict[str, Any]:
    """Decrypt, redact, embed and store one document. Returns the outcome.

    The text arrives encrypted (see app/crypto.py). The decrypted original lives
    only in this function: it is never saved, and only the redacted copy is.

    A database outage (OperationalError) is deliberately NOT handled here: it
    propagates, so the caller can decide to try again later.
    """
    # The code to report if the stage we are about to run fails.
    failure_code = ErrorCode.DECRYPTION_FAILED
    try:
        if not _set_status(document_id, DocumentStatus.PROCESSING):
            return mark_failed(document_id, ErrorCode.DOCUMENT_NOT_FOUND)

        document_text = decrypt_text(encrypted_text)

        failure_code = ErrorCode.REDACTION_FAILED
        safe_text = redact_pii(document_text)

        # Converts the text into an array of 384 floating-point numbers
        failure_code = ErrorCode.EMBEDDING_FAILED
        embedding_vector = embed_text(safe_text)
        extracted_data = _extract_data(safe_text)

        # Save to PostgreSQL
        failure_code = ErrorCode.SAVE_FAILED
        if not _save_result(document_id, extracted_data, embedding_vector):
            return mark_failed(document_id, ErrorCode.DOCUMENT_NOT_FOUND)
    except OperationalError:
        raise
    except Exception as exc:
        # Log only the kind of error, never its message.
        print(f"Document {document_id} failed ({failure_code}): {type(exc).__name__}")
        return mark_failed(document_id, failure_code)

    print(f"Document {document_id} processed successfully.")
    return {"status": DocumentStatus.COMPLETED, "doc_id": document_id}
