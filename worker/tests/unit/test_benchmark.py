import importlib
import io
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock torch before importing benchmark if it doesn't exist
if "torch" not in sys.modules:
    mock_torch = MagicMock()
    # Mocking torch.cuda.is_available to return False by default
    mock_torch.cuda.is_available.return_value = False
    sys.modules["torch"] = mock_torch

import benchmark


class TestBenchmark(unittest.TestCase):
    @patch("benchmark.torch")
    @patch("time.time")
    def test_run_benchmark_cpu(self, mock_time, mock_torch):
        # Setup mocks
        mock_torch.cuda.is_available.return_value = False
        mock_time.side_effect = [100.0, 105.0]  # start_time, duration calculation

        mock_result = MagicMock()
        # Mocking the sum() to return something that has .item() which returns 42.0
        mock_result.sum.return_value.item.return_value = 42.0
        mock_torch.randn.return_value = MagicMock()
        mock_torch.matmul.return_value = mock_result

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            benchmark.run_benchmark("deadbeef", 128)
            output = json.loads(fake_out.getvalue())

            self.assertEqual(output["duration"], 5.0)
            self.assertEqual(output["device"], "CPU")
            self.assertTrue(output["proof_hash"])

    @patch("benchmark.torch")
    @patch("time.time")
    def test_run_benchmark_cuda(self, mock_time, mock_torch):
        # Setup mocks
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4090"
        mock_time.side_effect = [200.0, 202.5]

        mock_result = MagicMock()
        mock_result.sum.return_value.item.return_value = 123.456
        mock_torch.randn.return_value = MagicMock()
        mock_torch.matmul.return_value = mock_result

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            benchmark.run_benchmark("cafebabe", 256)
            output = json.loads(fake_out.getvalue())

            self.assertEqual(output["duration"], 2.5)
            self.assertEqual(output["device"], "NVIDIA RTX 4090")
            self.assertTrue(output["proof_hash"])
            mock_torch.cuda.synchronize.assert_called()

    def test_run_benchmark_no_torch(self):
        """Test that run_benchmark raises ImportError if torch is None."""
        with patch("benchmark.torch", None):
            with self.assertRaises(ImportError) as cm:
                benchmark.run_benchmark("abc", 128)
            self.assertEqual(str(cm.exception), "torch is not installed")

    def test_import_benchmark_without_torch(self):
        """Test that missing torch dependency correctly falls back to torch = None during import."""
        with patch.dict("sys.modules", {"torch": None}):
            importlib.reload(benchmark)
            self.assertIsNone(benchmark.torch)

        # Reload again to restore the module state for other tests
        importlib.reload(benchmark)
        self.assertIsNotNone(benchmark.torch)

    def test_main_error_path(self):
        """
        Mock run_benchmark to raise an exception and assert that
        sys.exit(1) is called and an error message is printed to stderr.
        """
        with patch("benchmark.run_benchmark") as mock_run:
            mock_run.side_effect = RuntimeError("Simulated benchmark failure")

            # Arguments: script_name, seed, matrix_size
            with patch("sys.argv", ["benchmark.py", "abc", "128"]):
                with patch("sys.stderr", new=io.StringIO()) as fake_err:
                    with self.assertRaises(SystemExit) as cm:
                        benchmark.main()

                    self.assertEqual(cm.exception.code, 1)
                    err_msg = fake_err.getvalue()
                    self.assertIn(
                        "Benchmark error: Simulated benchmark failure", err_msg
                    )

    def test_main_usage_error(self):
        """Test that missing arguments trigger usage message and exit(1)."""
        with patch("sys.argv", ["benchmark.py"]):  # No args
            with patch("sys.stderr", new=io.StringIO()) as fake_err:
                with self.assertRaises(SystemExit) as cm:
                    benchmark.main()

                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Usage: python3 benchmark.py", fake_err.getvalue())

    def test_main_invalid_matrix_size(self):
        """Test that invalid matrix_size triggers error and exit(1)."""
        with patch("sys.argv", ["benchmark.py", "abc", "not-an-int"]):
            with patch("sys.stderr", new=io.StringIO()) as fake_err:
                with self.assertRaises(SystemExit) as cm:
                    benchmark.main()

                self.assertEqual(cm.exception.code, 1)
                self.assertIn(
                    "Benchmark error: matrix_size must be an integer",
                    fake_err.getvalue(),
                )

    @patch("benchmark.run_benchmark")
    def test_main_success(self, mock_run):
        """Test the successful execution path in the main block."""
        with patch("sys.argv", ["benchmark.py", "1234", "64"]):
            benchmark.main()
            mock_run.assert_called_once_with("1234", 64)


if __name__ == "__main__":
    unittest.main()
