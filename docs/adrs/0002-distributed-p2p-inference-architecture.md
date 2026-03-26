# 2. Distributed P2P Inference Architecture

Date: 2026-03-14

## Status

Accepted

## Context

Typical cloud inference services (e.g., OpenAI, Anthropic) use a centralized model where all requests and data pass through the service provider's infrastructure. This centralizes control, but also introduces potential privacy concerns, high infrastructure costs for the provider, and a single point of failure or bottleneck for data transfer. For Monkey Troop, we want to leverage a distributed network of idle GPUs while maintaining privacy and performance.

## Decision

We have adopted a **Peer-to-Peer (P2P) Distributed Inference Architecture**.

1. **Separation of Control and Data Planes**:
    * **Control Plane (Coordinator)**: A central coordinator handles node registration, discovery, authentication (issuing JWT tickets), and credit accounting. It *never* sees the actual inference data (prompts or responses).
    * **Data Plane (Client/Worker)**: The client connects directly to a selected worker node using a secure VPN (Headscale/Tailscale). The inference request and response flow directly between the client and the worker.
2. **Stateless Coordinator**: The coordinator is designed to be stateless (using Redis for ephemeral state and PostgreSQL for persistent data), allowing it to scale horizontally.
3. **Client-Side Discovery**: The client is responsible for discovering available nodes via the coordinator and establishing the direct connection.
4. **Federation Roadmap (Planned)**: To avoid a single point of failure and enhance censorship resistance, the coordinator will transition to a **federated model**. Multiple coordinators can synchronize state via a distributed ledger or consensus protocol, allowing users to choose their preferred coordinator while still participating in the global worker pool.

## Consequences

* **Privacy**: User prompts and model outputs are only ever seen by the client and the specific worker processing the request. The coordinator has no visibility into the content.
* **Scalability**: The network's inference capacity scales with the number of worker nodes, without placing additional load on the central coordinator's bandwidth.
* **Low Latency**: Direct P2P connections minimize network hops for the large data transfers associated with LLM inference.
* **Complexity**: Managing P2P connections and discovery is more complex than a standard centralized API. We use Headscale/Tailscale to mitigate the networking complexity.
* **Trust**: While the coordinator doesn't see data, users must trust the worker nodes (or the system must provide mechanisms like TEEs, which are currently out of scope).
* **Resilience (via Federation)**: Moving to a federated model will eliminate the single point of failure and allow for a more robust, decentralized network.
