from typing import Any

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from sqlalchemy.exc import OperationalError

from app.celery_app import PROCESS_NOTE_TASK, celery_app
from app.database import SessionLocal
from app.embeddings import embed_text, get_embedding_model
from app.models import ClinicalDocument
from app.status import DocumentStatus, ErrorCode

# When the database is temporarily unreachable, try the task again this many
# times, waiting this long between tries.
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10

# Load the models when the worker starts, so the first task is not slow.
print("Loading HuggingFace AI Model...")
get_embedding_model()

print("Loading Microsoft Presidio PII Analyzer...")
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

print("AI Models loaded successfully!")


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


def _failed(document_id: int, error_code: str) -> dict[str, Any]:
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


@celery_app.task(bind=True, name=PROCESS_NOTE_TASK, max_retries=MAX_RETRIES)  # type: ignore[untyped-decorator]
def process_clinical_note(
    self: Any, document_id: int, document_text: str
) -> dict[str, Any]:
    print(f"Task {self.request.id} started for Document ID: {document_id}")

    # The code to report if the stage we are about to run fails.
    failure_code = ErrorCode.REDACTION_FAILED
    try:
        if not _set_status(document_id, DocumentStatus.PROCESSING):
            return _failed(document_id, ErrorCode.DOCUMENT_NOT_FOUND)

        # Redact PII
        analyzer_results = analyzer.analyze(
            text=document_text,
            entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"],
            language="en",
        )
        anonymized_result = anonymizer.anonymize(
            text=document_text,
            analyzer_results=analyzer_results,
        )
        safe_text = anonymized_result.text

        # Converts the text into an array of 384 floating-point numbers
        failure_code = ErrorCode.EMBEDDING_FAILED
        embedding_vector = embed_text(safe_text)

        # Dynamic NLP Extraction
        text_lower = safe_text.lower()
        detected_symptoms = []

        if "chest" in text_lower or "breath" in text_lower:
            detected_symptoms.append("cardiac distress")
        if "ankle" in text_lower or "swelling" in text_lower:
            detected_symptoms.append("musculoskeletal injury")

        extracted_data = {
            "symptoms": detected_symptoms if detected_symptoms else ["unspecified"],
            "word_count": len(safe_text.split()),
            "redacted_text": safe_text,
        }

        # Save to PostgreSQL
        failure_code = ErrorCode.SAVE_FAILED
        if not _save_result(document_id, extracted_data, embedding_vector):
            return _failed(document_id, ErrorCode.DOCUMENT_NOT_FOUND)
        print(f"Document {document_id} processed successfully.")
    except OperationalError:
        # The database is temporarily unreachable: wait, then run the task again.
        # No exception is passed on, so nothing sensitive is stored with the retry.
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=RETRY_DELAY_SECONDS)
        return _failed(document_id, ErrorCode.DATABASE_UNAVAILABLE)
    except Exception as exc:
        # Log only the kind of error, never its message.
        print(f"Task {self.request.id} failed ({failure_code}): {type(exc).__name__}")
        return _failed(document_id, failure_code)

    return {"status": DocumentStatus.COMPLETED, "doc_id": document_id}
