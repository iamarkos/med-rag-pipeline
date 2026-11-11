# Synthetic clinical notes

`synthetic_notes.jsonl` holds 130 invented notes with an answer key. It is used
to measure how well redaction finds personal data. **Everything here is
invented. Never add real patient data to this repository.**

## Format

One JSON object per line:

```json
{
  "id": "note-001",
  "kind": "admission",
  "text": "Patient: SILVA, Zoë\nDOB: January 16, 1949 ...",
  "entities": [
    {"type": "PERSON", "start": 9, "end": 19, "text": "SILVA, Zoë"}
  ]
}
```

`start` and `end` are character positions in `text`, so
`text[start:end] == entity["text"]`.

## What is labelled

| Type | Examples |
| --- | --- |
| `PERSON` | `Maria Rossi`, `ROSSI, Maria`, the `Okafor` in `Mrs Okafor`, the name after `Dr.` |
| `LOCATION` | a city (`Leeds`) or a street address (`167 Oak Road, Lakewood`) |
| `DATE_TIME` | birth, admission, discharge and appointment dates, in four formats |
| `PHONE_NUMBER` | numbers from ranges reserved for fiction |
| `EMAIL_ADDRESS` | always `@example.org`, a domain reserved for examples |
| `MEDICAL_RECORD_NUMBER` | `4827193`, `A-482193`, `00482193` |

Titles (`Dr.`, `Mrs`) are not part of a `PERSON` label. Ages and durations
("three days") are left out of the notes, so that every label is clearly
personal data. About one note in six contains no personal data at all, and some
notes contain things a redactor may wrongly hide: diseases named after people
(`Crohn's disease`) and vital signs (`BP 139/95`).

## Regenerating

The notes come from `tests/synthetic_notes.py` with a fixed seed, so the same
code always gives the same file. After changing the generator, run:

```
python tests/synthetic_notes.py
```
