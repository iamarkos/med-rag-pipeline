"""Tests for /search, using hand-made vectors instead of a real model.

A unit vector along axis 0 and one along axis 1 are completely unrelated, and a
vector is closest to itself. That is enough to check how documents are ranked
and filtered, with no model involved.
"""

from app.status import DocumentStatus


def _unit_vector(axis: int) -> list[float]:
    vector = [0.0] * 384
    vector[axis] = 1.0
    return vector


def _search(client, monkeypatch, query_vector):
    # The API turns the question into a vector; here we choose that vector.
    monkeypatch.setattr("app.main.embed_text", lambda query: query_vector)
    return client.get("/search", params={"query": "any question"})


def test_the_closest_document_comes_first(client, add_document, monkeypatch):
    add_document(DocumentStatus.COMPLETED, _unit_vector(1), "far.txt")
    close = add_document(DocumentStatus.COMPLETED, _unit_vector(0), "close.txt")

    response = _search(client, monkeypatch, _unit_vector(0))

    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["id"] == close
    assert results[0]["filename"] == "close.txt"


def test_only_completed_documents_with_a_vector_are_returned(
    client, add_document, monkeypatch
):
    vector = _unit_vector(0)
    searchable = add_document(DocumentStatus.COMPLETED, vector)
    add_document(DocumentStatus.PROCESSING, vector)
    add_document(DocumentStatus.FAILED, vector)
    add_document(DocumentStatus.COMPLETED, None)

    response = _search(client, monkeypatch, vector)

    assert [r["id"] for r in response.json()["results"]] == [searchable]


def test_at_most_three_results_are_returned(client, add_document, monkeypatch):
    for axis in range(5):
        add_document(DocumentStatus.COMPLETED, _unit_vector(axis))

    response = _search(client, monkeypatch, _unit_vector(0))

    assert len(response.json()["results"]) == 3


def test_an_empty_database_returns_no_results(client, monkeypatch):
    response = _search(client, monkeypatch, _unit_vector(0))

    assert response.status_code == 200
    assert response.json()["results"] == []
