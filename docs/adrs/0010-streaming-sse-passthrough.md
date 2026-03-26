# 10. Streaming SSE Passthrough

Date: 2026-03-14

## Status

Accepted

## Context

Many LLM applications require real-time responses to provide a good user experience. Standard HTTP request-response cycles can introduce significant latency for long-running inference tasks. We need a way to stream responses from the worker engine back to the client as they are generated.

## Decision

We have implemented **zero-copy streaming passthrough** using **Server-Sent Events (SSE)**.

1. **SSE Protocol**: We use the standard SSE protocol for streaming responses from the worker to the client. This is well-supported by most web browsers and LLM client libraries.
2. **Zero-Copy Streaming**: The worker and client agents are designed to forward streaming data from the underlying inference engine (e.g., Ollama) directly to the next hop without buffering or processing the entire response.
3. **Body-to-Stream Conversion**: In Rust, we use `Body::from_stream()` to efficiently handle the streaming data and minimize memory overhead.
4. **OpenAI-Compatible Streaming**: The worker's proxy server correctly handles the `stream: true` parameter in OpenAI-compatible requests and provides the corresponding SSE output.
5. **End-to-End Streaming**: Streaming is supported throughout the entire pipeline: from the worker's inference engine, through the worker's proxy, across the P2P connection, and finally through the client's local proxy to the application.

## Consequences

* **Real-Time Responsiveness**: Users see results as they are generated, greatly improving the perceived performance of LLM interactions.
* **Reduced Latency**: Zero-copy streaming minimizes the time-to-first-token (TTFT) and overall response time.
* **Memory Efficiency**: Streaming avoids the need to buffer large responses in memory, allowing the worker and client to handle many concurrent requests efficiently.
* **Complexity**: Implementing and testing end-to-end streaming is more complex than a simple request-response model, requiring careful handling of connection state and error conditions.
* **Compatibility**: SSE is a well-established standard, but some legacy clients or proxies may not support it correctly.
