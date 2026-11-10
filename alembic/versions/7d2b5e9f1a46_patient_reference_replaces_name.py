"""patient_reference_replaces_name

Revision ID: 7d2b5e9f1a46
Revises: 3c9f1a7be2d4
Create Date: 2026-11-10 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d2b5e9f1a46"
down_revision: str | Sequence[str] | None = "3c9f1a7be2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Identify patients by a pseudonymous reference and drop their names."""
    # Added empty first, because existing rows need a value before the column
    # can be made mandatory.
    op.add_column("patients", sa.Column("patient_ref", sa.String(), nullable=True))
    # Existing patients get a placeholder made from their unique id.
    op.execute("UPDATE patients SET patient_ref = 'LEGACY-' || CAST(id AS TEXT)")
    op.alter_column("patients", "patient_ref", nullable=False)
    op.create_index(
        op.f("ix_patients_patient_ref"), "patients", ["patient_ref"], unique=True
    )
    # The names are deleted for good: nothing in this project needs them.
    op.drop_column("patients", "full_name")


def downgrade() -> None:
    """Restore the column layout. The deleted names cannot be restored."""
    op.add_column(
        "patients",
        sa.Column("full_name", sa.String(), nullable=False, server_default="unknown"),
    )
    op.alter_column("patients", "full_name", server_default=None)
    op.drop_index(op.f("ix_patients_patient_ref"), table_name="patients")
    op.drop_column("patients", "patient_ref")
