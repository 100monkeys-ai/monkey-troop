# 11. Audit Logging

Date: 2026-03-14

## Status

Accepted

## Context

For security, compliance, and debugging purposes, we need to maintain a clear record of important events within the Monkey Troop network. This includes authentication attempts, credit transactions, rate limit violations, and security-related incidents.

## Decision

We have implemented a **dual-layered audit logging** system in the coordinator.

1.  **File-Based Logging**: All audit events are written to a local log file in a structured JSON format. This provides a durable and easily accessible record for local analysis and backup.
2.  **Database-Backed Logging (PostgreSQL)**: Audit events are also stored in a dedicated `audit_logs` table in the PostgreSQL database. This allows for complex querying, filtering, and analysis of events over time.
3.  **JSONB for Flexibility**: The `details` field in the database table uses the JSONB data type, providing flexibility to store event-specific data without a fixed schema.
4.  **Admin Interface**: We've created an admin API endpoint (protected by HTTP Basic Auth) to allow authorized users to query and view the audit logs.
5.  **Event Categorization**: Events are categorized (e.g., "authorization", "transaction", "rate_limit", "security") to simplify filtering and reporting.

## Consequences

*   **Observability**: Audit logging provides excellent visibility into the system's operation and security state.
*   **Compliance**: The dual-layered approach meets many common security and compliance requirements for audit trails.
*   **Debuggability**: Structured logs make it much easier to diagnose issues and trace the sequence of events leading up to a problem.
*   **Security**: Logging security events helps identify and respond to potential attacks or unauthorized activities.
*   **Storage Overhead**: Storing logs in both files and the database increases storage requirements, which must be managed through rotation and retention policies.
*   **Performance**: While logging is typically fast, frequent database writes could potentially impact performance under extremely high load. We mitigate this through efficient indexing and asynchronous operations where possible.
