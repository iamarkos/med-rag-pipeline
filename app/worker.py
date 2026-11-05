import time
from celery import Celery
from sentence_transformers import SentenceTransformer
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from app.database import SessionLocal
from app.models import ClinicalDocument

# Initialize Celery
celery_app = Celery(
    "medical_worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

# Load the AI model globally
print("Loading HuggingFace AI Model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("Loading Microsoft Presidio PII Analyzer...")
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

print("AI Models loaded successfully!")

@celery_app.task(bind=True)
def process_clinical_note(self, document_id: int, document_text: str):
    print(f"Task {self.request.id} started for Document ID: {document_id}")

    # Redact PII
    analyzer_results = analyzer.analyze(
        text=document_text,
        entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"],
        language='en'
    )
    anonymized_result = anonymizer.anonymize(
        text=document_text,
        analyzer_results=analyzer_results # type: ignore
    )
    safe_text = anonymized_result.text


    # Converts the text into an array of 384 floating-point numbers
    embedding_vector = model.encode(safe_text).tolist()
    
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
        "redacted_text": safe_text
    }
    
    # Save to PostgreSQL
    db = SessionLocal()
    try:
        # Find the pending document in the database
        document = db.query(ClinicalDocument).filter(ClinicalDocument.id == document_id).first()
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