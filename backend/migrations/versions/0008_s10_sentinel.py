"""Latched CEO emergency stop. Revision ID 0008_s10, revises 0007_s9."""
from alembic import op
import sqlalchemy as sa
revision='0008_s10';down_revision='0007_s9';branch_labels=None;depends_on=None

def upgrade():
    op.create_table('safety_latches',
       sa.Column('id',sa.String(36),primary_key=True),
       sa.Column('reason',sa.String(200),nullable=False),
       sa.Column('actor_id',sa.String(36),sa.ForeignKey('ceo_users.id'),nullable=False),
       sa.Column('locked_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    op.drop_table('safety_latches')
