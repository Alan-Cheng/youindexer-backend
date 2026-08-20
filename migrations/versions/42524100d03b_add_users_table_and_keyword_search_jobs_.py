"""add users table and keyword_search_jobs user_id

Revision ID: 42524100d03b
Revises: 20260818_0004
Create Date: 2026-08-20 11:27:30.901675
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '42524100d03b'
down_revision: Union[str, Sequence[str], None] = '20260818_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False, comment='使用者識別碼'),
        sa.Column('email', sa.String(length=255), nullable=True, comment='電子郵件'),
        sa.Column('display_name', sa.String(length=255), nullable=True, comment='顯示名稱'),
        sa.Column('google_subject', sa.String(length=255), nullable=True, comment='Google OAuth sub'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='資料建立時間'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='資料更新時間'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_subject'),
        comment='使用者帳號主檔',
    )
    op.create_index('ix_users_google_subject', 'users', ['google_subject'], unique=False)
    op.add_column(
        'keyword_search_jobs',
        sa.Column('user_id', sa.BigInteger(), nullable=True, comment='建立任務的使用者'),
    )
    op.create_index('ix_keyword_search_jobs_user_id', 'keyword_search_jobs', ['user_id'], unique=False)
    op.create_foreign_key(None, 'keyword_search_jobs', 'users', ['user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(None, 'keyword_search_jobs', type_='foreignkey')
    op.drop_index('ix_keyword_search_jobs_user_id', table_name='keyword_search_jobs')
    op.drop_column('keyword_search_jobs', 'user_id')
    op.drop_index('ix_users_google_subject', table_name='users')
    op.drop_table('users')
