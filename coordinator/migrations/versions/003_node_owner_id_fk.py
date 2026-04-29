"""Replace nodes.owner_public_key FK with nodes.owner_id FK to users.id

Revision ID: 003_node_owner_id_fk
Revises: 002_audit_log
Create Date: 2026-03-14 00:00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003_node_owner_id_fk"
down_revision = "002_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the new surrogate FK column (nullable initially to allow backfill)
    op.add_column("nodes", sa.Column("owner_id", sa.Integer(), nullable=True))

    # Backfill owner_id from the users table via the existing owner_public_key.
    # Use SQLAlchemy table constructs to stay dialect-agnostic.
    nodes_table = sa.table(
        "nodes",
        sa.column("id", sa.Integer),
        sa.column("owner_id", sa.Integer),
        sa.column("owner_public_key", sa.String),
    )
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("public_key", sa.String),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(users_table.c.id, users_table.c.public_key)
    ).fetchall()
    for user_id, public_key in rows:
        conn.execute(
            sa.update(nodes_table)
            .where(nodes_table.c.owner_public_key == public_key)
            .values(owner_id=user_id)
        )

    # Make owner_id non-nullable now that it is populated
    op.alter_column("nodes", "owner_id", nullable=False)

    # Add FK constraint and index on owner_id
    op.create_foreign_key(
        "fk_nodes_owner_id_users",
        "nodes",
        "users",
        ["owner_id"],
        ["id"],
    )
    op.create_index(op.f("ix_nodes_owner_id"), "nodes", ["owner_id"], unique=False)

    # Drop the old index on owner_public_key (the FK constraint was only present
    # when using create_all(); migrations never added it, so we only drop the index).
    op.drop_index(op.f("ix_nodes_owner_public_key"), table_name="nodes")


def downgrade() -> None:
    # Restore index on owner_public_key
    op.create_index(
        op.f("ix_nodes_owner_public_key"), "nodes", ["owner_public_key"], unique=False
    )

    # Drop the owner_id FK constraint, index, and column
    op.drop_index(op.f("ix_nodes_owner_id"), table_name="nodes")
    op.drop_constraint("fk_nodes_owner_id_users", "nodes", type_="foreignkey")
    op.drop_column("nodes", "owner_id")
