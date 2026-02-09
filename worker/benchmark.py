#!/usr/bin/env python3
"""
Hardware benchmark script for Proof-of-Hardware verification.
Runs matrix multiplication using PyTorch and returns timing + hash proof.
"""

import sys
import json
import hashlib
import time
import torch

def run_benchmark(seed: str, matrix_size: int):
    """Run GPU benchmark with given seed and matrix size."""
    
    # Set seed for reproducibility
    seed_int = int(seed, 16) % (2**32)
    torch.manual_seed(seed_int)
    
    # Check for GPU availability
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Generate random matrices
    a = torch.randn(matrix_size, matrix_size, device=device)
    b = torch.randn(matrix_size, matrix_size, device=device)
    
    # Warm-up run
    _ = torch.matmul(a, b)
    if device == "cuda":
        torch.cuda.synchronize()
    
    # Timed run
    start_time = time.time()
    result = torch.matmul(a, b)
    if device == "cuda":
        torch.cuda.synchronize()
    duration = time.time() - start_time
    
    # Generate proof hash from seed, duration, and result checksum
    result_sum = result.sum().item()
    proof_data = f"{seed}:{duration:.6f}:{result_sum:.6f}"
    proof_hash = hashlib.sha256(proof_data.encode()).hexdigest()
    
    # Get device name
    if device == "cuda":
        device_name = torch.cuda.get_device_name(0)
    else:
        device_name = "CPU"
    
    # Output JSON
    output = {
        "proof_hash": proof_hash,
        "duration": duration,
        "device": device_name
    }
    
    print(json.dumps(output))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 benchmark.py <seed> <matrix_size>", file=sys.stderr)
        sys.exit(1)
    
    seed = sys.argv[1]
    matrix_size = int(sys.argv[2])
    
    try:
        run_benchmark(seed, matrix_size)
    except Exception as e:
        print(f"Benchmark error: {e}", file=sys.stderr)
        sys.exit(1)
