# 3. Polyglot Implementation: FastAPI and Rust

Date: 2026-03-14

## Status

Accepted

## Context

The Monkey Troop project involves two distinct types of software components:
1.  **A centralized coordinator**: This component manages users, nodes, transactions, and authentication. It needs a robust API framework, a rich ecosystem for database interactions, and should be easy to develop and iterate on.
2.  **Distributed worker and client agents**: These components run on various hardware (often with limited resources or alongside heavy GPU workloads). They need to be highly performant, have a small footprint, and provide strong memory safety and concurrency guarantees.

## Decision

We have decided on a **polyglot implementation** strategy:

1.  **Coordinator (Python/FastAPI)**:
    *   **FastAPI**: Used for its modern, asynchronous, and easy-to-use API framework. It provides excellent documentation, validation (Pydantic), and high performance for an interpreted language.
    *   **SQLAlchemy/Alembic**: For robust database management and migrations.
    *   **Python Ecosystem**: Allows for easy integration with libraries like PyTorch (for PoH benchmarks) and various utility packages.
2.  **Worker & Client (Rust)**:
    *   **Performance**: Rust's zero-cost abstractions and absence of a garbage collector make it ideal for high-performance networking and proxying.
    *   **Footprint**: Rust produces small, self-contained binaries that are easy to distribute and have low memory overhead.
    *   **Concurrency**: Rust's ownership model and type system ensure thread safety and prevent common bugs in highly concurrent code (like our JWT proxy and heartbeat broadcaster).
    *   **Ecosystem**: The `tokio` (async), `axum` (web server), and `reqwest` (HTTP client) libraries provide a powerful foundation for the worker and client's networking needs.

## Consequences

*   **Development Speed**: Python/FastAPI allows for rapid development and iteration on the coordinator's complex business logic and API.
*   **Operational Efficiency**: Rust's performance and low resource usage make the worker and client highly efficient, which is crucial for components that may be running on a wide range of hardware.
*   **Skill Set Diversity**: This approach requires developers to be comfortable with both Python and Rust, which may slightly increase the onboarding curve for new contributors.
*   **Shared Types**: To maintain consistency between the components, we use a `shared/` Rust crate for common data structures and types, but the coordinator's Python models must be manually synchronized (or use a tool like `pydantic-to-rust-codegen`, which is currently not in use).
