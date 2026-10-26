"""Persist XAUUSD historical bytes in DB for ephemeral Render web previews.

Revision ID: 0010_s12
Revises: 0009_s11

The upgrade is additive. Existing historical dataset metadata is not altered.
Previously imported on-disk datasets still use their original paths unless
the operator explicitly migrates their verified bytes into this archive.
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_s12"
down_revision = "0009_s11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historical_dataset_artifacts",
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("historical_datasets.id"), primary_key=True),
        sa.Column("raw_csv", sa.LargeBinary(), nullable=False),
        sa.Column("canonical_jsonl", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("historical_dataset_artifacts")
