"""Blocked CEO paper pilot review, no trading orders. Revision 0009_s11 from 0008_s10."""
from alembic import op
import sqlalchemy as sa
revision='0009_s11';down_revision='0008_s10';branch_labels=None;depends_on=None

def upgrade():
    op.create_table('paper_pilot_requests',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('student_id',sa.String(36),sa.ForeignKey('students.id'),nullable=False),
        sa.Column('ceo_id',sa.String(36),sa.ForeignKey('ceo_users.id'),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('payload_sha256',sa.String(64),unique=True,nullable=False),
        sa.Column('status',sa.String(40),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    op.drop_table('paper_pilot_requests')
