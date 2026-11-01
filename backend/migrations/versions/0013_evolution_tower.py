"""Evolution Tower persistence, research-only.

Revision ID: 0013_tower
Revises: 0012_s14
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_tower"
down_revision = "0012_s14"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evolution_tower_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ceo_id", sa.String(36), sa.ForeignKey("ceo_users.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("state_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evolution_tower_ceo", "evolution_tower_sessions", ["ceo_id"], unique=True)
    op.create_table(
        "evolution_tower_archive",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("evolution_tower_sessions.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("event", sa.JSON(), nullable=False),
        sa.Column("event_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evolution_tower_event_generation", "evolution_tower_archive",
                    ["session_id", "generation"], unique=True)


def downgrade():
    op.drop_index("ix_evolution_tower_event_generation", table_name="evolution_tower_archive")
    op.drop_table("evolution_tower_archive")
    op.drop_index("ix_evolution_tower_ceo", table_name="evolution_tower_sessions")
    op.drop_table("evolution_tower_sessions")
