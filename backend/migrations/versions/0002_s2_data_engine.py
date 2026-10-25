"""Immutable historical dataset metadata; raw files stored out-of-repo.

Revision ID: 0002_s2
Revises: 0001_s1
"""
from alembic import op
import sqlalchemy as sa
revision = "0002_s2"
down_revision = "0001_s1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("historical_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("canonical_hash", sa.String(64), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("quality_report", sa.JSON(), nullable=False),
        sa.Column("raw_path", sa.String(300), nullable=False),
        sa.Column("canonical_path", sa.String(300), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("historical_datasets")
