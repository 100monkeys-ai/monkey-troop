# AGENTS.md - Monkey Troop Development Mandates

This document establishes the foundational architectural and development standards for Monkey Troop, mandating strict compliance with **Domain-Driven Design (DDD)** principles. All agents (human or AI) contributing to this codebase must adhere to these patterns to ensure scalability, maintainability, and clear separation of business logic from infrastructure.

---

## 1. DDD Philosophy
Monkey Troop manages complex distributed state, P2P networking, and economic incentives. To manage this complexity, we prioritize:
- **Business Logic First**: The core domain logic must be isolated from databases, APIs, and frameworks.
- **Explicit Bounded Contexts**: Clear boundaries between different sub-domains to prevent model pollution.
- **Ubiquitous Language**: Using consistent terminology across code, tests, and documentation.

---

## 2. Architectural Context & ADRs
This development mandate is the implementation strategy for the decisions recorded in the project's **Architectural Decision Records (ADRs)** located in `docs/adrs/`. 

- **ADR-0002 (P2P Architecture)**: Defines the separation of Control (Coordinator) and Data (Worker/Client) planes.
- **ADR-0006 (Credit System)**: Establishes the core domain logic for the Accounting context.
- **ADR-0007 (Multi-Engine Abstraction)**: Mandates the engine-agnostic domain models for Inference.
- **ADR-0011 (Audit Logging)**: Defines cross-cutting concerns for security and compliance.

All code changes must not only comply with DDD patterns but also remain consistent with the finalized decisions in these ADRs.

## 3. Ubiquitous Language
- **Node/Worker**: A GPU provider contributing compute to the network.
- **Requester/Client**: A user or service consuming inference from a Node.
- **Coordinator**: The control plane managing discovery, verification, and accounting.
- **Credit**: The unit of value for time-based compute access.
- **Multiplier**: A factor derived from hardware performance (PoH) that scales credit costs/earnings.
- **Heartbeat**: A periodic status update from a Node to the Coordinator.
- **PoH (Proof-of-Hardware)**: A benchmark-based verification process to prove GPU performance.

---

## 3. Bounded Contexts

### 3.1 Inference Orchestration
- **Responsibility**: Node discovery, model registry management, heartbeat tracking, and load balancing.
- **Key Entities**: `Node`, `Model`, `Engine`.
- **Primary Aggregate**: `Node` (Aggregate Root).

### 3.2 Accounting & Credits (Ledger)
- **Responsibility**: Credit balance management, hardware multipliers, and transaction auditing.
- **Key Entities**: `User`, `Transaction`, `Ledger`.
- **Primary Aggregate**: `User` (Aggregate Root for Balance/Transactions).

### 3.3 Verification (PoH)
- **Responsibility**: Issuing benchmark challenges and verifying cryptographic proofs of work.
- **Key Entities**: `Challenge`, `Proof`, `BenchmarkResult`.
- **Primary Aggregate**: `Challenge` (Aggregate Root).

### 3.4 Security & Identity
- **Responsibility**: JWT ticket issuance, public key management, and P2P connection security.
- **Key Entities**: `Identity`, `Ticket`, `AuthToken`.

---

## 4. Layered Architecture (The Onion)

Strict adherence to the following four layers is required:

### 4.1 Domain Layer (Core)
- **Entities**: Objects with identity and lifecycle (e.g., `User`).
- **Value Objects**: Immutable objects with no identity (e.g., `HardwareSpec`, `CreditAmount`).
- **Aggregates**: Groups of entities and value objects that are treated as a single unit (e.g., `User` manages its own `Balance`).
- **Domain Services**: Logic that doesn't naturally fit into an entity (e.g., `CreditCalculator`).
- **Domain Events**: Significant occurrences within the domain.
- **RULES**:
    - **Zero Dependencies**: Must not import from Application, Infrastructure, or Presentation.
    - **No Side Effects**: Methods should prioritize pure functions where possible.

