import time
import sqlalchemy as sa
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData


def benchmark_migration(num_users=1000, nodes_per_user=2):
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()

    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("public_key", String, unique=True),
    )

    nodes = Table(
        "nodes",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("owner_id", Integer),
        Column("owner_public_key", String),
    )

    metadata.create_all(engine)

    # Populate data
    with engine.begin() as conn:
        user_data = [{"public_key": f"key_{i}"} for i in range(num_users)]
        conn.execute(users.insert(), user_data)

        node_data = []
        for i in range(num_users):
            for j in range(nodes_per_user):
                node_data.append({"owner_public_key": f"key_{i}"})
        conn.execute(nodes.insert(), node_data)

    # Optimized implementation (Single query)
    start_time = time.perf_counter()
    with engine.begin() as conn:
        users_table = sa.table(
            "users",
            sa.column("id", sa.Integer),
            sa.column("public_key", sa.String),
        )
        nodes_table = sa.table(
            "nodes",
            sa.column("id", sa.Integer),
            sa.column("owner_id", sa.Integer),
            sa.column("owner_public_key", sa.String),
        )

        # For SQLite, we might need a correlated subquery if it doesn't support UPDATE FROM
        # But let's try the SQLAlchemy version that should be more efficient

        # SQLAlchemy correlated subquery update (works on most dialects)
        subquery = (
            sa.select(users_table.c.id)
            .where(users_table.c.public_key == nodes_table.c.owner_public_key)
            .scalar_subquery()
        )
        conn.execute(sa.update(nodes_table).values(owner_id=subquery))

    end_time = time.perf_counter()
    optimized_time = end_time - start_time
    print(f"Optimized implementation time: {optimized_time:.4f}s")

    # Verify results
    with engine.connect() as conn:
        count = conn.execute(
            sa.select(sa.func.count()).select_from(nodes).where(nodes.c.owner_id is None)
        ).scalar()
        if count > 0:
            print(f"FAILED: {count} nodes not updated")
        else:
            print("SUCCESS: All nodes updated")


if __name__ == "__main__":
    benchmark_migration(1000, 5)
