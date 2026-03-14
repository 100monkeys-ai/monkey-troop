# 5. RSA-2048 JWT Authentication

Date: 2026-03-14

## Status

Accepted

## Context

In our P2P architecture, worker nodes need a way to verify that a client's request is authorized by the central coordinator. This verification must be secure, efficient, and ideally stateless, so workers don't have to contact the coordinator for every individual inference request.

## Decision

We have decided to use **RSA-2048 signed JSON Web Tokens (JWT)** for our authentication and authorization mechanism.

1.  **Asymmetric Signing**: The coordinator holds a private RSA-2048 key and uses it to sign JWT tickets. Each worker node is pre-configured with the coordinator's public RSA-2048 key.
2.  **Stateless Verification**: Workers can verify the signature and validity of a JWT using the public key locally. This avoids any per-request communication with the coordinator during the inference process.
3.  **Ticket Contents**: Each JWT (ticket) includes essential information such as the `user_id`, the target `node_id`, the allowed `model`, and an `expiration` time.
4.  **Security Standards**: Using RSA-2048 provides strong cryptographic security that meets modern standards.
5.  **Audience Checks**: Workers verify that the `audience` field in the JWT matches their own identity, preventing a ticket from being used on an unintended node.

## Consequences

*   **Security**: RSA-2048 is robust against token forgery. Even if a worker's public key is compromised, it cannot be used to sign new valid tokens.
*   **Performance**: Local verification is extremely fast, minimizing the latency overhead for each inference request.
*   **Decoupling**: Workers can operate independently of the coordinator for authorization as long as the JWT is valid and they have the public key.
*   **Key Management**: The coordinator's public key must be securely distributed to all worker nodes. If the private key is compromised, all previously issued tokens are potentially invalid, and a new key pair must be generated and distributed.
*   **Revocation**: Revoking a JWT before its expiration is challenging in a purely stateless model. We rely on short expiration times (e.g., a few minutes) to mitigate this.
