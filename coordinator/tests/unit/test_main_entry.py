import runpy
from unittest.mock import patch


def test_main_entry_point():
    """Test the if __name__ == '__main__' block."""
    with patch("uvicorn.run") as mock_run:
        # Execute the module as __main__ using runpy so the entry point block runs.
        runpy.run_module("main", run_name="__main__", alter_sys=True)

        mock_run.assert_called_with("main:app", host="0.0.0.0", port=8000)
