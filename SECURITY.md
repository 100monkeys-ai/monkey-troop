# Security Policy

## 1. Our Commitment

Monkey Troop takes the security of our distributed inference network and our users' data seriously. As a P2P compute network, maintaining the integrity of the Control Plane (Coordinator) and the privacy of the Data Plane (Worker/Client) is our top priority.

## 2. Supported Versions

We currently support and provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| v0.1.x  | :white_check_mark: |
| < v0.1  | :x:                |

## 3. Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a potential security vulnerability, please report it via one of the following channels:

- **Email**: <security@100monkeys.ai> (Response within 48 hours)
- **GitHub**: Private Security Advisory (preferred for documented exploits)

Please include:

- A detailed description of the vulnerability.
- Steps to reproduce the issue.
- Potential impact if exploited.

## 4. Security Mandates (from AGENTS.md)

All development on Monkey Troop must adhere to the following strict security standards:

- **JWT RSA Authentication**: All P2P traffic must be authorized via RSA-signed JWT tickets issued by the Coordinator (ADR-0005).
- **Data Plane Isolation**: The Coordinator must never see, log, or store raw inference data (Prompts/Completions).
- **E2E Encryption**: Inference data must be encrypted between the Client and the Worker (ADR-0013).
- **No Secrets**: API keys, private keys, and database credentials must never be committed to source control.
- **Audit Logging**: All sensitive control-plane actions must be recorded in the immutable audit log (ADR-0011).

## 5. Security Architecture

The system is designed with a strict separation of concerns using **Domain-Driven Design (DDD)**. Security logic is isolated within the `Security & Identity` bounded context, ensuring that authentication and authorization invariants are enforced consistently across the entire network.
