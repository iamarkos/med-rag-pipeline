from typing import Any

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from app.celery_app import PROCESS_NOTE_TASK, celery_app
from app.database import SessionLocal
from app.embeddings import embed_text, get_embedding_model
from app.models import ClinicalDocument

# Load the models when the worker starts, so the first task is not slow.
print("Loading HuggingFace AI Model...")
get_embedding_model()

print("Loading Microsoft Presidio PII Analyzer...")
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

print("AI Models loaded successfully!")


@celery_app.task(bind=True, name=PROCESS_NOTE_TASK)  # type: ignore[untyped-decorator]
def process_clinical_note(
    self: Any, document_id: int, document_text: str
) -> dict[str, Any]:
    print(f"Task {self.request.id} started for Document ID: {document_id}")

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
    db = SessionLocal()
    try:
        # Find the pending document in the database
        document = (
            db.query(ClinicalDocument)
            .filter(ClinicalDocument.id == document_id)
            .first()
        )
        if document:
            document.extracted_data = extracted_data
            document.embedding = embedding_vector
            document.status = "completed"

            db.commit()
            print(f"Document {document_id} processed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")
    finally:
        db.close()

    return {"status": "completed", "doc_id": document_id}
