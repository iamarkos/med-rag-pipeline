"""Tests for how patients are identified (app/patients.py)."""

from sqlalchemy import inspect

from app.database import SessionLocal, engine
from app.models import Patient
from app.patients import get_or_create_patient


def test_the_same_reference_gives_the_same_patient(db):
    first = get_or_create_patient(db, "P-0042")
    db.commit()
    second = get_or_create_patient(db, "P-0042")

    assert second.id == first.id
    assert db.query(Patient).count() == 1


def test_losing_a_race_to_create_the_patient_uses_the_winner(db, monkeypatch):
    # Another request has already created and saved this patient.
    winner = Patient(patient_ref="P-0042")
    db.add(winner)
    db.commit()
    winner_id = winner.id

    # Make our request miss it on the first lookup, as if it ran a moment
    # earlier, so it tries to insert a duplicate and the database refuses.
    from app import patients

    real_find = patients._find_patient
    lookups = []

    def blind_the_first_time(session, patient_ref):
        lookups.append(patient_ref)
        return None if len(lookups) == 1 else real_find(session, patient_ref)

    monkeypatch.setattr("app.patients._find_patient", blind_the_first_time)

    with SessionLocal() as other_session:
        found_id = get_or_create_patient(other_session, "P-0042").id
        other_session.commit()  # the session is still usable after the clash

    assert found_id == winner_id
    assert len(lookups) == 2
    assert db.query(Patient).count() == 1


def test_the_patients_table_stores_no_name():
    columns = {column["name"] for column in inspect(engine).get_columns("patients")}

    assert columns == {"id", "patient_ref", "created_at"}
