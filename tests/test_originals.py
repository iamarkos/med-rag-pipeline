"""Tests for keeping originals and handing them back (app/original_store.py)."""

from unittest.mock import patch

import pytest

from app.original_store import LocalFolderStore
from app.status import DocumentStatus

NOTE = b"John Smith has chest pain."


@pytest.fixture
def store(tmp_path):
    return LocalFolderStore(tmp_path)


@pytest.mark.parametrize("content_type", ["text/plain", "text/csv", "application/pdf"])
def test_an_original_comes_back_exactly_as_saved(store, content_type):
    store.save("src-abc123", NOTE, content_type)

    original = store.load("src-abc123")

    assert original is not None
    assert original.content == NOTE
    assert original.content_type == content_type


def test_an_unknown_reference_gives_nothing(store):
    assert store.load("src-missing") is None


def test_deleting_removes_the_original_and_is_safe_to_repeat(store):
    store.save("src-abc123", NOTE, "text/plain")

    store.delete("src-abc123")
    store.delete("src-abc123")

    assert store.load("src-abc123") is None


@pytest.mark.parametrize("bad_reference", ["../outside", "folder/file", ""])
def test_a_reference_that_could_escape_the_folder_is_refused(store, bad_reference):
    with pytest.raises(ValueError):
        store.save(bad_reference, NOTE, "text/plain")
    with pytest.raises(ValueError):
        store.load(bad_reference)


def test_an_unsupported_type_is_refused(store):
    with pytest.raises(ValueError):
        store.save("src-abc123", NOTE, "text/html")


def _upload(client, content=NOTE):
    files = {"file": ("note.txt", content, "text/plain")}
    with patch("app.main.celery_app.send_task") as mock_celery_task:
        mock_celery_task.return_value.id = "test-task-uuid"
        return client.post("/upload", files=files, data={"patient_ref": "P-0042"})


def test_an_uploaded_original_can_be_opened_from_its_document_id(client):
    upload = _upload(client).json()

    response = client.get(f"/documents/{upload['database_id']}/original")

    assert response.status_code == 200
    assert response.content == NOTE  # the real text, not the redacted copy
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "no-store"


def test_opening_the_original_of_an_unknown_document_gives_404(client):
    assert client.get("/documents/2147483647/original").status_code == 404


def test_a_document_without_a_stored_original_gives_404(client, add_document):
    document_id = add_document(DocumentStatus.COMPLETED)

    assert client.get(f"/documents/{document_id}/original").status_code == 404


def test_no_file_is_left_behind_when_the_database_save_fails(client, originals_dir):
    with (
        patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        _upload(client)

    assert list(originals_dir.iterdir()) == []
