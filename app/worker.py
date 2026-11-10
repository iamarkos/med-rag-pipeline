from typing import Any

from sqlalchemy.exc import OperationalError

from app.celery_app import PROCESS_NOTE_TASK, celery_app
from app.embeddings import get_embedding_model
from app.pii import warm_up
from app.processing import mark_failed, process_document
from app.status import ErrorCode

# When the database is temporarily unreachable, try the task again this many
# times, waiting this long between tries.
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10

# Load the models when the worker starts, so the first task is not slow.
print("Loading HuggingFace AI Model...")
get_embedding_model()

print("Loading Microsoft Presidio PII Analyzer...")
warm_up()

print("AI Models loaded successfully!")


@celery_app.task(bind=True, name=PROCESS_NOTE_TASK, max_retries=MAX_RETRIES)  # type: ignore[untyped-decorator]
def process_clinical_note(
    self: Any, document_id: int, encrypted_text: str
) -> dict[str, Any]:
    print(f"Task {self.request.id} started for Document ID: {document_id}")

    try:
        return process_document(document_id, encrypted_text)
    except OperationalError:
        # The database is temporarily unreachable: wait, then run the task again.
        # No exception is passed on, so nothing sensitive is stored with the retry.
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=RETRY_DELAY_SECONDS)
        return mark_failed(document_id, ErrorCode.DATABASE_UNAVAILABLE)
