from fastapi import FastAPI, UploadFile, File, Form, status, HTTPException, Depends
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database import engine, Base, get_db
from app.models import ClinicalDocument, Patient
from app.worker import process_clinical_note
import fitz

# Before the API starts accepting requests
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enable the pgvector extension in PostgreSQL
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        
    # Create the tables
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Medical RAG Pipeline", lifespan=lifespan)


@app.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...), 
    patient_name: str = Form(...),
    db: Session = Depends(get_db)
):
    # Validate File Type
    allowed_types = ["text/plain", "text/csv", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail="Unsupported Media Type. Please upload a .txt, .csv, or .pdf file."
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
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    else:
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
             raise HTTPException(status_code=400, detail="Ensure valid UTF-8 text.")
    
    # Identity Isolation
    new_patient = Patient(full_name=patient_name)
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    
    # Clinical Storage (UUID linked)
    new_doc = ClinicalDocument(
        filename=file.filename, 
        status="pending",
        patient_id=new_patient.id
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    # Send to Celery worker
    task = process_clinical_note.delay(new_doc.id, text_content)
    
    return {
        "message": "Document received and queued for processing.",
        "task_id": task.id,
        "database_id": new_doc.id,
        "patient_uuid": new_patient.id,
        "filename": file.filename
    }

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    # Check Redis for the status of the task
    from app.worker import celery_app
    task_result = celery_app.AsyncResult(task_id)
    
    if task_result.ready():
        return {"status": "completed", "result": task_result.result}
    
    return {"status": task_result.status}



from sentence_transformers import SentenceTransformer

# Load the model in the API specifically for translating search queries
print("Loading Search Embeddings Model...")
search_model = SentenceTransformer("all-MiniLM-L6-v2")
print("Search Model ready!")

@app.get("/search")
def search_documents(query: str, db: Session = Depends(get_db)):
    # 1. Convert the user's question into a mathematical vector
    query_vector = search_model.encode(query).tolist()
    
    # 2. Perform Cosine Similarity Search using pgvector
    # The .cosine_distance() function maps directly to PostgreSQL's <=> operator
    results = db.query(ClinicalDocument).filter(
        ClinicalDocument.status == "completed",
        ClinicalDocument.embedding.is_not(None)
    ).order_by(
        ClinicalDocument.embedding.cosine_distance(query_vector)
    ).limit(3).all()
    
    # 3. Return the semantically closest medical documents
    return {
        "query": query,
        "results": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "extracted_data": doc.extracted_data
            } for doc in results
        ]
    }