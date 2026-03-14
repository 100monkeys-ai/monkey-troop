# 14. Trusted Execution Environments (TEE) for Worker Nodes

Date: 2026-03-14

## Status

Accepted

## Context

Even with end-to-end encryption (E2E), the worker node must decrypt the prompt to perform inference. This means the model weights and inference results are processed in the host node's RAM, potentially leaving them vulnerable to a malicious host administrator who can access the system's memory.

## Decision

We propose supporting **Trusted Execution Environments (TEE)** for worker inference.

1.  **Hardware Isolation**: Worker nodes with compatible hardware (e.g., NVIDIA Confidential Computing, Intel SGX, AMD SEV) will run the inference engine within a secure enclave.
2.  **Memory Encryption**: The enclave will use hardware-level memory encryption to prevent the host OS or any other process from reading the data within the enclave's memory.
3.  **Remote Attestation**: The client will perform remote attestation to verify that the worker is indeed running the inference engine within a genuine, untampered TEE.
4.  **Secure Key Provisioning**: Keys for E2E encryption will be provisioned directly into the TEE, ensuring they are never exposed to the host OS.

## Consequences

*   **Security**: Hardware-level isolation provides the highest possible level of security for inference data and model weights.
*   **Trust**: Users can trust the hardware-enforced isolation, even if they don't trust the worker node's owner.
*   **Performance**: TEEs can introduce a performance penalty due to memory encryption and enclave entry/exit overhead.
*   **Hardware Availability**: TEE support is limited to specific high-end CPUs and GPUs, reducing the pool of eligible worker nodes.
*   **Complexity**: Implementing remote attestation and secure enclave management is highly complex and hardware-specific.
