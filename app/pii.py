"""Removing personal data (PII) from text.

The Presidio engines are heavy, so they are created on first use (or earlier,
with warm_up) and then reused.
"""

from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

# The kinds of personal data we look for.
PII_ENTITIES = ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"]


@lru_cache(maxsize=1)
def _get_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    return AnalyzerEngine(), AnonymizerEngine()


def warm_up() -> None:
    """Create the engines now, so the first document is not slow."""
    _get_engines()


def find_pii(text: str) -> list[RecognizerResult]:
    """Find the personal data in a text: what it is and where it sits.

    redact_pii uses exactly this, and so does the quality report, so the report
    measures what the worker really does.
    """
    analyzer, _ = _get_engines()
    results: list[RecognizerResult] = analyzer.analyze(
        text=text, entities=PII_ENTITIES, language="en"
    )
    return results


def redact_pii(text: str) -> str:
    """Return the text with personal data replaced by placeholders like <PERSON>."""
    _, anonymizer = _get_engines()
    analyzer_results = find_pii(text)
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=analyzer_results,
    )
    safe_text: str = anonymized_result.text
    return safe_text
