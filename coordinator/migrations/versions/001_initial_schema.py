"""initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-01-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_key', sa.String(), nullable=False),
        sa.Column('balance_seconds', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_active', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_key')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    
    # Create nodes table
    op.create_table('nodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('owner_public_key', sa.String(), nullable=False),
        sa.Column('multiplier', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('benchmark_score', sa.Float(), nullable=True),
        sa.Column('trust_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_jobs_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('node_id')
    )
    op.create_index(op.f('ix_nodes_id'), 'nodes', ['id'], unique=False)
    op.create_index(op.f('ix_nodes_owner_public_key'), 'nodes', ['owner_public_key'], unique=False)
    
    # Create transactions table
    op.create_table('transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_user', sa.String(), nullable=True),
        sa.Column('to_user', sa.String(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('credits_transferred', sa.BigInteger(), nullable=False),
        sa.Column('job_id', sa.String(), nullable=True),
        sa.Column('node_id', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_from_user'), 'transactions', ['from_user'], unique=False)
    op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)
    op.create_index(op.f('ix_transactions_to_user'), 'transactions', ['to_user'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_transactions_to_user'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_id'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_from_user'), table_name='transactions')
    op.drop_table('transactions')
    op.drop_index(op.f('ix_nodes_owner_public_key'), table_name='nodes')
    op.drop_index(op.f('ix_nodes_id'), table_name='nodes')
    op.drop_table('nodes')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
