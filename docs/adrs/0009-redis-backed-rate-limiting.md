# 9. Redis-backed Rate Limiting

Date: 2026-03-14

## Status

Accepted

## Context

To protect the coordinator from abuse and ensure fair access to its discovery and authentication endpoints, we need a way to limit the rate of requests from individual users and IP addresses.

## Decision

We have implemented **Redis-backed rate limiting** with a sliding window algorithm.

1. **Sliding Window Algorithm**: This algorithm provides a smooth and fair way to limit requests over time, avoiding the "burst" issues of fixed window counters.
2. **Redis Storage**: We use Redis for its extremely low latency and high-performance in-memory storage, which is ideal for the frequent read/write operations required by rate limiting.
3. **Tiered Limits**: We've implemented different tiers of rate limits for different types of operations (e.g., a default of 100 requests per hour for discovery, and a more strict limit of 20 per hour for authorization tickets).
4. **Per-IP Enforcement**: Rate limits are enforced on a per-IP address basis, with support for `X-Forwarded-For` headers to identify clients behind proxies.
5. **Violation Logging**: All rate limit violations are logged for audit and security monitoring purposes.

## Consequences

* **System Stability**: Rate limiting protects the coordinator from being overwhelmed by a large number of requests, whether intentional or accidental.
* **Fairness**: It ensures that all users have fair access to the coordinator's resources.
* **Security**: It provides a layer of defense against distributed denial-of-service (DDoS) and brute-force attacks.
* **Performance**: Redis's high-speed operations minimize the latency overhead of checking rate limits on every request.
* **Infrastructure Dependency**: The system now requires a running Redis instance for rate limiting to function correctly.
* **Configuration**: The rate limit thresholds must be carefully tuned to provide adequate protection without being overly restrictive for legitimate users.
