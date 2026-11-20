"""UMI Core：端口与稳定类型。业务依赖本包，不依赖 pmem.Entry。"""
from __future__ import annotations

from pmem.umi.core.ports import (
    GovernanceEngine,
    KnowledgeRepository,
    MemoryRetriever,
    MemoryStore,
    SpaceManagerPort,
    TrustManager,
)
from pmem.umi.core.types import MemoryHit, MemoryRecord, RetrieveResult, StoreWrite

__all__ = [
    "GovernanceEngine",
    "KnowledgeRepository",
    "MemoryHit",
    "MemoryRecord",
    "MemoryRetriever",
    "MemoryStore",
    "RetrieveResult",
    "SpaceManagerPort",
    "StoreWrite",
    "TrustManager",
]
