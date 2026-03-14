# 13. End-to-End Encryption for Inference Data

Date: 2026-03-14

## Status

Proposed

## Context

While current communication is encrypted in transit via WireGuard (Tailscale), the worker node itself still receives inference prompts and generates responses in plaintext. In a distributed network of third-party workers, this creates a privacy risk where a malicious worker owner could intercept or log sensitive user data.

## Decision

We propose implementing **End-to-End Encryption (E2E)** for all inference payloads.

1.  **Asymmetric Encryption**: Each worker node will publish a public encryption key as part of its heartbeat to the coordinator.
2.  **Payload Encryption**: The client will encrypt the inference prompt using the target worker's public key before sending it.
3.  **Secure Response**: The worker will encrypt the generated response using a session key (negotiated via ECDH) before streaming it back to the client.
4.  **Key Management**: The client agent will handle key discovery and encryption/decryption transparently, presenting a standard plaintext API to the local application.

## Consequences

*   **Privacy**: Neither the coordinator nor the worker owner (outside the secure process) can read the prompt or response content.
*   **Trust**: Users can utilize third-party workers with significantly higher confidence in their data privacy.
*   **Overhead**: Encryption and decryption will add a small amount of computational overhead to both the client and the worker.
*   **Complexity**: Managing public key distribution and session key negotiation increases the complexity of the client and worker networking logic.
*   **Compatibility**: This requires both the client and worker to support the E2E encryption protocol.
