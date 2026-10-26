"""Offline immutable-by-service research examination reports.

Revision ID: 0005_s7
Revises: 0004_s6
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_s7'
down_revision = '0004_s6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('exam_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('training_run_id', sa.String(36), sa.ForeignKey('training_runs.id'), nullable=False),
        sa.Column('plan_sha256', sa.String(64), nullable=False),
        sa.Column('report_sha256', sa.String(64), nullable=False),
        sa.Column('report', sa.JSON(), nullable=False),
        sa.Column('dataset_id', sa.String(36), sa.ForeignKey('historical_datasets.id'), nullable=False),
        sa.Column('source_sha256', sa.String(64), nullable=False),
        sa.Column('challenger_model_sha256', sa.String(64), nullable=False),
        sa.Column('market', sa.String(16), nullable=False),
        sa.Column('tactic', sa.String(32), nullable=False),
        sa.Column('verdict', sa.String(36), nullable=False),
        sa.Column('qualification', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_exams_student_created', 'exam_runs', ['student_id', 'created_at'])


def downgrade():
    op.drop_index('ix_exams_student_created', table_name='exam_runs')
    op.drop_table('exam_runs')
