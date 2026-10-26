"""Persistent research Academy jobs. Revision ID 0006_s8, revises 0005_s7."""
from alembic import op
import sqlalchemy as sa
revision = '0006_s8'
down_revision = '0005_s7'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('academy_jobs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('student_id',sa.String(36),sa.ForeignKey('students.id'),nullable=False),
        sa.Column('plan_version',sa.Integer(),nullable=False),
        sa.Column('idempotency_sha256',sa.String(64),unique=True,nullable=False),
        sa.Column('spec',sa.JSON(),nullable=False),
        sa.Column('state',sa.String(36),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('worker_id',sa.String(100),nullable=True),
        sa.Column('lease_until',sa.DateTime(timezone=True),nullable=True),
        sa.Column('result',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_academy_student_state','academy_jobs',['student_id','state'])

def downgrade():
    op.drop_index('ix_academy_student_state',table_name='academy_jobs')
    op.drop_table('academy_jobs')
