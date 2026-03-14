# 7. Multi-Engine Inference Abstraction

Date: 2026-03-14

## Status

Accepted

## Context

Different worker nodes may run different inference engines (e.g., Ollama, vLLM, LM Studio) based on their hardware, operating system, or user preference. To create a unified distributed network, we need the worker agent to support multiple engines and provide a consistent interface to the client.

## Decision

We have implemented a **multi-engine abstraction layer** within the worker.

1.  **Engine Drivers**: We've created specific drivers for Ollama, vLLM, and LM Studio. Each driver is responsible for detecting available models and communicating with the engine's API.
2.  **Universal Model Registry**: The worker maintains a unified registry of all models available across all locally installed and running engines.
3.  **Priority-Based Routing**: When a request arrives, the worker automatically routes it to the most appropriate engine based on model availability and pre-defined priorities (e.g., vLLM > Ollama > LM Studio).
4.  **OpenAI-Compatible Proxy**: The worker presents an OpenAI-compatible API to the client, regardless of the underlying engine's native API.
5.  **Dynamic Discovery**: The worker periodically refreshes its model registry (default every 3 minutes) and only sends heartbeats to the coordinator when the registry changes.

## Consequences

*   **Flexibility**: Users can choose their preferred inference engine, and the worker will adapt.
*   **Interoperability**: Different engines are unified under a single, standard interface (OpenAI API).
*   **Optimized Routing**: Priority-based routing allows us to leverage the strengths of each engine (e.g., vLLM's high throughput).
*   **Reduced Coordinator Traffic**: Only sending heartbeats on changes significantly reduces network load on the central coordinator.
*   **Maintenance**: Each supported engine requires a dedicated driver, which must be maintained as engine APIs evolve.
*   **Feature Parity**: Some engines may support advanced features that others don't, requiring careful abstraction to provide a consistent experience.
