"""Generates the synthetic clinical notes used to measure redaction.

Every note is invented. Names, places, dates, numbers and addresses come from
small lists and a seeded random generator, so the same seed always gives the
same notes. While a note is built, the position of every piece of personal data
is recorded, so the answer key ("this part is a PERSON") is exact by
construction and never has to be typed or checked by hand.

Run `python tests/synthetic_notes.py` to rewrite tests/data/synthetic_notes.jsonl.
Real patient data must never be added to this repository.
"""

import json
import random
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Any, TypeVar

SEED = 20261111
NOTE_COUNT = 130
DATA_FILE = Path(__file__).parent / "data" / "synthetic_notes.jsonl"

ENTITY_TYPES = (
    "PERSON",
    "LOCATION",
    "DATE_TIME",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "MEDICAL_RECORD_NUMBER",
)

FIRST_NAMES = [
    "Maria", "John", "Aisha", "Wei", "Olga", "Carlos", "Priya", "Ahmed",
    "Sofia", "Liam", "Fatima", "Dmitri", "Chloe", "Kwame", "Elena", "Hiroshi",
    "Grace", "Mateus", "Nora", "Tariq", "Ingrid", "Rahul", "Beatrice",
    "Samuel", "Yara", "Lukas", "Amara", "Giovanni", "Zoë", "José", "Anika",
    "Pavel", "Hannah", "Omar", "Leila", "Thomas", "Mei", "Daniel", "Ruth",
    "Ibrahim",
]  # fmt: skip
LAST_NAMES = [
    "Rossi", "Smith", "Okafor", "Chen", "Petrova", "Garcia", "Sharma",
    "Hassan", "Costa", "O'Brien", "Khan", "Volkov", "Dubois", "Mensah",
    "Ricci", "Tanaka", "Whitfield", "Silva", "Nowak", "Haddad", "Lindqvist",
    "Patel", "Moretti", "Johnson", "Nasser", "Müller", "Adeyemi", "Bianchi",
    "Kowalski", "Fernandez", "Walker", "Ito", "Larsen", "Mbeki", "Ferrari",
    "Brown", "Yilmaz", "Novak", "Hughes", "Santos",
]  # fmt: skip
CITIES = [
    "Springfield", "Riverton", "Lakewood", "Fairview", "Milan", "Leeds",
    "Toledo", "Bristol", "Austin", "Verona", "Lyon", "Porto", "Dundee",
    "Madison", "Salem", "Glasgow", "Turin", "Denver", "Oxford", "Bergen",
]  # fmt: skip
STREETS = ["Maple", "Oak", "Cedar", "Elm", "Park", "Station", "Church", "Mill"]
STREET_TYPES = ["Street", "Road", "Avenue", "Lane", "Drive"]
RELATIONS = ["wife", "husband", "daughter", "son", "mother", "father", "sister"]
MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]  # fmt: skip

# Medical text with no personal data. Ages and durations are left out on
# purpose, so that every labelled span is clearly personal data.
COMPLAINTS = [
    "chest tightness on exertion",
    "shortness of breath and a dry cough",
    "a swollen left ankle after a fall",
    "persistent headaches and blurred vision",
    "abdominal pain with nausea",
    "fever and fatigue",
    "palpitations and dizziness",
    "lower back pain radiating to the leg",
    "a non-healing wound on the foot",
    "increased thirst and frequent urination",
]
HISTORY = [
    "Symptoms began gradually and have worsened.",
    "There is no history of recent travel.",
    "Past medical history includes hypertension and type 2 diabetes.",
    "Medication has been taken as prescribed.",
    "Symptoms are worse in the evening.",
    "No known drug allergies.",
]
FINDINGS = [
    "Heart sounds are regular with no murmur.",
    "Chest is clear on auscultation.",
    "Mild tenderness in the right lower quadrant.",
    "Swelling and bruising around the joint.",
    "Neurological examination is unremarkable.",
    "Blood glucose is elevated.",
    "ECG shows sinus rhythm.",
    "Chest X-ray shows no acute change.",
]
PLANS = [
    "Start metformin and review in the clinic.",
    "Continue lisinopril and repeat blood tests.",
    "Arrange an echocardiogram.",
    "Advise rest, ice and elevation.",
    "Refer to cardiology for further assessment.",
    "Increase atorvastatin and recheck lipids.",
    "Physiotherapy referral placed.",
    "Discharge with written advice and safety-netting.",
]
# Diseases named after people. They are not personal data, and a redactor may
# wrongly hide them: a deliberate trap for precision.
EPONYMS = [
    "history of Crohn's disease",
    "known Hashimoto's thyroiditis",
    "Raynaud's phenomenon in both hands",
    "previous Bell's palsy",
    "family history of Parkinson's disease",
    "treated for Hodgkin lymphoma in the past",
    "diagnosed with Cushing's syndrome",
]

