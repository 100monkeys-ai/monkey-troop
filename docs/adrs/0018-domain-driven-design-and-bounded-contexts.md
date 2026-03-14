# 18. Domain-Driven Design and Bounded Contexts

Date: 2026-03-14

## Status

Accepted

## Context

Monkey Troop is a complex distributed system involving P2P networking, economic incentives (credits), hardware verification (PoH), and inference orchestration. As the project grows, a procedural or flat architecture risks becoming unmaintainable, with business logic leaking into infrastructure layers and models becoming bloated or ambiguous across different parts of the system.

## Decision

We have adopted **Domain-Driven Design (DDD)** as the primary architectural pattern to manage this complexity. This involves:

1.  **Strict Bounded Contexts**: We have identified and isolated four primary bounded contexts to ensure model integrity:
    *   **Inference Orchestration**: Manages node discovery, model registry, heartbeats, and peer lists.
    *   **Accounting & Credits**: Handles user balances, credit amounts, hardware multipliers, and the transaction ledger.
    *   **Verification (PoH)**: Manages benchmark challenges, proof-of-hardware submissions, and multiplier calculations.
    *   **Security & Identity**: Manages JWT ticket issuance, public/private key pairs, and secure P2P identity.

2.  **Layered "Onion" Architecture**: Each context follows a strict four-layer structure:
    *   **Domain Layer**: Pure entities, value objects, and domain services. Zero dependencies on external libraries or other layers.
    *   **Application Layer**: Use cases and command/query handlers. Defines interfaces (Ports) for infrastructure.
    *   **Infrastructure Layer**: Implementations of ports (Repositories, Clients, Adapters).
    *   **Interface (Presentation) Layer**: FastAPI controllers/routers, Pydantic schemas (DTOs), and CLI commands.

3.  **Ubiquitous Language**: Terminology (e.g., Node, Multiplier, Credit, Heartbeat) is consistently used across code, ADRs, and documentation.

4.  **Dependency Inversion**: High-level domain and application logic must not depend on low-level infrastructure. Infrastructure depends on domain/application interfaces.

## Consequences

*   **Maintainability**: Business logic is isolated and easier to test in isolation.
*   **Scalability**: Different bounded contexts can be refactored or even moved to separate microservices if needed without impacting the entire system.
*   **Clarity**: Clear boundaries prevent the "Big Ball of Mud" pattern.
*   **Development Overhead**: DDD introduces more initial boilerplate (interfaces, DTOs, domain models) compared to procedural code, but reduces long-term technical debt.
*   **Alignment**: This ADR aligns all previous and future ADRs under a unified architectural philosophy.
