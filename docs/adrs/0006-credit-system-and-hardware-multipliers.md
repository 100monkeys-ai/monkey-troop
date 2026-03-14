# 6. Credit System and Transaction Ledger

Date: 2026-03-14

## Status

Accepted

## Context

Monkey Troop is designed as an incentivized network where users provide GPU resources to others. To ensure fairness and resource allocation, we need a way to track usage, reward providers (workers), and charge consumers (clients).

## Decision

We have implemented a **time-based credit system** with a persistent **transaction ledger**.

1.  **Credit-Based Economy**: Users have a credit balance. New users receive initial "starter" credits.
2.  **Hardware Multipliers**: Not all GPUs are created equal. We assign each worker node a "hardware multiplier" based on its performance (determined by PoH benchmarks). Higher-performance nodes earn more credits per unit of time.
3.  **Usage Tracking**: Inference duration is tracked. The credit cost is calculated as `duration * hardware_multiplier`.
4.  **Transaction Ledger (PostgreSQL)**: All credit movements (grants, debits, credits) are recorded in a central `transactions` table in the coordinator's database. This provides a full audit trail and history.
5.  **Receipt Verification**: After a job is completed, the worker issues a signed "receipt" (HMAC-SHA256) to the client. The client then presents this receipt to the coordinator to finalize the transaction.
6.  **Authorization Check**: The coordinator checks the user's balance before issuing a JWT authorization ticket, ensuring they have sufficient credits for the request.
7.  **ZKP Roadmap (Planned)**: To enhance privacy and prevent the coordinator from learning details about the computation, the receipt mechanism will transition to **Zero-Knowledge Proofs (ZKP)**. Workers will generate a proof of work that the coordinator can verify without needing access to secret keys or task-specific metadata.

## Consequences

*   **Fairness**: Hardware multipliers ensure that providers with more powerful hardware are rewarded proportionally to the value they provide.
*   **Auditability**: The transaction ledger provides a transparent record of all credit-related events.
*   **Security**: HMAC-signed receipts (and later ZKPs) prevent clients from forging job completion records to manipulate their credit balances.
*   **System Integrity**: Pre-authorization checks prevent users from using resources they haven't paid for (or haven't been granted).
*   **Incentives**: The system provides clear incentives for users to join as providers and contribute their idle GPU capacity to the network.
*   **Privacy Enhancement**: Adopting ZKPs will ensure that the coordinator only learns *that* work was done, not *what* was done, further decoupling the control plane from the data plane.
