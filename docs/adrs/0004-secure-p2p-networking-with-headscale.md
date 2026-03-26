# 4. Secure P2P Networking with Headscale/Tailscale

Date: 2026-03-14

## Status

Accepted

## Context

In our P2P architecture, clients and workers need a secure and reliable way to connect to each other across different networks. They may be behind NATs, firewalls, or on mobile networks. Establishing direct connections (NAT traversal) and ensuring all traffic is encrypted and authenticated are significant challenges.

## Decision

We have decided to use **Headscale/Tailscale** (based on the WireGuard protocol) for our networking layer.

1. **Mesh Networking**: Tailscale (and its open-source alternative, Headscale) provides a zero-config, P2P mesh network that simplifies NAT traversal and connection establishment.
2. **Encryption and Security**: All traffic over the Tailscale network is encrypted using WireGuard (ChaCha20-Poly1305), providing strong security by default.
3. **Authentication**: Each node is assigned a unique IP address on the Tailscale network, and connections are authenticated at the network level.
4. **Open Source Control**: We use **Headscale** as our self-hosted coordination server to maintain full control over the network's control plane and metadata.
5. **Simplified Development**: Using Tailscale allows developers to work with standard IP-based networking as if the nodes were on the same local network, abstracting away the complexities of the internet's infrastructure.

## Consequences

* **Security**: All P2P traffic is encrypted and authenticated by default, reducing the risk of eavesdropping or unauthorized access.
* **NAT Traversal**: Tailscale's sophisticated NAT traversal techniques ensure that nodes can connect to each other in almost any network environment.
* **Reliability**: The mesh network is robust and automatically handles changes in node IP addresses and network conditions.
* **Dependency**: The project depends on the Headscale/Tailscale ecosystem. While we use the open-source Headscale, the client-side agents are often proprietary (though we use the open-source `tailscaled` where possible).
* **Deployment**: Deploying the network requires setting up and managing a Headscale server, which adds to the infrastructure overhead.
* **Performance**: While WireGuard is highly performant, there is a small overhead associated with encryption and Tailscale's coordination.
