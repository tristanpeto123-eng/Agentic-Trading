"""Append-only closed trade research archive.

Revision ID: 0003_s5
Revises: 0002_s2
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_s5'
down_revision = '0002_s2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('trade_experiences',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('source_id', sa.String(120), nullable=False),
        sa.Column('source_sha256', sa.String(64), nullable=False),
        sa.Column('origin', sa.String(32), nullable=False),
        sa.Column('partition', sa.String(20), nullable=False),
        sa.Column('instrument', sa.String(16), nullable=False),
        sa.Column('strategy_version', sa.String(100), nullable=False),
        sa.Column('skill_ids', sa.JSON(), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('outcome', sa.String(8), nullable=False),
        sa.Column('net_pnl_usd', sa.String(64), nullable=False),
        sa.Column('net_r', sa.String(64), nullable=False),
    )
    op.create_index('ix_experience_student_asof', 'trade_experiences', ['student_id', 'available_at'])
    op.create_index('ix_experience_student_partition', 'trade_experiences', ['student_id', 'partition'])


def downgrade():
    op.drop_index('ix_experience_student_partition', table_name='trade_experiences')
    op.drop_index('ix_experience_student_asof', table_name='trade_experiences')
    op.drop_table('trade_experiences')
