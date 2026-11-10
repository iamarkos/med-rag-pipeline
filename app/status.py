"""Names used to report what happened to a document.

Kept in a module with no imports, so the API, the worker and the tests can all
use the same words without pulling in a database or a model.
"""


class DocumentStatus:
    """Where a document is in its life."""

    PENDING = "pending"  # saved, waiting in the queue
    PROCESSING = "processing"  # a worker is redacting and embedding it
    COMPLETED = "completed"  # searchable
    FAILED = "failed"  # see error_code for the reason


class ErrorCode:
    """Short, fixed reasons for a failure.

    Only these codes are stored and returned. Exception messages are never
    used, because they can contain pieces of the document text.
    """

    QUEUE_UNAVAILABLE = "QUEUE_UNAVAILABLE"  # the API could not reach Redis
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"  # the database row is gone
    DECRYPTION_FAILED = "DECRYPTION_FAILED"  # the queued text could not be decrypted
    REDACTION_FAILED = "REDACTION_FAILED"  # PII removal raised an error
    EMBEDDING_FAILED = "EMBEDDING_FAILED"  # the embedding model raised an error
    SAVE_FAILED = "SAVE_FAILED"  # writing the result raised an error
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"  # still unreachable after retries
    TASK_CRASHED = "TASK_CRASHED"  # the task died without reporting
