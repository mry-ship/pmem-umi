"""UMI Core 稳定数据类型：不依赖 pmem.Entry / Index / FilesStorage。

Adapter 负责与底层存储互转；业务逻辑只认这里的结构。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pmem.umi.models import KnowledgeClaim, Provenance, SpaceRef, TrustInfo


@dataclass
class MemoryRecord:
    """一条可读写的记忆/知识单元（UMI 视角）。"""

    id: str
    module: str
    entity: str
    kind: str
    content: str
    summary: str = ""
    status: str = "active"  # 底层可见性；信任以 trust 为准
    verified: bool = False
    trust: TrustInfo | None = None
    space: SpaceRef | None = None
    claim: KnowledgeClaim | None = None
    provenance: Provenance | None = None
    version: int = 0
    layer: str = "memory"
    profile_id: str = ""
    profile_kind: str = ""
    content_sha256: str = ""
    anchors: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    applies: str = ""
    when: dict[str, Any] = field(default_factory=dict)
    supersedes: list[str] = field(default_factory=list)
    source_conversation: str = ""
    author: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryHit:
    """检索命中：可无正文；Safe Recall 先看 disposition 再决定是否展开。"""

    id: str
    module: str
    entity: str = ""
    kind: str = ""
    summary: str = ""
    status: str = "active"
    verified: bool = False
    stale: bool = False
    conflict: bool = False
    trust: TrustInfo | None = None
    space: SpaceRef | None = None
    score: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrieveResult:
    ok: bool
    hits: list[MemoryHit] = field(default_factory=list)
    features: list[MemoryHit] = field(default_factory=list)
    error: str = ""
    code: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoreWrite:
    """写入意图：由 MemoryStore / KnowledgeRepository 执行，不暴露 Markdown 细节。"""

    module: str
    entity: str
    kind: str
    content: str
    summary: str = ""
    status: str = "seed"
    trust: TrustInfo | None = None
    space: SpaceRef | None = None
    claim: KnowledgeClaim | None = None
    provenance: Provenance | None = None
    layer: str = "memory"
    profile_id: str = ""
    profile_kind: str = ""
    anchors: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    applies: str = ""
    when: dict[str, Any] = field(default_factory=dict)
    supersedes: list[str] = field(default_factory=list)
    draft_id: str | None = None
    source_conversation: str | None = None
    op_id: str | None = None
    expected_version: int | None = None
