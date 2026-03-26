# 8. Proof-of-Hardware (PoH) Verification

Date: 2026-03-14

## Status

Accepted

## Context

In a distributed network where providers are rewarded based on their hardware's performance, there is an incentive to spoof or misrepresent capabilities to earn higher credits. We need a reliable way to verify the actual hardware performance of a worker node.

## Decision

We have implemented a **Proof-of-Hardware (PoH)** verification mechanism.

1. **Coordinator Challenge**: The coordinator issues a specific cryptographic challenge and a computational task (e.g., matrix multiplication) to the worker.
2. **Worker Benchmark**: The worker executes the task using its local GPU (via a PyTorch-based benchmark script).
3. **Result Verification**: The worker returns the results and its execution time to the coordinator.
4. **Hardware Multiplier Assignment**: The coordinator verifies the result and assigns a **hardware multiplier** based on the benchmark performance. This multiplier is then used in all future credit calculations for that node.
5. **Initial Registration**: PoH verification is required during the initial registration of a worker node.
6. **Periodic Re-verification**: (Planned) The system should periodically re-verify nodes to ensure hardware remains consistent and to detect changes or spoofing.

## Consequences

* **Integrity**: PoH prevents nodes from falsely advertising high-performance hardware to gain unfair rewards.
* **Fairness**: The hardware multiplier objectively rewards providers based on their hardware's actual performance.
* **Security**: The challenge-response mechanism prevents simple replay attacks.
* **Resource Usage**: The benchmark itself consumes GPU resources, although it's typically a short-duration task.
* **Benchmark Accuracy**: The benchmark must be carefully designed to accurately represent LLM inference performance across different GPU architectures.
* **Timeouts**: Benchmarks have a defined timeout (e.g., 300 seconds) to prevent long-running or stalled processes from blocking the registration flow.
