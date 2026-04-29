import sqlite3
import time

def benchmark_migration(num_users=1000, nodes_per_user=5):
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, public_key TEXT UNIQUE)")
    cursor.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, owner_id INTEGER, owner_public_key TEXT)")

    # Populate data
    users = [(i, f"key_{i}") for i in range(num_users)]
    cursor.executemany("INSERT INTO users VALUES (?, ?)", users)

    nodes = []
    for i in range(num_users):
        for j in range(nodes_per_user):
            nodes.append((f"key_{i}",))
    cursor.executemany("INSERT INTO nodes (owner_public_key) VALUES (?)", nodes)
    conn.commit()

    # Current implementation (N+1 simulated)
    start_time = time.perf_counter()
    cursor.execute("SELECT id, public_key FROM users")
    user_rows = cursor.fetchall()
    for user_id, public_key in user_rows:
        cursor.execute(
            "UPDATE nodes SET owner_id = ? WHERE owner_public_key = ?",
            (user_id, public_key)
        )
    conn.commit()
    end_time = time.perf_counter()
    n_plus_one_time = end_time - start_time
    print(f"N+1 implementation time: {n_plus_one_time:.4f}s")

    # Reset owner_id
    cursor.execute("UPDATE nodes SET owner_id = NULL")
    conn.commit()

    # Optimized implementation (Single query using correlated subquery as UPDATE FROM is not in all sqlite versions)
    start_time = time.perf_counter()
    cursor.execute("""
        UPDATE nodes
        SET owner_id = (SELECT id FROM users WHERE users.public_key = nodes.owner_public_key)
    """)
    conn.commit()
    end_time = time.perf_counter()
    optimized_time = end_time - start_time
    print(f"Optimized implementation time: {optimized_time:.4f}s")

    # Verify results
    cursor.execute("SELECT COUNT(*) FROM nodes WHERE owner_id IS NULL")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"FAILED: {count} nodes not updated")
    else:
        print("SUCCESS: All nodes updated")

    conn.close()

if __name__ == "__main__":
    benchmark_migration(2000, 5)
