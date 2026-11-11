"""Measures how well redaction hides personal data, using the synthetic corpus.

How each labelled item (a name, a date, a phone number...) is judged:

- HIDDEN:  every letter and digit of it lies inside a span the analyzer found.
           Spaces and punctuation do not need covering. The type the analyzer
           gave does not matter: what counts for privacy is that the text is gone.
- PARTLY:  only some of its letters and digits are covered. The rest leaks, so
           this is a failure, but a different one from a total miss.
- MISSED:  none of it is covered.

Recall = hidden items / all items. "Of the personal data, how much did we hide?"

Each span the analyzer found is CORRECT when it overlaps a labelled item. Any
other span is a FALSE ALARM: text hidden for no reason. Precision = correct
spans / spans found. "Of what we hid, how much really was personal data?"

For privacy, recall matters most: a missed name leaks, a false alarm only costs
a little readability.

Run it alone with `python tests/redaction_report.py`. The real check, with
targets, is tests/test_redaction_quality.py.
"""

import sys
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

EXAMPLE_LIMIT = 5  # examples shown per kind of mistake and type


class Found(NamedTuple):
    """A span of personal data reported by the analyzer."""

    start: int
    end: int
    entity_type: str


@dataclass
class TypeScore:
    items: int = 0  # labelled items of this type in the corpus
    hidden: int = 0
    partly: int = 0
    missed: int = 0
    found: int = 0  # spans the analyzer reported with this type
    correct: int = 0  # ...of which overlap a labelled item

    @property
    def recall(self) -> float | None:
        return self.hidden / self.items if self.items else None

    @property
    def precision(self) -> float | None:
        return self.correct / self.found if self.found else None


@dataclass
class Example:
    note_id: str
    entity_type: str
    what: str  # "missed", "partly hidden" or "false alarm"
    text: str


@dataclass
class Report:
    note_count: int
    scores: dict[str, TypeScore]
    examples: list[Example]

    def total(self) -> TypeScore:
        total = TypeScore()
        for score in self.scores.values():
            total.items += score.items
            total.hidden += score.hidden
            total.partly += score.partly
            total.missed += score.missed
            total.found += score.found
            total.correct += score.correct
        return total


def evaluate(
    notes: Iterable[dict[str, Any]], find: Callable[[str], Iterable[Found]]
) -> Report:
    """Run `find` over every note and compare what it reports with the labels."""
    scores: dict[str, TypeScore] = {}
    examples: list[Example] = []
    shown: Counter[tuple[str, str]] = Counter()

    def add_example(note_id: str, entity_type: str, what: str, text: str) -> None:
        if shown[(what, entity_type)] < EXAMPLE_LIMIT:
            shown[(what, entity_type)] += 1
            examples.append(Example(note_id, entity_type, what, text))

    note_count = 0
    for note in notes:
        note_count += 1
        text = note["text"]
        labels = note["entities"]
        found = list(find(text))
        covered = {
            position for item in found for position in range(item.start, item.end)
        }

        for label in labels:
            score = scores.setdefault(label["type"], TypeScore())
            score.items += 1
            needed = {
                position
                for position in range(label["start"], label["end"])
                if text[position].isalnum()
            }
            reached = needed & covered
            if reached == needed:
                score.hidden += 1
            elif reached:
                score.partly += 1
                add_example(note["id"], label["type"], "partly hidden", label["text"])
            else:
                score.missed += 1
                add_example(note["id"], label["type"], "missed", label["text"])

        for item in found:
            score = scores.setdefault(item.entity_type, TypeScore())
            score.found += 1
            overlaps = any(
                label["start"] < item.end and item.start < label["end"]
                for label in labels
            )
            if overlaps:
                score.correct += 1
            else:
                add_example(
                    note["id"],
                    item.entity_type,
                    "false alarm",
                    text[item.start : item.end],
                )

    return Report(note_count, scores, examples)


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.0%}"


def _row(name: str, score: TypeScore) -> str:
    return (
        f"{name:<24}{score.items:>6}{score.hidden:>8}{score.partly:>8}"
        f"{score.missed:>8}{_percent(score.recall):>8}{score.found:>8}"
        f"{score.correct:>9}{_percent(score.precision):>11}"
    )


def format_report(report: Report) -> str:
    total = report.total()
    header = (
        f"{'Type':<24}{'Items':>6}{'Hidden':>8}{'Partly':>8}{'Missed':>8}"
        f"{'Recall':>8}{'Found':>8}{'Correct':>9}{'Precision':>11}"
    )
    lines = [
        f"Redaction report: {report.note_count} notes, {total.items} labelled items",
        "",
        header,
        "-" * len(header),
    ]
    lines += [_row(name, report.scores[name]) for name in sorted(report.scores)]
    lines += ["-" * len(header), _row("TOTAL", total), ""]

    if report.examples:
        lines.append(f"Examples (up to {EXAMPLE_LIMIT} per kind and type):")
        ordered = sorted(
            report.examples, key=lambda e: (e.what, e.entity_type, e.note_id)
        )
        for example in ordered:
            shortened = (
                example.text if len(example.text) <= 50 else example.text[:47] + "..."
            )
            lines.append(
                f"  {example.note_id}  {example.entity_type:<22} "
                f"{example.what:<14} {shortened!r}"
            )
    return "\n".join(lines)


def main() -> None:
    # Allow `python tests/redaction_report.py` from the project folder.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from synthetic_notes import load_corpus

    from app.pii import find_pii

    print(format_report(evaluate(load_corpus(), find_pii)))


if __name__ == "__main__":
    main()
