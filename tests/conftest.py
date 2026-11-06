import os

import pytest

# 1. FORCE THE TEST TO USE THE MAC'S PORT (5433) BEFORE IMPORTING THE APP
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://admin:password@localhost:5433/medical_db"
)

# 2. Now it is safe to import the app
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
