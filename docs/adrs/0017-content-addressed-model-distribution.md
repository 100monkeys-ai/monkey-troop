# 17. Content-Addressed Model Distribution

Date: 2026-03-14

## Status

Accepted

## Context

In the current system, worker nodes manually download and manage their models (e.g., using `ollama pull`). There's no mechanism to verify that a model with a given name (e.g., `llama3:8b`) is identical across all nodes. A worker node could potentially "spoof" a model name, either accidentally or maliciously, which could lead to inconsistent or incorrect inference results.

## Decision

We propose implementing **Content-Addressed Model Distribution**.

1. **Global Model IDs**: Each model will be uniquely identified by a cryptographic hash of its content (e.g., its weights and configuration files), rather than just a human-readable name.
2. **Manifest-Based Discovery**: The coordinator will maintain a registry of human-readable model names and their corresponding content hashes.
3. **Hash Verification**: When a worker node downloads a model, it must verify the model's hash against the global registry.
4. **Client-Side Check**: When a client requests a model, it will specify the model's hash (or a name that the coordinator resolves to a hash). The worker must prove it's using the model with the requested hash.

## Consequences

* **Consistency**: Clients can be certain that the model they're using is identical across all worker nodes.
* **Integrity**: Content-addressing prevents model spoofing or accidental use of the wrong model version.
* **Efficiency**: Content-addressing can simplify model distribution and deduplication, especially when multiple models share common layers.
* **Complexity**: Implementing a hash-based model registry and verification system is more complex than a simple name-based system.
* **Infrastructure Dependency**: The system now requires a central registry of model hashes, though this can be decentralized (e.g., via IPFS).
* **Update Management**: Updating a model requires a new entry in the registry and a new content hash.
