"""Research Strategy DNA and non-authoritative peer lessons.

Revision ID: 0007_s9; Revises: 0006_s8
"""
from alembic import op
import sqlalchemy as sa
revision='0007_s9'
down_revision='0006_s8'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('strategy_revisions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('student_id',sa.String(36),sa.ForeignKey('students.id'),nullable=False),
        sa.Column('family',sa.String(60),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('market',sa.String(16),nullable=False),
        sa.Column('tactic',sa.String(32),nullable=False),
        sa.Column('parent_ids',sa.JSON(),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('payload_sha256',sa.String(64),nullable=False),
        sa.Column('state',sa.String(32),nullable=False))
    op.create_index('ix_strategy_family_version','strategy_revisions',['student_id','family','version'],unique=True)
    op.create_table('peer_lessons',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('source_student_id',sa.String(36),sa.ForeignKey('students.id'),nullable=False),
        sa.Column('target_student_id',sa.String(36),sa.ForeignKey('students.id'),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('payload_sha256',sa.String(64),nullable=False,unique=True))
    op.create_index('ix_peer_target','peer_lessons',['target_student_id'])

def downgrade():
    op.drop_index('ix_peer_target',table_name='peer_lessons')
    op.drop_table('peer_lessons')
    op.drop_index('ix_strategy_family_version',table_name='strategy_revisions')
    op.drop_table('strategy_revisions')
