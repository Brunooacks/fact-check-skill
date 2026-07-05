"""Identidade de agente — manifesto assinável e portável.

Cada agente carrega uma identidade declarativa (quem é, o que pode fazer, que
dados pode tocar, qual seu nível de risco). O manifesto é o que se apresenta a
uma plataforma de governança no momento do registro.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List

import yaml

# Namespace fixo para derivar agent_ids estáveis a partir do nome.
_AGENT_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00cf4fc964ff")


@dataclass
class AgentIdentity:
    """Identidade declarativa de um agente."""

    name: str
    role: str
    description: str = ""
    version: str = "0.1.0"
    owner: str = "unknown"
    contact: str = ""
    risk_tier: str = "medium"  # low | medium | high
    capabilities: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    data_scopes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Preenchidos em runtime.
    agent_id: str = ""
    instance_id: str = ""

    def __post_init__(self) -> None:
        # agent_id estável = derivado do nome (a menos que sobrescrito por env).
        env_id = os.getenv("AGENT_ID")
        if env_id:
            self.agent_id = env_id
        elif not self.agent_id:
            self.agent_id = str(uuid.uuid5(_AGENT_NAMESPACE, self.name))
        # instance_id = único por boot (rastreia esta execução específica).
        if not self.instance_id:
            self.instance_id = uuid.uuid4().hex

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AgentIdentity":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        allowed = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in data.items() if k in allowed}
        return cls(**clean)

    def to_manifest(self) -> dict:
        """Manifesto público — o que se envia à plataforma de governança."""
        return asdict(self)
