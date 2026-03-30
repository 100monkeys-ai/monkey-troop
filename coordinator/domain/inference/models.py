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


@dataclass
class Node:
    """A provider node in the inference network."""

    node_id: str
    tailscale_ip: str
    status: str  # "IDLE", "BUSY", "OFFLINE"
    models: List[str]
    hardware: HardwareSpec
    engines: List[EngineInfo]
    reputation_score: float = 0.5

    def to_json(self) -> str:
        # Pydantic is already used for DTOs; this is for Domain -> JSON conversion
        return json.dumps(
            {
                "node_id": self.node_id,
                "tailscale_ip": self.tailscale_ip,
                "status": self.status,
                "models": self.models,
                "hardware": {"gpu": self.hardware.gpu, "vram_free": self.hardware.vram_free_mb},
                "engines": [
                    {"type": e.type, "version": e.version, "port": e.port} for e in self.engines
                ],
                "reputation_score": self.reputation_score,
            }
        )

    @classmethod
    def from_dict(cls, data: dict) -> "Node":
        return cls(
            node_id=data["node_id"],
            tailscale_ip=data["tailscale_ip"],
            status=data["status"],
            models=data["models"],
            hardware=HardwareSpec(
                gpu=data["hardware"]["gpu"], vram_free_mb=data["hardware"]["vram_free"]
            ),
            engines=[EngineInfo(e["type"], e["version"], e["port"]) for e in data["engines"]],
            reputation_score=data.get("reputation_score", 0.5),
        )
