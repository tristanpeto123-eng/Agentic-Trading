"""Research-only neural training jobs and immutable checkpoint indexes.

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
        sa.Column('config_sha256', sa.String(64), nullable=False),
        sa.Column('snapshot_sha256', sa.String(64), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('snapshot_manifest', sa.JSON(), nullable=False),
        sa.Column('state', sa.String(30), nullable=False),
        sa.Column('qualification', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_training_student_created', 'training_runs', ['student_id', 'created_at'])
    op.create_table('training_checkpoints',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('training_runs.id'), nullable=False),
        sa.Column('epoch', sa.Integer(), nullable=False),
        sa.Column('relative_path', sa.String(300), nullable=False),
        sa.Column('artifact_sha256', sa.String(64), nullable=False),
        sa.Column('snapshot_sha256', sa.String(64), nullable=False),
        sa.Column('train_loss', sa.Float(), nullable=False),
        sa.Column('development_loss', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_training_run_epoch', 'training_checkpoints', ['run_id', 'epoch'], unique=True)


def downgrade():
    op.drop_index('ix_training_run_epoch', table_name='training_checkpoints')
    op.drop_table('training_checkpoints')
    op.drop_index('ix_training_student_created', table_name='training_runs')
    op.drop_table('training_runs')
