"""Add node_reputations table for ADR-0016

Revision ID: 004_node_reputation
Revises: 003_node_owner_id_fk
Create Date: 2026-03-29 00:00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "004_node_reputation"
down_revision = "003_node_owner_id_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "node_reputations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "node_id",
            sa.String(50),
            sa.ForeignKey("nodes.node_id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("availability", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("reliability", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("performance", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("total_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_heartbeats_expected",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_heartbeats_received",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_node_reputations_node_id", "node_reputations", ["node_id"], unique=True)
    op.create_index("ix_node_reputations_score", "node_reputations", ["score"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_node_reputations_score", table_name="node_reputations")
    op.drop_index("ix_node_reputations_node_id", table_name="node_reputations")
    op.drop_table("node_reputations")
