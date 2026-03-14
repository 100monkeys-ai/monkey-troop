# 12. Automated Deployment and Infrastructure Management

Date: 2026-03-14

## Status

Accepted

## Context

Managing a distributed system with multiple components (Coordinator, Headscale, Worker, Caddy, PostgreSQL, Redis) across various environments can be complex and error-prone. We need a way to automate the setup, deployment, and management of these components to ensure consistency, reliability, and ease of use.

## Decision

We have implemented a **multi-layered automation strategy** for deployment and infrastructure management.

1.  **Orchestration Scripts**: We've created a central `install-coordinator.sh` script and several supporting scripts (e.g., `setup-headscale.sh`, `setup-coordinator-stack.sh`, `setup-caddy.sh`) to automate the entire setup process for the coordinator.
2.  **Docker Compose**: We use Docker Compose (`docker-compose.coordinator.yml`, `docker-compose.worker.yml`) to containerize and orchestrate the core services (Coordinator, PostgreSQL, Redis), ensuring consistent environments across different hosts.
3.  **Systemd Integration**: For host-level management, we use Systemd service files to manage the lifecycle of the coordinator stack, Headscale, and backup tasks, providing auto-restart and dependency management.
4.  **Caddy for Reverse Proxy**: We use Caddy for automated TLS/SSL certificate management and routing at the coordinator's edge, simplifying secure access to the API and Headscale.
5.  **Backup Automation**: We've implemented automated PostgreSQL backups with rolling retention using a dedicated Systemd service and timer.
6.  **Configuration Templates**: We use templates for configuration files (e.g., `Caddyfile`, `headscale.yaml`) to allow for dynamic customization during the installation process.

## Consequences

*   **Ease of Use**: A one-command installation process makes it easy for users to set up their own Monkey Troop coordinator.
*   **Consistency**: Automation ensures that the system is configured identically across different environments, reducing "it works on my machine" issues.
*   **Reliability**: Systemd and Docker Compose provide robust mechanisms for managing service lifecycles and handling failures.
*   **Scalability**: The modular approach makes it easier to scale individual components or migrate to more complex orchestration tools (like Kubernetes) in the future.
*   **Maintenance**: Automated backups and systemd-managed services reduce the operational overhead of running the coordinator.
*   **Complexity**: Maintaining a suite of automation scripts and configuration templates adds to the project's maintenance burden.
*   **Host-Level Dependencies**: Some automation tasks (like setting up Headscale and Systemd services) require specific host-level permissions and dependencies.
