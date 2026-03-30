"""Domain models for the Inference Orchestration context."""

import json
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class HardwareSpec:
    gpu: str
    vram_free_mb: int


@dataclass(frozen=True)
class EngineInfo:
    type: str
    version: str
    port: int


@dataclass(frozen=True)
class ModelIdentity:
    """Content-addressed model identity ensuring integrity via cryptographic hash."""

    name: str
    content_hash: str
    size_bytes: int


@dataclass
class Node:
    """A provider node in the inference network."""

    node_id: str
    tailscale_ip: str
    status: str  # "IDLE", "BUSY", "OFFLINE"
    models: List[ModelIdentity]
    hardware: HardwareSpec
    engines: List[EngineInfo]

    def to_json(self) -> str:
        # Pydantic is already used for DTOs; this is for Domain -> JSON conversion
        return json.dumps(
            {
                "node_id": self.node_id,
                "tailscale_ip": self.tailscale_ip,
                "status": self.status,
                "models": [
                    {
                        "name": m.name,
                        "content_hash": m.content_hash,
                        "size_bytes": m.size_bytes,
                    }
                    for m in self.models
                ],
                "hardware": {"gpu": self.hardware.gpu, "vram_free": self.hardware.vram_free_mb},
                "engines": [
                    {"type": e.type, "version": e.version, "port": e.port} for e in self.engines
                ],
            }
        )

    @classmethod
    def from_dict(cls, data: dict) -> "Node":
        return cls(
            node_id=data["node_id"],
            tailscale_ip=data["tailscale_ip"],
            status=data["status"],
            models=[
                ModelIdentity(
                    name=m["name"],
                    content_hash=m["content_hash"],
                    size_bytes=m["size_bytes"],
                )
                for m in data["models"]
            ],
            hardware=HardwareSpec(
                gpu=data["hardware"]["gpu"], vram_free_mb=data["hardware"]["vram_free"]
            ),
            engines=[EngineInfo(e["type"], e["version"], e["port"]) for e in data["engines"]],
        )