### 4.2 Application Layer
- **Use Cases**: Orchestrates domain objects to perform specific tasks (e.g., `SubmitJobReceipt`).
- **Command/Query Handlers**: Decouples the request for an action from its execution.
- **Interfaces**: Defines repository and external service interfaces (Ports).
- **RULES**:
    - Does not contain business logic; it coordinates it.
    - No direct database access or API calls.

### 4.3 Infrastructure Layer
- **Repositories**: Implementations of Domain/Application interfaces (e.g., `SQLAlchemyUserRepo`).
- **External Clients**: Adaptors for Redis, Tailscale, or Engine APIs (Ollama, etc.).
- **RULES**:
    - Depends on the Domain and Application layers.
    - Isolates implementation details of third-party libraries.

### 4.4 Presentation (Interface) Layer
- **Controllers**: FastAPI endpoints or CLI commands.
- **DTOs (Data Transfer Objects)**: Pydantic or Serde models for API requests/responses.
- **Validation**: Ensures incoming data is well-formed before passing it to the Application layer.

---

## 5. Strict Compliance Rules

1. **Dependency Inversion**: High-level modules (Application/Domain) must not depend on low-level modules (Infrastructure). Use interfaces/abstract classes.
2. **Persistence Ignorance**: Domain objects must not know how they are saved or retrieved.
3. **Explicit Aggregate Roots**: Access to entities within an aggregate must only happen through the aggregate root.
4. **Validation at the Edge**: DTOs handle structural validation; Domain objects handle business invariant validation.
5. **No "God Modules"**: Refactor large procedural files (like `main.py` or `transactions.py`) into their respective contexts and layers.

---

## 6. Implementation Guidelines

### 6.1 Python (Coordinator) Recommended Folder Structure
```
coordinator/
├── domain/            # Entities, Value Objects, Domain Services
│   ├── accounting/    # Context: Accounting
│   └── inference/     # Context: Inference
├── application/       # Use Cases, Ports (Interfaces)
├── infrastructure/    # Adapters (PostgreSQL, Redis, JWT)
├── interface/         # FastAPI Controllers, Pydantic DTOs
└── tests/             # Unit (Domain/App) and Integration (Infra)
```

### 6.2 Rust (Worker/Client) Recommended Folder Structure
```
worker/src/
├── domain/            # Domain logic, Model registry
├── application/       # Task execution, heartbeat logic
├── infrastructure/    # Engine drivers, GPU access, Axum server
├── presentation/      # CLI, Proxy endpoints
└── main.rs
```

---

## 7. Refactoring Mandate
When modifying existing procedural code:
1. Identify the **Bounded Context**.
2. Identify the **Layer** the code belongs to.
3. Move the logic to the appropriate directory following the structures above.
## 8. Mandatory Validation, Testing & Production Readiness

### 8.1 Compulsory Validation Commands
After **any** code modification, the following commands must be executed and pass without any warnings or failures.

**For Rust (Worker/Client/Shared):**
```bash
cargo fmt --all && \
cargo clippy --workspace --locked -- -D warnings && \
cargo build --release && \
cargo test --workspace --locked && \
cargo doc --no-deps
```

**For Python (Coordinator):**
```bash
black . && \
ruff check . && \
pytest --cov=. --cov-report=term-missing --cov-fail-under=100
```

### 8.2 Production Readiness & Testing
- **100% Test Coverage**: All new code and refactored code MUST be covered by automated tests. This includes unit tests for the Domain and Application layers, and integration tests for the Infrastructure and Interface layers.
- **Passing Test Suite**: No change is considered complete if any test in the workspace fails.
- **No Dead Code**: Unused functions, variables, or structs are strictly forbidden. Use of `#[allow(dead_code)]` or similar attributes is prohibited.
- **No Stubs/Placeholders**: All logic must be fully implemented according to the ADRs and domain requirements. "TODO" comments or mock implementations are not permitted in the production branch.
- **Surgical Implementation**: If a feature cannot be fully implemented, it must be removed rather than left in a partial or stubbed state.
