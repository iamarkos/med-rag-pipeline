"""Removing personal data (PII) from text.

Three sources of evidence are combined:
- a language model (spaCy) that recognises names, places and dates from context;
- Presidio's built-in recognizers for emails and phone numbers;
- our own patterns (app/pii_patterns.py) for formats a clinic uses that these miss.

The Presidio engines are heavy, so they are created on first use (or earlier,
with warm_up) and then reused.
"""

import re
from functools import lru_cache

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

from app.pii_patterns import CUSTOM_RECOGNIZERS, RecognizerSpec

# The language model Presidio uses. It is installed from requirements.txt, so
# nothing is downloaded while the app runs.
SPACY_MODEL = "en_core_web_lg"

# The kinds of personal data we look for. Dates are not kept: they are replaced
# by <DATE_TIME> like everything else.
PII_ENTITIES = [
    "PERSON",
    "LOCATION",
    "DATE_TIME",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "MEDICAL_RECORD_NUMBER",
]

# A name followed by one of these words is a disease, not a person: "Crohn's
# disease", "Hodgkin lymphoma". Hiding it would only make notes harder to read
# and to search.
_MEDICAL_TERM_AFTER_NAME = re.compile(
    r"(?:'s|’s)?[ ]+(?:disease|syndrome|thyroiditis|lymphoma|palsy|phenomenon"
    r"|disorder|sign)\b"
)
# A blood pressure such as 139/95 looks like a phone number to Presidio.
_BLOOD_PRESSURE = re.compile(r"\d{2,3}/\d{2,3}")


def is_known_false_alarm(text: str, result: RecognizerResult) -> bool:
    """True for a finding that is known not to be personal data."""
    if result.entity_type == "PHONE_NUMBER":
        return bool(_BLOOD_PRESSURE.fullmatch(text[result.start : result.end]))
    if result.entity_type == "PERSON":
        return bool(_MEDICAL_TERM_AFTER_NAME.match(text, result.end))
    return False


def _build_recognizer(spec: RecognizerSpec) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=spec.entity,
        name=f"{spec.entity}_patterns",
        patterns=[
            Pattern(name=pattern.name, regex=pattern.regex, score=pattern.score)
            for pattern in spec.patterns
        ],
        context=list(spec.context) or None,
        # Capital letters matter in these patterns (a month name, an upper-case
        # surname), so, unlike Presidio's default, matching is case-sensitive.
        global_regex_flags=re.DOTALL | re.MULTILINE,
    )


def _build_analyzer() -> AnalyzerEngine:
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
        }
    )
    analyzer = AnalyzerEngine(
        nlp_engine=provider.create_engine(), supported_languages=["en"]
    )
    for spec in CUSTOM_RECOGNIZERS:
        analyzer.registry.add_recognizer(_build_recognizer(spec))
    return analyzer


@lru_cache(maxsize=1)
def _get_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    return _build_analyzer(), AnonymizerEngine()


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
    return [result for result in results if not is_known_false_alarm(text, result)]


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
