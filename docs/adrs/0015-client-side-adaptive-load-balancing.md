# 15. Client-Side Adaptive Load Balancing

Date: 2026-03-14

## Status

Proposed

## Context

In a distributed network where many workers may offer the same model, the client's current approach is to select any available node from the coordinator's list. This may result in suboptimal performance if the selected node is under heavy load, has high network latency, or is nearing its memory limits.

## Decision

We propose implementing **Client-Side Adaptive Load Balancing**.

1.  **Metric Collection**: Clients will collect and maintain local metrics for each worker they connect to, including RTT (Round Trip Time), throughput (tokens per second), and historical reliability.
2.  **Worker-Provided Metrics**: Workers will include real-time metrics in their heartbeats, such as current request queue depth, GPU utilization, and KV cache memory pressure.
3.  **Intelligent Selection**: When making a request, the client's proxy will use these metrics (weighted appropriately) to select the most "efficient" worker for the specific request.
4.  **Health Probing**: The client will periodically perform lightweight "health probes" to identify nodes that are unresponsive or experiencing performance issues before sending a full inference request.

## Consequences

*   **Performance**: Intelligent routing will lead to lower latency and higher throughput for the user's inference tasks.
*   **Reliability**: The system will automatically avoid nodes with high failure rates or significant performance degradation.
*   **Efficiency**: Requests will be distributed more evenly across the network, optimizing the use of available GPU resources.
*   **Complexity**: Implementing and maintaining a client-side load balancer with adaptive logic is more complex than simple random or round-robin selection.
*   **Overhead**: Collecting and maintaining worker metrics adds a small amount of network and computational overhead.
