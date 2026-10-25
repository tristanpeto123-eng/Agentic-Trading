"""Initial CEO users, students, immutable learning plans and audit events.

Revision ID: 0001_s1
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_s1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ceo_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "students",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("name_key", sa.String(80), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "learning_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("markets", sa.JSON(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_student_plan_version", "learning_plans", ["student_id", "version"], unique=True)
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("ceo_users.id"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("audit_events")
    op.drop_index("ix_student_plan_version", table_name="learning_plans")
    op.drop_table("learning_plans")
    op.drop_table("students")
    op.drop_table("ceo_users")
