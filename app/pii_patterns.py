"""Patterns for personal data that Presidio's built-in recognizers do not find.

Presidio finds names, places and dates with a language model, and a few kinds
(emails, many phone numbers) with patterns. It does not know the formats a clinic
uses: record numbers, street addresses, phone numbers without an area code,
numeric dates, or names written "SURNAME, First". Those are described here as
plain regular expressions.

These formats come from the synthetic corpus (tests/synthetic_notes.py). A real
hospital writes its own formats, so replace them with that hospital's before any
real use. Without that, a good score on the corpus says little.

This module has no Presidio import, so the patterns can be tested without it.
"""

from dataclasses import dataclass

# Letters beyond A-Z (such as the ü in Müller or the ë in Zoë), so that names
# with accents are matched whole.
UPPER = "A-ZÀ-ÖØ-Þ"
LOWER = "a-zß-öø-ÿ"
NAME_WORD = rf"[{UPPER}][{UPPER}{LOWER}'’-]*"

MONTH = (
    "(?:January|February|March|April|May|June|July|August|September|October"
    "|November|December)"
)
STREET_TYPE = (
    "(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct"
    "|Way|Place|Close|Terrace)"
)


@dataclass(frozen=True)
class PatternSpec:
    name: str
    regex: str
    score: float  # how sure we are, from 0 to 1, when only the pattern matches


@dataclass(frozen=True)
class RecognizerSpec:
    entity: str  # the kind of personal data these patterns find
    patterns: tuple[PatternSpec, ...]
    # Words that, when they appear just before a match, make Presidio more sure.
    context: tuple[str, ...] = ()


CUSTOM_RECOGNIZERS: tuple[RecognizerSpec, ...] = (
    RecognizerSpec(
        entity="DATE_TIME",
        patterns=(
            PatternSpec("iso_date", r"\b\d{4}-\d{2}-\d{2}\b", 0.85),
            PatternSpec("numeric_date", r"\b\d{1,2}/\d{1,2}/\d{4}\b", 0.85),
            PatternSpec(
                "day_month_year", rf"\b\d{{1,2}}[ ]+{MONTH}[ ]+\d{{4}}\b", 0.85
            ),
            PatternSpec(
                "month_day_year", rf"\b{MONTH}[ ]+\d{{1,2}},[ ]+\d{{4}}\b", 0.85
            ),
        ),
    ),
    RecognizerSpec(
        entity="MEDICAL_RECORD_NUMBER",
        patterns=(
            # A letter prefix, such as A-482193.
            PatternSpec("prefixed_number", r"\b[A-Z]{1,3}-\d{5,9}\b", 0.6),
            # Plain digits are weak evidence alone, so the label before them
            # (MRN, medical record, ...) is what raises the score.
            PatternSpec("plain_number", r"\b\d{6,10}\b", 0.3),
        ),
        context=("mrn", "medical", "record", "patient", "id"),
    ),
    RecognizerSpec(
        entity="LOCATION",
        patterns=(
            # "167 Oak Road, Lakewood": number, street name, street type and
            # an optional city. Spaces only, so a match never runs onto the
            # next line.
            PatternSpec(
                "street_address",
                rf"\b\d{{1,5}}[ ]+(?:{NAME_WORD}[ ]+){{1,3}}{STREET_TYPE}\b\.?"
                rf"(?:,[ ]+{NAME_WORD}(?:[ ]+{NAME_WORD})?)?",
                0.85,
            ),
        ),
    ),
    RecognizerSpec(
        entity="PERSON",
        patterns=(
            # "ROSSI, Maria": a capitalised-letters surname confuses the
            # language model, so this form gets its own pattern.
            PatternSpec(
                "surname_comma_first",
                rf"\b[{UPPER}][{UPPER}'’-]{{2,}},[ ]+[{UPPER}][{LOWER}]+"
                rf"(?:-[{UPPER}][{LOWER}]+)?\b",
                0.6,
            ),
        ),
    ),
    RecognizerSpec(
        entity="PHONE_NUMBER",
        patterns=(
            # A local number without an area code, such as 555-0182, which
            # Presidio cannot check and so skips.
            PatternSpec("local_number", r"\b\d{3}-\d{4}\b", 0.4),
        ),
        context=("phone", "tel", "telephone", "call", "mobile", "contact"),
    ),
)