T = TypeVar("T")


# Only random() is used, because Python promises that its sequence never
# changes between versions. Helpers such as choice() and randrange() may change,
# which would silently alter the notes and break the check that the saved file
# matches the generator.
def _choice(rng: random.Random, options: list[T]) -> T:
    return options[int(rng.random() * len(options))]


def _integer(rng: random.Random, low: int, high: int) -> int:
    """A whole number from low up to, but not including, high."""
    return low + int(rng.random() * (high - low))


class _Note:
    """Builds a note piece by piece and records where each identifier sits."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._entities: list[dict[str, Any]] = []
        self._length = 0

    def text(self, value: str) -> "_Note":
        """Add ordinary text."""
        self._parts.append(value)
        self._length += len(value)
        return self

    def entity(self, entity_type: str, value: str) -> "_Note":
        """Add personal data and record its exact position."""
        start = self._length
        self.text(value)
        self._entities.append(
            {"type": entity_type, "start": start, "end": self._length, "text": value}
        )
        return self

    def build(self, note_id: str, kind: str) -> dict[str, Any]:
        return {
            "id": note_id,
            "kind": kind,
            "text": "".join(self._parts),
            "entities": self._entities,
        }


# --- Small generators for each kind of identifier ---------------------------


def _person(rng: random.Random) -> tuple[str, str]:
    return _choice(rng, FIRST_NAMES), _choice(rng, LAST_NAMES)


def _add_name(
    rng: random.Random, note: _Note, first: str, last: str, style: str | None = None
) -> None:
    """Add a person's name the way a clinician might write it.

    Only the name itself is labelled, not a title such as "Mrs" or "Dr.".
    """
    style = style or _choice(
        rng, ["full", "full", "surname_first", "title_surname", "first_only"]
    )
    if style == "surname_first":
        note.entity("PERSON", f"{last.upper()}, {first}")
    elif style == "title_surname":
        note.text(_choice(rng, ["Mr ", "Ms ", "Mrs "])).entity("PERSON", last)
    elif style == "first_only":
        note.entity("PERSON", first)
    else:
        note.entity("PERSON", f"{first} {last}")


def _add_doctor(rng: random.Random, note: _Note) -> None:
    first, last = _person(rng)
    note.text("Dr. ").entity("PERSON", f"{first} {last}")


def _random_date(rng: random.Random, first_year: int, last_year: int) -> date:
    start = date(first_year, 1, 1)
    days = (date(last_year, 12, 28) - start).days
    return start + timedelta(days=_integer(rng, 0, days))


def _format_date(rng: random.Random, value: date) -> str:
    month = MONTHS[value.month - 1]
    style = _choice(rng, ["long", "day_first", "iso", "us_long"])
    if style == "long":
        return f"{value.day} {month} {value.year}"
    if style == "day_first":
        return f"{value.day:02d}/{value.month:02d}/{value.year}"
    if style == "iso":
        return value.isoformat()
    return f"{month} {value.day}, {value.year}"


def _phone(rng: random.Random) -> str:
    # Numbers from ranges reserved for fiction, so none belongs to a real person.
    style = _choice(rng, ["us", "uk", "short"])
    if style == "us":
        return f"({_choice(rng, [212, 415, 617])}) 555-01{_integer(rng, 0, 100):02d}"
    if style == "uk":
        return f"+44 20 7946 0{_integer(rng, 0, 1000):03d}"
    return f"555-01{_integer(rng, 0, 100):02d}"


def _email(rng: random.Random, first: str, last: str) -> str:
    # example.org is reserved for examples: it can never be a real mailbox.
    plain = unicodedata.normalize("NFKD", f"{first}.{last}").encode("ascii", "ignore")
    local = plain.decode().lower().replace("'", "")
    return f"{local}@example.org"


def _medical_record_number(rng: random.Random) -> str:
    style = _choice(rng, ["digits", "letter", "padded"])
    if style == "digits":
        return str(_integer(rng, 1_000_000, 9_999_999))
    if style == "letter":
        return f"A-{_integer(rng, 100_000, 999_999)}"
    return f"00{_integer(rng, 100_000, 999_999)}"


def _address(rng: random.Random) -> str:
    street = (
        f"{_integer(rng, 1, 200)} {_choice(rng, STREETS)} {_choice(rng, STREET_TYPES)}"
    )
    return f"{street}, {_choice(rng, CITIES)}"


def _vitals(rng: random.Random) -> str:
    # Numbers that look a little like dates or phone numbers: a precision trap.
    return (
        f"BP {_integer(rng, 105, 170)}/{_integer(rng, 60, 100)} mmHg, "
        f"pulse {_integer(rng, 55, 120)} bpm, "
        f"temperature {36.0 + rng.random() * 3.5:.1f} C."
    )


# --- One function per kind of note ------------------------------------------


def _admission_note(rng: random.Random, note: _Note) -> None:
    first, last = _person(rng)
    note.text("ADMISSION NOTE\n\nPatient: ")
    _add_name(rng, note, first, last, _choice(rng, ["full", "surname_first"]))
    note.text("\nDOB: ").entity(
        "DATE_TIME", _format_date(rng, _random_date(rng, 1935, 2005))
    )
    note.text("   MRN: ").entity("MEDICAL_RECORD_NUMBER", _medical_record_number(rng))
    note.text("\nAddress: ").entity("LOCATION", _address(rng))
    note.text("\nPhone: ").entity("PHONE_NUMBER", _phone(rng))
    note.text("\nDate of admission: ")
    note.entity("DATE_TIME", _format_date(rng, _random_date(rng, 2023, 2026)))
    note.text("\n\nHistory of present illness:\n")
    _add_name(rng, note, first, last, _choice(rng, ["title_surname", "first_only"]))
    note.text(f" presented with {_choice(rng, COMPLAINTS)}. {_choice(rng, HISTORY)} ")
    note.text(f"Background: {_choice(rng, EPONYMS)}. {_vitals(rng)}")
    note.text(f"\n\nExamination: {_choice(rng, FINDINGS)} {_choice(rng, FINDINGS)}")
    note.text(f"\n\nPlan: {_choice(rng, PLANS)}\n\nSigned: ")
    _add_doctor(rng, note)
    note.text("\n")


def _progress_note(rng: random.Random, note: _Note) -> None:
    first, last = _person(rng)
    note.text("PROGRESS NOTE - ")
    note.entity("DATE_TIME", _format_date(rng, _random_date(rng, 2023, 2026)))
    note.text("\nSeen by ")
    _add_doctor(rng, note)
    note.text(".\n\n")
    _add_name(
        rng, note, first, last, _choice(rng, ["title_surname", "first_only", "full"])
    )
    note.text(f" reports {_choice(rng, COMPLAINTS)}. {_choice(rng, FINDINGS)} ")
    note.text(
        f"{_choice(rng, HISTORY)}\n\nSpoke with the patient's {_choice(rng, RELATIONS)}, "
    )
    _add_name(rng, note, *_person(rng), style="full")
    note.text(", phone ").entity("PHONE_NUMBER", _phone(rng))
    note.text(f".\n\nPlan: {_choice(rng, PLANS)}\n")


def _referral_letter(rng: random.Random, note: _Note) -> None:
    first, last = _person(rng)
    note.entity("LOCATION", _address(rng))
    note.text("\n").entity(
        "DATE_TIME", _format_date(rng, _random_date(rng, 2023, 2026))
    )
    note.text("\n\nDear ")
    _add_doctor(rng, note)
    note.text(",\n\nI am writing to refer my patient ")
    _add_name(rng, note, first, last, "full")
    note.text(" (DOB ").entity(
        "DATE_TIME", _format_date(rng, _random_date(rng, 1935, 2005))
    )
    note.text(", MRN ").entity("MEDICAL_RECORD_NUMBER", _medical_record_number(rng))
    note.text("), who lives at ").entity("LOCATION", _address(rng))
    note.text(f". The patient presented with {_choice(rng, COMPLAINTS)}. ")
    note.text(f"{_choice(rng, HISTORY)} I would be grateful for your assessment.")
    doctor_first, doctor_last = _person(rng)
    note.text("\n\nYou can reach me on ").entity("PHONE_NUMBER", _phone(rng))
    note.text(" or at ").entity("EMAIL_ADDRESS", _email(rng, doctor_first, doctor_last))
    note.text(".\n\nYours sincerely,\nDr. ")
    note.entity("PERSON", f"{doctor_first} {doctor_last}").text("\n")


def _discharge_summary(rng: random.Random, note: _Note) -> None:
    first, last = _person(rng)
    admitted = _random_date(rng, 2023, 2026)
    discharged = admitted + timedelta(days=_integer(rng, 1, 12))
    follow_up = discharged + timedelta(days=_integer(rng, 7, 40))
    city = _choice(rng, CITIES)
    note.text("DISCHARGE SUMMARY\n\nPatient: ")
    _add_name(rng, note, first, last, "full")
    note.text("   MRN: ").entity("MEDICAL_RECORD_NUMBER", _medical_record_number(rng))
    note.text("\nAdmitted: ").entity("DATE_TIME", _format_date(rng, admitted))
    note.text("   Discharged: ").entity("DATE_TIME", _format_date(rng, discharged))
    note.text("\nHome: ").entity("LOCATION", city)
    note.text(f", lives with the patient's {_choice(rng, RELATIONS)}, ")
    _add_name(rng, note, *_person(rng), style="full")
    note.text(
        f".\n\nDiagnosis: {_choice(rng, EPONYMS)}; admitted with {_choice(rng, COMPLAINTS)}."
    )
    note.text(f"\nCourse: {_choice(rng, FINDINGS)} {_choice(rng, PLANS)}")
    note.text("\n\nFollow-up: appointment on ")
    note.entity("DATE_TIME", _format_date(rng, follow_up)).text(" with ")
    _add_doctor(rng, note)
    note.text(" at the ").entity("LOCATION", _choice(rng, CITIES)).text(" clinic.\n")


def _telephone_note(rng: random.Random, note: _Note) -> None:
    caller_first, caller_last = _person(rng)
    patient_first, patient_last = _person(rng)
    note.text("TELEPHONE ENCOUNTER ")
    note.entity("DATE_TIME", _format_date(rng, _random_date(rng, 2023, 2026)))
    note.text("\nCaller: ")
    _add_name(rng, note, caller_first, caller_last, "full")
    note.text(f", {_choice(rng, RELATIONS)} of ")
    _add_name(rng, note, patient_first, patient_last, "surname_first")
    note.text("\nPhone: ").entity("PHONE_NUMBER", _phone(rng))
    note.text("   Email: ")
    note.entity("EMAIL_ADDRESS", _email(rng, caller_first, caller_last))
    note.text(f"\n\nThe caller asked about {_choice(rng, COMPLAINTS)}. ")
    note.text(f"{_choice(rng, PLANS)} Callback arranged for ")
    note.entity("DATE_TIME", _format_date(rng, _random_date(rng, 2023, 2026))).text(
        ".\n"
    )


def _clinical_only_note(rng: random.Random, note: _Note) -> None:
    # No personal data at all: anything a redactor hides here is a mistake.
    note.text(f"CLINIC NOTE\n\nBackground: {_choice(rng, EPONYMS)}. ")
    note.text(f"Presents with {_choice(rng, COMPLAINTS)}. {_choice(rng, HISTORY)} ")
    note.text(f"{_vitals(rng)}\n\nExamination: {_choice(rng, FINDINGS)} ")
    note.text(f"{_choice(rng, FINDINGS)}\n\nPlan: {_choice(rng, PLANS)}\n")


NOTE_KINDS = {
    "admission": _admission_note,
    "progress": _progress_note,
    "referral": _referral_letter,
    "discharge": _discharge_summary,
    "telephone": _telephone_note,
    "clinical_only": _clinical_only_note,
}


def generate_corpus(count: int = NOTE_COUNT, seed: int = SEED) -> list[dict[str, Any]]:
    """Make `count` notes. The same seed always gives the same notes."""
    rng = random.Random(seed)
    kinds = list(NOTE_KINDS)
    notes = []
    for index in range(count):
        kind = kinds[index % len(kinds)]
        note = _Note()
        NOTE_KINDS[kind](rng, note)
        notes.append(note.build(f"note-{index + 1:03d}", kind))
    return notes


def write_corpus(path: Path = DATA_FILE) -> None:
    lines = [json.dumps(note, ensure_ascii=False) for note in generate_corpus()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_corpus(path: Path = DATA_FILE) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


if __name__ == "__main__":
    write_corpus()
    print(f"Wrote {NOTE_COUNT} notes to {DATA_FILE}")
