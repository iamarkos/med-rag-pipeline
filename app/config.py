import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Return an environment variable, or stop with a message."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


DATABASE_URL = _require("DATABASE_URL")
REDIS_URL = _require("REDIS_URL")


def get_text_encryption_key() -> str:
    """The key that protects document text while it waits in the queue.

    Read when it is needed, not when this module loads, so tools that never
    handle document text (such as the database migrations) do not need it.
    """
    return _require("TEXT_ENCRYPTION_KEY")


def get_originals_dir() -> str:
    """The folder where uploaded originals are kept (the demo's original store).

    Read when it is needed, not when this module loads, so tools that never
    touch originals (such as the database migrations) do not need it.
    """
    return _require("ORIGINALS_DIR")
