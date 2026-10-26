"""Add research-only neural training registry.

Revision ID: 0004_s6
Revises: 0003_s5
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_s6'
down_revision = '0003_s5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('training_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('plan_version', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.String(80), nullable=False),
        sa.Column('instrument', sa.String(16), nullable=False),
        sa.Column('experiment_key', sa.String(64), nullable=False, unique=True),
        sa.Column('provenance_hash', sa.String(64), nullable=False),
        sa.Column('checkpoint_hash', sa.String(64), nullable=False),
        sa.Column('checkpoint_path', sa.String(300), nullable=False),
        sa.Column('training_summary', sa.JSON(), nullable=False),
        sa.Column('state', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_training_student_created', 'training_runs', ['student_id', 'created_at'])


def downgrade():
    op.drop_index('ix_training_student_created', table_name='training_runs')
    op.drop_table('training_runs')
