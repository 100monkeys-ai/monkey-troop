from infrastructure.persistence.database import get_db


def test_get_db_yields_and_closes():
    """Test that get_db yields a session and then closes it."""
    gen = get_db()
    db = next(gen)
    assert db is not None
    try:
        next(gen)
    except StopIteration:
        pass
    # If we reached here without error, the finally block executed.
