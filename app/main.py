from fastapi import FastAPI, UploadFile, File, status, HTTPException, Depends
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database import engine, Base
from app.worker import process_clinical_note
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ClinicalDocument

# Before the API starts accepting requests
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Enable the pgvector extension in PostgreSQL
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        
    # 2. Create the tables
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Medical RAG Pipeline", lifespan=lifespan)


@app.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    if file.content_type not in ["text/plain", "text/csv"]:
        raise HTTPException(
            status_code=415,
            detail="Unsupported Media Type. Please upload a raw .txt file."
        )

    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
         raise HTTPException(
            status_code=400,
            detail="File could not be decoded. Ensure it is a valid UTF-8 text file."
        )
    
    # 1. Create a "pending" row in PostgreSQL immediately
    new_doc = ClinicalDocument(filename=file.filename, status="pending")
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc) # Retrieves the generated ID from Postgres
    
    # 2. Send to Celery, passing the new Database ID
    task = process_clinical_note.delay(new_doc.id, text_content)
    
    return {
        "message": "Document received and queued for processing.",
        "task_id": task.id,
        "database_id": new_doc.id,
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