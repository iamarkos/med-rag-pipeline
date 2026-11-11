"""Tests for the measuring tool itself (tests/redaction_report.py).

The tool decides whether redaction passes, so it must be right. These tests use
tiny hand-made notes and a pretend analyzer, with no models.
"""

from redaction_report import EXAMPLE_LIMIT, Found, evaluate, format_report

TEXT = "Maria Rossi called"


def _note(text, *labels, note_id="n1"):
    entities = []
    for entity_type, value in labels:
        start = text.index(value)
        entities.append(
            {
                "type": entity_type,
                "start": start,
                "end": start + len(value),
                "text": value,
            }
        )
    return {"id": note_id, "text": text, "entities": entities}


def _run(found, text=TEXT, labels=(("PERSON", "Maria Rossi"),)):
    return evaluate([_note(text, *labels)], lambda _text: found)


def test_an_item_that_is_fully_covered_is_hidden():
    score = _run([Found(0, 11, "PERSON")]).scores["PERSON"]

    assert (score.items, score.hidden, score.partly, score.missed) == (1, 1, 0, 0)
    assert score.recall == 1.0


def test_an_item_that_is_only_partly_covered_is_a_leak():
    report = _run([Found(0, 5, "PERSON")])
    score = report.scores["PERSON"]

    assert (score.hidden, score.partly, score.missed) == (0, 1, 0)
    assert score.recall == 0.0
    assert report.examples[0].what == "partly hidden"


def test_an_item_with_no_cover_is_missed():
    report = _run([])
    score = report.scores["PERSON"]

    assert (score.hidden, score.partly, score.missed) == (0, 0, 1)
    assert report.examples[0].what == "missed"
    assert report.examples[0].text == "Maria Rossi"


def test_text_that_is_hidden_counts_even_under_another_type():
    report = _run([Found(0, 11, "LOCATION")])

    assert report.scores["PERSON"].hidden == 1
    assert report.scores["LOCATION"].found == 1
    assert report.scores["LOCATION"].correct == 1


def test_spaces_and_punctuation_do_not_need_covering():
    text = "Phone: (415) 555-0161 today"
    first_digit = text.index("415")
    last_digit_end = text.index(" today")

    report = _run(
        [Found(first_digit, last_digit_end, "PHONE_NUMBER")],
        text=text,
        labels=(("PHONE_NUMBER", "(415) 555-0161"),),
    )

    assert report.scores["PHONE_NUMBER"].hidden == 1


def test_a_span_over_ordinary_text_is_a_false_alarm():
    report = _run([Found(0, 5, "PERSON")], text="Crohn's disease noted", labels=())
    score = report.scores["PERSON"]

    assert (score.found, score.correct, score.precision) == (1, 0, 0.0)
    assert score.recall is None  # no labelled items, so recall does not apply
    assert report.examples[0].what == "false alarm"
    assert report.examples[0].text == "Crohn"


def test_only_a_few_examples_are_kept_per_kind_of_mistake():
    notes = [_note(TEXT, ("PERSON", "Maria Rossi"), note_id=f"n{i}") for i in range(10)]

    report = evaluate(notes, lambda _text: [])

    assert report.scores["PERSON"].missed == 10
    assert len(report.examples) == EXAMPLE_LIMIT


def test_the_printed_report_shows_each_type_and_the_total():
    printed = format_report(_run([Found(0, 11, "PERSON")]))

    assert "PERSON" in printed
    assert "TOTAL" in printed
    assert "100%" in printed
