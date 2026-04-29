import os
import signal
import subprocess
import sys
import time


def test_main_module_execution():
    """Test that the main module can be executed and shut down without crashing."""
    # We use a subprocess to run the module and then terminate it.
    # This ensures the if __name__ == "__main__" block is covered and that startup
    # does not immediately crash.
    env = os.environ.copy()
    env["RECEIPT_SECRET"] = "test_secret"
    env["DATABASE_URL"] = "sqlite:////tmp/test_main_module.db"

    # We must ensure the current directory is in PYTHONPATH so main.py can import its modules
    current_pythonpath = env.get("PYTHONPATH", "")
    if current_pythonpath:
        env["PYTHONPATH"] = f"{current_pythonpath}:."
    else:
        env["PYTHONPATH"] = "."

    process = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=os.path.abspath(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        ),  # Set cwd to coordinator root
    )

    # Wait a short moment for it to start; it should still be running after this.
    time.sleep(1)
    assert process.poll() is None, "main.py exited immediately; startup may have failed"

    # Send SIGTERM to stop it gracefully.
    process.send_signal(signal.SIGTERM)

    # Wait for it to finish
    stdout, stderr = process.communicate(timeout=5)

    # The process should have terminated in response to SIGTERM without an obvious crash.
    assert process.returncode is not None, "main.py did not terminate after SIGTERM"
    assert b"Traceback" not in stderr, (
        f"main.py crashed on startup:\n{stderr.decode(errors='ignore')}"
    )
