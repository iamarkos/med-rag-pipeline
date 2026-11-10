from typing import Any

import fitz
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy.orm import Session

from app.celery_app import PROCESS_NOTE_TASK, celery_app
from app.crypto import encrypt_text
from app.database import get_db
from app.embeddings import embed_text
from app.models import ClinicalDocument
from app.original_store import OriginalStore, get_original_store
from app.patients import PATIENT_REF_PATTERN, get_or_create_patient
from app.status import DocumentStatus, ErrorCode

# The database schema (tables and the pgvector extension) is created by the
# Alembic migrations, not by the API at startup.
app = FastAPI(title="Medical RAG Pipeline")

# Create the original store now, so a missing ORIGINALS_DIR stops the API at
# startup instead of at the first upload.
get_original_store()


@app.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    patient_ref: str = Form(..., pattern=PATIENT_REF_PATTERN),
    db: Session = Depends(get_db),
    store: OriginalStore = Depends(get_original_store),
) -> dict[str, Any]:
    # Validate File Type
    allowed_types = ["text/plain", "text/csv", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail="Unsupported Media Type. Please upload a .txt, .csv, or .pdf file.",
        )

    content = await file.read()
    text_content = ""

    # Secure In-Memory Parsing
    if file.content_type == "application/pdf":
        try:
            # Open the PDF directly from the byte stream
            pdf_document = fitz.open(stream=content, filetype="pdf")
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text_content += str(page.get_text())
            pdf_document.close()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {e!s}")
    else:
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Ensure valid UTF-8 text.")

    # The patient is known only by a pseudonymous reference, and the same
    # reference always gives the same patient. Saved in one transaction: either
    # the patient and the document both exist, or neither does.
    patient = get_or_create_patient(db, patient_ref)
    new_doc = ClinicalDocument(
        status=DocumentStatus.PENDING,
        patient=patient,
    )
    db.add(new_doc)
    db.flush()  # assigns the id and the source_ref; nothing is saved yet
    source_ref = new_doc.source_ref

    # Keep the original, so a doctor can open it later. If the database save
    # then fails, remove the file again so none is left behind unreferenced.
    try:
        store.save(source_ref, content, file.content_type or "")
        db.commit()
    except Exception:
        db.rollback()
        store.delete(source_ref)
        raise
    db.refresh(new_doc)

    # Send to Celery worker (by task name, so the API never imports the worker).
    # The text is encrypted first, so it is unreadable while it waits in Redis.
    encrypted_text = encrypt_text(text_content)
    try:
        task = celery_app.send_task(
            PROCESS_NOTE_TASK, args=[new_doc.id, encrypted_text]
        )
    except BrokerError:
        # Redis is unreachable: nothing will ever process this document, so say so.
        new_doc.status = DocumentStatus.FAILED
        new_doc.error_code = ErrorCode.QUEUE_UNAVAILABLE
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Processing queue unavailable. Please try again later.",
        )

    return {
        "message": "Document received and queued for processing.",
        "task_id": task.id,
        "database_id": new_doc.id,
        "patient_ref": patient_ref,
        "source_ref": source_ref,
    }


@app.get("/task/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    # Check Redis for the status of the task
    task_result = celery_app.AsyncResult(task_id)

    if task_result.state == "SUCCESS":
        # The task reports its own outcome: "completed", or "failed" + error_code.
        outcome = task_result.result
        return {"status": outcome["status"], "result": outcome}

    if task_result.state == "FAILURE":
        # The task died. Never return the exception itself: it may contain text.
        return {"status": "failed", "result": {"error_code": ErrorCode.TASK_CRASHED}}

    return {"status": task_result.status}


@app.get("/documents/{document_id}")
def get_document_status(
    document_id: int, db: Session = Depends(get_db)
) -> dict[str, Any]:
    # The database is the source of truth for what happened to a document.
    document = db.get(ClinicalDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return {
        "id": document.id,
        "status": document.status,
        "error_code": document.error_code,
    }


@app.get("/documents/{document_id}/original")
def get_original(
    document_id: int,
    db: Session = Depends(get_db),
    store: OriginalStore = Depends(get_original_store),
) -> Response:
    # This is the doctor's path to the real document. It is NOT redacted, and
    # there is no login yet, so it must not be exposed beyond a demo.
    document = db.get(ClinicalDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    original = store.load(document.source_ref)
    if original is None:
        raise HTTPException(status_code=404, detail="The original is not available.")

    return Response(
        content=original.content,
        media_type=original.content_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/search")
def search_documents(query: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    # Convert the user's question into a mathematical vector
    query_vector = embed_text(query)

    # Perform Cosine Similarity Search using pgvector
    # The .cosine_distance() function maps directly to PostgreSQL's <=> operator
    results = (
        db.query(ClinicalDocument)
        .filter(
            ClinicalDocument.status == "completed",
            ClinicalDocument.embedding.is_not(None),
        )
        .order_by(ClinicalDocument.embedding.cosine_distance(query_vector))
        .limit(3)
        .all()
    )

    # Return the semantically closest medical documents
    return {
        "query": query,
        "results": [
            {
                "id": doc.id,
                "name": doc.display_name,
                "source_ref": doc.source_ref,
                "extracted_data": doc.extracted_data,
            }
            for doc in results
        ],
    }
