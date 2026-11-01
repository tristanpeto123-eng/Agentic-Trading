"""Durable research neural training snapshots and immutable epoch weights.

Revision ID: 0012_s14
Revises: 0011_s13
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_s14"
down_revision = "0011_s13"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "research_neural_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("tactic", sa.String(32), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("frozen_examples", sa.JSON(), nullable=False),
        sa.Column("epochs_planned", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("qualification", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_research_neural_student_created", "research_neural_runs",
                    ["student_id", "created_at"])
    op.create_table(
        "research_neural_epochs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("research_neural_runs.id"), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("weights_npz", sa.LargeBinary(), nullable=False),
        sa.Column("weights_sha256", sa.String(64), nullable=False),
        sa.Column("train_loss", sa.Float(), nullable=False),
        sa.Column("development_loss", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_neural_epoch_unique", "research_neural_epochs",
                    ["run_id", "epoch"], unique=True)


def downgrade():
    op.drop_index("ix_neural_epoch_unique", table_name="research_neural_epochs")
    op.drop_table("research_neural_epochs")
    op.drop_index("ix_research_neural_student_created", table_name="research_neural_runs")
    op.drop_table("research_neural_runs")
