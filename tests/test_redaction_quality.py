"""The redaction quality check: fails if redaction gets worse than the targets.

It runs the real analyzer (the real models), so it is skipped in a normal
`pytest`. Run it on purpose with:

    pytest -m redaction -s

CI runs it too. The -s shows the full table.
"""

import pytest
from redaction_report import evaluate, format_report
from synthetic_notes import load_corpus

# The lowest recall accepted for each type: the share of personal data that must
# be hidden. Set from the first measurement; raise as redaction improves.
# Set each value to the recall you saw, rounded down to the nearest 5%.
MINIMUM_RECALL = {
    "PERSON": 0.90,
    "LOCATION": 0.25,
    "DATE_TIME": 0.0,
    "PHONE_NUMBER": 0.60,
    "EMAIL_ADDRESS": 1.0,
    "MEDICAL_RECORD_NUMBER": 0.05,
}


@pytest.mark.redaction
def test_redaction_recall_meets_the_targets():
    from app.pii import find_pii

    report = evaluate(load_corpus(), find_pii)
    print("\n" + format_report(report))

    too_low = {
        entity_type: report.scores[entity_type].recall
        for entity_type, minimum in MINIMUM_RECALL.items()
        if (report.scores[entity_type].recall or 0.0) < minimum
    }
    assert not too_low, f"Recall is below the target for: {too_low}"
