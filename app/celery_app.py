"""The Celery application.
The API imports this module to send jobs to the queue and to look up their
status. The worker imports it to register its tasks. Because it contains no
models, importing it is cheap, so the API never has to load the worker code.
"""

from celery import Celery

from app.config import REDIS_URL

# Name of the task that processes an uploaded note. The API sends the job by
# this name; the worker registers its task under the same name.
PROCESS_NOTE_TASK = "process_clinical_note"

celery_app = Celery("medical_worker", broker=REDIS_URL, backend=REDIS_URL)
