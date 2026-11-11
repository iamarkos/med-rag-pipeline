"""Tests for the synthetic corpus (tests/synthetic_notes.py).

The corpus is only useful as an answer key if the answers are exact, so these
tests check the labels themselves.
"""

from collections import Counter

from synthetic_notes import ENTITY_TYPES, generate_corpus, load_corpus


def test_the_corpus_has_at_least_100_notes():
    assert len(load_corpus()) >= 100


def test_every_label_points_at_exactly_its_text():
    for note in load_corpus():
        for entity in note["entities"]:
            assert note["text"][entity["start"] : entity["end"]] == entity["text"]


def test_labels_have_known_types_and_do_not_overlap():
    for note in load_corpus():
        previous_end = 0
        for entity in note["entities"]:
            assert entity["type"] in ENTITY_TYPES
            assert entity["start"] >= previous_end
            previous_end = entity["end"]


def test_every_type_appears_often_enough_to_measure():
    counts = Counter(
        entity["type"] for note in load_corpus() for entity in note["entities"]
    )

    for entity_type in ENTITY_TYPES:
        assert counts[entity_type] >= 20, entity_type


def test_some_notes_contain_no_personal_data():
    # They show what a redactor hides by mistake.
    notes = load_corpus()

    assert sum(1 for note in notes if not note["entities"]) >= 10


def test_all_email_addresses_use_the_reserved_example_domain():
    for note in load_corpus():
        for entity in note["entities"]:
            if entity["type"] == "EMAIL_ADDRESS":
                assert entity["text"].endswith("@example.org")


def test_the_saved_file_matches_the_generator():
    # If this fails, the generator changed: run `python tests/synthetic_notes.py`.
    assert load_corpus() == generate_corpus()
