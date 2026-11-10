"""source_reference_replaces_filename

Revision ID: a41c8d3e7b92
Revises: 7d2b5e9f1a46
Create Date: 2026-11-10 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a41c8d3e7b92"
down_revision: str | Sequence[str] | None = "7d2b5e9f1a46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Identify documents by a source reference and drop their filenames."""
    # Added empty first, because existing rows need a value before the column
    # can be made mandatory.
    op.add_column(
        "clinical_documents", sa.Column("source_ref", sa.String(), nullable=True)
    )
    # Existing documents get a placeholder. Their originals were never kept, so
    # it points to nothing.
    op.execute(
        "UPDATE clinical_documents SET source_ref = 'legacy-' || CAST(id AS TEXT)"
    )
    op.alter_column("clinical_documents", "source_ref", nullable=False)
    op.create_index(
        op.f("ix_clinical_documents_source_ref"),
        "clinical_documents",
        ["source_ref"],
        unique=True,
    )
    # The filenames are deleted for good: they can contain a patient's name.
    op.drop_column("clinical_documents", "filename")


def downgrade() -> None:
    """Restore the column layout. The deleted filenames cannot be restored."""
    op.add_column(
        "clinical_documents",
        sa.Column("filename", sa.String(), nullable=False, server_default="unknown"),
    )
    op.alter_column("clinical_documents", "filename", server_default=None)
    op.drop_index(
        op.f("ix_clinical_documents_source_ref"), table_name="clinical_documents"
    )
    op.drop_column("clinical_documents", "source_ref")
