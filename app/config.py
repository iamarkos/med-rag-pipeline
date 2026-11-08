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
