"""add_error_code_to_clinical_documents

Revision ID: 3c9f1a7be2d4
Revises: 10b249034eda
Create Date: 2026-11-09 13:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c9f1a7be2d4"
down_revision: str | Sequence[str] | None = "10b249034eda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "clinical_documents",
        sa.Column("error_code", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("clinical_documents", "error_code")
