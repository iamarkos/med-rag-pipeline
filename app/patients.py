"""Finding or creating a patient from a pseudonymous reference."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Patient

# "P-" and then 3 to 10 digits, for example P-0042. Letters and spaces are
# refused on purpose, so a name typed into the wrong field is rejected.
PATIENT_REF_PATTERN = r"^P-[0-9]{3,10}$"


def _find_patient(db: Session, patient_ref: str) -> Patient | None:
    return db.execute(
        select(Patient).where(Patient.patient_ref == patient_ref)
    ).scalar_one_or_none()


def get_or_create_patient(db: Session, patient_ref: str) -> Patient:
    """Return the patient with this reference, creating it the first time.

    The caller commits. Creating the patient and saving a document for them
    therefore happen in one transaction: both exist or neither does.
    """
    existing = _find_patient(db, patient_ref)
    if existing is not None:
        return existing

    try:
        # A savepoint: if another request creates the same patient at the same
        # moment, only this small step is undone, not the caller's whole work.
        with db.begin_nested():
            new_patient = Patient(patient_ref=patient_ref)
            db.add(new_patient)
        return new_patient
    except IntegrityError:
        # Lost the race: the other request's patient is the one to use.
        winner = _find_patient(db, patient_ref)
        if winner is None:
            raise
        return winner
