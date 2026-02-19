import os
import sys

# Set required environment variables for tests
os.environ.setdefault("RECEIPT_SECRET", "test_secret_key_for_unit_tests")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")

# Add coordinator root directory to sys.path so tests can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
