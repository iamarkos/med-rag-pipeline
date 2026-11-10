"""Test setup: a dedicated database, so tests never touch your development data.

How it works:
1. TEST_DATABASE_URL (from .env, or from CI) names a database whose name ends
   in "_test".
2. DATABASE_URL is pointed at it, and a temporary encryption key is created,
   before the app is imported. The app under test only ever sees the test
   database and the temporary key.
3. At the start of the run, the database is created if it is missing and
   brought up to date with the Alembic migrations (so the migrations are
   tested too).
4. Every test starts and ends with empty tables.

The app itself is imported inside the fixtures below (and by the test modules),
never at the top of this file, so that step 2 always happens first.
"""

import itertools
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from alembic.config import Config
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def database_name(url: str) -> str:
    """The database part of a connection URL."""
    return urlsplit(url).path.lstrip("/")


def server_url(url: str) -> str:
    """The same server, but its built-in 'postgres' database.

    We connect there to create the test database, because a database cannot be
    created from inside itself.
    """
    return urlunsplit(urlsplit(url)._replace(path="/postgres"))


def _require_test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set. Add it to your .env file (see .env.example)."
        )
    # Safety net: the tests empty every table, so refuse anything that does not
    # look like a test database (for example, by mistake, your development one).
    if not re.fullmatch(r"[A-Za-z0-9_]+_test", database_name(url)):
        raise RuntimeError(
            "TEST_DATABASE_URL must point to a database whose name ends in '_test'."
        )
    return url


TEST_DATABASE_URL = _require_test_database_url()

# The app reads DATABASE_URL when it is first imported, so this comes first.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Tests get their own throwaway encryption key, so they never depend on (or
# touch) the real one in your .env.
os.environ["TEXT_ENCRYPTION_KEY"] = Fernet.generate_key().decode()


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Create the test database if needed and migrate it to the latest version."""
    name = database_name(TEST_DATABASE_URL)
    admin_engine = create_engine(
        server_url(TEST_DATABASE_URL), isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    admin_engine.dispose()

    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    # Alembic would otherwise reconfigure Python's logging inside the test run.
    alembic_config.attributes["configure_logger"] = False
    command.upgrade(alembic_config, "head")


def _empty_all_tables():
    from app.database import Base, engine

    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def _clean_tables(_test_database):
    """Empty tables before and after every test, so tests cannot affect each other."""
    _empty_all_tables()
    yield
    _empty_all_tables()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    """A database session, for arranging test data and reading results back."""
    from app.database import SessionLocal

    with SessionLocal() as session:
        yield session


@pytest.fixture
def add_document(db):
    """Returns a function that saves a document (by default with a new patient).

    The function returns the new document's id. All data is synthetic.
    """
    from app.models import ClinicalDocument, Patient
    from app.status import DocumentStatus

    references = itertools.count(1)

    def _add(
        status=DocumentStatus.PENDING,
        embedding=None,
        filename="note.txt",
        patient_ref=None,
    ):
        patient = Patient(patient_ref=patient_ref or f"P-{next(references):04d}")
        document = ClinicalDocument(
            filename=filename,
            status=status,
            embedding=embedding,
            patient=patient,
        )
        db.add_all([patient, document])
        db.commit()
        return document.id

    return _add
