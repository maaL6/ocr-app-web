"""add document history image storage and update metadata

Revision ID: 20260713_document_history
Revises: 20260706_users_docs
Create Date: 2026-07-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260713_document_history"
down_revision = "20260706_users_docs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ocr_image_path", sa.String(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "ocr_image_path")
