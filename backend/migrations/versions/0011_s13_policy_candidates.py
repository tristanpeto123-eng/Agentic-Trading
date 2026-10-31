"""Add immutable research policy candidate snapshots; no active execution state.

Revision ID: 0011_s13
Revises: 0010_s12
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_s13"
down_revision = "0010_s12"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "research_policy_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("candidate_sha256", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_student_market_version", "research_policy_candidates",
                    ["student_id", "market", "version"], unique=True)
    op.create_index("ix_policy_candidate_hash", "research_policy_candidates",
                    ["candidate_sha256"], unique=True)


def downgrade():
    op.drop_index("ix_policy_candidate_hash", table_name="research_policy_candidates")
    op.drop_index("ix_policy_student_market_version", table_name="research_policy_candidates")
    op.drop_table("research_policy_candidates")
