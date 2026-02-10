"""
Proof-of-Hardware benchmark using PyTorch matrix multiplication.
This script is called by worker nodes to prove their hardware capabilities.
"""

import hashlib
import sys
import time

import torch


def get_device():
    """Detect the best available hardware."""
    if torch.cuda.is_available():
        return torch.device("cuda"), torch.cuda.get_device_name(0)
    elif torch.backends.mps.is_available():
        return torch.device("mps"), "Apple Metal (MPS)"
    else:
        return torch.device("cpu"), "CPU (Slow)"


def run_proof_of_hardware(challenge_seed: str, matrix_size=4096, iterations=100):
    """
    Run the benchmark challenge.

    Args:
        challenge_seed: Random seed from coordinator
        matrix_size: Size of matrices (default 4096x4096)
        iterations: Number of iterations (default 100)

    Returns:
        tuple: (proof_hash, duration_seconds, device_name)
    """
    device, device_name = get_device()

    # Deterministic seeding
    seed_int = int(hashlib.sha256(challenge_seed.encode()).hexdigest(), 16) % (2**32)
    torch.manual_seed(seed_int)

    # Initialize matrices
    try:
        a = torch.randn(matrix_size, matrix_size, device=device)
        b = torch.randn(matrix_size, matrix_size, device=device)
    except RuntimeError as e:
        return None, 0, f"OOM Error: {str(e)}"

    # Synchronize before timing
    if device.type == "cuda":
        torch.cuda.synchronize()

    start_time = time.time()

    # The benchmark loop
    current_val = torch.tensor([0.0], device=device)

    for i in range(iterations):
        # Heavy matrix multiplication
        c = torch.matmul(a, b)

        # Chain dependency to prevent optimization
        slice_val = c[0, 0]
        a.add_(slice_val * 0.00001)
        current_val.add_(slice_val)

    # Synchronize after computation
    if device.type == "cuda":
        torch.cuda.synchronize()

    duration = time.time() - start_time

    # Generate proof hash
    final_val_str = str(current_val.item())
    proof_hash = hashlib.sha256(final_val_str.encode()).hexdigest()

    return proof_hash, duration, device_name


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python benchmark.py <challenge_seed>")
        sys.exit(1)

    challenge_seed = sys.argv[1]

    print("--- 🚀 STARTING BENCHMARK ---", file=sys.stderr)
    print(f"Seed: {challenge_seed}", file=sys.stderr)

    proof, duration, device = run_proof_of_hardware(challenge_seed)

    if proof:
        print("--- ✅ RESULTS ---", file=sys.stderr)
        print(f"Device: {device}", file=sys.stderr)
        print(f"Time: {duration:.4f}s", file=sys.stderr)
        print(f"Proof: {proof}", file=sys.stderr)

        # Output JSON to stdout for parsing
        import json

        result = {"proof_hash": proof, "duration": duration, "device_name": device}
        print(json.dumps(result))
    else:
        print("❌ Benchmark failed", file=sys.stderr)
        sys.exit(1)
