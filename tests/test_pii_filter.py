"""Tests for the filter that drops known false alarms (app/pii.py)."""

from types import SimpleNamespace

import pytest

from app.pii import is_known_false_alarm


def _result(entity_type, text, span):
    start = text.index(span)
    return SimpleNamespace(entity_type=entity_type, start=start, end=start + len(span))


@pytest.mark.parametrize(
    ("entity_type", "text", "span", "expected"),
    [
        ("PHONE_NUMBER", "BP 169/72 mmHg", "169/72", True),
        ("PHONE_NUMBER", "Phone: 555-0182", "555-0182", False),
        ("PHONE_NUMBER", "Phone: (415) 555-0161", "(415) 555-0161", False),
        ("PERSON", "Background: Crohn's disease.", "Crohn", True),
        ("PERSON", "known Hashimoto\u2019s thyroiditis", "Hashimoto", True),
        ("PERSON", "treated for Hodgkin lymphoma", "Hodgkin", True),
        ("PERSON", "previous Bell's palsy", "Bell", True),
        ("PERSON", "Maria reports chest pain", "Maria", False),
        ("PERSON", "Spoke with Maria's daughter", "Maria", False),
        ("LOCATION", "lives in Leeds", "Leeds", False),
    ],
)
def test_only_known_false_alarms_are_dropped(entity_type, text, span, expected):
    assert is_known_false_alarm(text, _result(entity_type, text, span)) is expected
