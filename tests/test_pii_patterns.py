"""Tests for our own patterns (app/pii_patterns.py).

They run with plain regular expressions, so they need no Presidio and no model.
"""

import re

import pytest
from redaction_report import Found, evaluate
from synthetic_notes import load_corpus

from app.pii_patterns import CUSTOM_RECOGNIZERS

# The same flags app/pii.py gives Presidio.
FLAGS = re.DOTALL | re.MULTILINE
COMPILED = [
    (recognizer.entity, re.compile(pattern.regex, FLAGS))
    for recognizer in CUSTOM_RECOGNIZERS
    for pattern in recognizer.patterns
]


def find_by_patterns(text):
    return [
        Found(match.start(), match.end(), entity)
        for entity, regex in COMPILED
        for match in regex.finditer(text)
    ]


def _matches(entity, text):
    return [
        text[f.start : f.end] for f in find_by_patterns(text) if f.entity_type == entity
    ]


@pytest.mark.parametrize(
    ("entity", "text", "expected"),
    [
        ("DATE_TIME", "Seen on 2024-03-12 by", "2024-03-12"),
        ("DATE_TIME", "DOB 03/12/1961 ok", "03/12/1961"),
        ("DATE_TIME", "admitted on 5 March 2024.", "5 March 2024"),
        ("DATE_TIME", "admitted March 5, 2024.", "March 5, 2024"),
        ("MEDICAL_RECORD_NUMBER", "MRN: A-482193 on", "A-482193"),
        ("MEDICAL_RECORD_NUMBER", "MRN 4827193,", "4827193"),
        ("MEDICAL_RECORD_NUMBER", "MRN: 00482193", "00482193"),
        ("LOCATION", "lives at 167 Oak Road, Lakewood. The", "167 Oak Road, Lakewood"),
        ("LOCATION", "Address: 42 Mill Lane\nPhone: 555-0182", "42 Mill Lane"),
        ("LOCATION", "at 9 O'Brien Street, Leeds", "9 O'Brien Street, Leeds"),
        ("PERSON", "Patient: ROSSI, Maria\nDOB", "ROSSI, Maria"),
        ("PERSON", "Patient: MÜLLER, Zoë\nDOB", "MÜLLER, Zoë"),
        ("PERSON", "Patient: O'BRIEN, John\nDOB", "O'BRIEN, John"),
        ("PHONE_NUMBER", "Phone: 555-0182", "555-0182"),
    ],
)
def test_a_pattern_finds_the_format_it_was_written_for(entity, text, expected):
    assert expected in _matches(entity, text)


@pytest.mark.parametrize(
    "text",
    [
        "BP 139/95 mmHg, pulse 80 bpm, temperature 36.3 C.",
        "The pain started in 2024.",
        "Take 500 mg twice daily.",
        "Result 12345 units.",
        "CLINIC NOTE\n\nBackground: previous Bell's palsy.",
        "Plan: start metformin, review in the clinic.",
    ],
)
def test_ordinary_clinical_text_is_left_alone(text):
    assert find_by_patterns(text) == []


def _only(notes, entity_type, keep):
    """The corpus, keeping only the labels of one type that satisfy `keep`."""
    return [
        {
            **note,
            "entities": [
                e
                for e in note["entities"]
                if e["type"] == entity_type and keep(e["text"])
            ],
        }
        for note in load_corpus()
    ]


@pytest.mark.parametrize(
    ("entity_type", "keep"),
    [
        ("DATE_TIME", lambda text: True),
        ("MEDICAL_RECORD_NUMBER", lambda text: True),
        ("LOCATION", lambda text: any(c.isdigit() for c in text)),  # street addresses
        ("PERSON", lambda text: "," in text),  # "ROSSI, Maria"
        ("PHONE_NUMBER", lambda text: re.fullmatch(r"\d{3}-\d{4}", text) is not None),
    ],
)
def test_the_patterns_hide_the_formats_they_target_in_the_corpus(entity_type, keep):
    labelled = _only(load_corpus(), entity_type, keep)

    score = evaluate(labelled, find_by_patterns).scores[entity_type]

    assert score.items > 20
    assert score.recall >= 0.95


def test_the_patterns_raise_no_false_alarms_on_the_corpus():
    report = evaluate(load_corpus(), find_by_patterns)

    for entity_type, score in report.scores.items():
        assert score.precision in (None, 1.0), entity_type


def test_notes_without_personal_data_produce_no_matches():
    clean = [note for note in load_corpus() if note["kind"] == "clinical_only"]

    assert clean
    assert all(find_by_patterns(note["text"]) == [] for note in clean)
