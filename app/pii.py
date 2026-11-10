"""Removing personal data (PII) from text.

The Presidio engines are heavy, so they are created on first use (or earlier,
with warm_up) and then reused.
"""

from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

# The kinds of personal data we look for.
PII_ENTITIES = ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"]


@lru_cache(maxsize=1)
def _get_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    return AnalyzerEngine(), AnonymizerEngine()


def warm_up() -> None:
    """Create the engines now, so the first document is not slow."""
    _get_engines()


def redact_pii(text: str) -> str:
    """Return the text with personal data replaced by placeholders like <PERSON>."""
    analyzer, anonymizer = _get_engines()
    analyzer_results = analyzer.analyze(text=text, entities=PII_ENTITIES, language="en")
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=analyzer_results,
    )
    safe_text: str = anonymized_result.text
    return safe_text
