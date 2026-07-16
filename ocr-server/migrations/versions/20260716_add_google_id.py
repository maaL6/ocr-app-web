"""add google_id to users and make password_hash nullable

Revision ID: 20260716_add_google_id
Revises: 20260713_document_history
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260716_add_google_id"
down_revision: Union[str, None] = "20260713_document_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add google_id column
    op.add_column("users", sa.Column("google_id", sa.String(), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)

    # 2. Make password_hash nullable
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # 1. Make password_hash non-nullable
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)

    # 2. Drop google_id column and index
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_id")
