"""UMI 运行时：聚合六大端口，业务层只拿 Runtime，不拿 MemoryService。"""
from __future__ import annotations

from dataclasses import dataclass

from pmem.umi.core.ports import (
    GovernanceEngine,
    KnowledgeRepository,
    MemoryRetriever,
    MemoryStore,
    SpaceManagerPort,
    TrustManager,
)


@dataclass
class UmiRuntime:
    store: MemoryStore
    retriever: MemoryRetriever
    knowledge: KnowledgeRepository
    trust: TrustManager
    spaces: SpaceManagerPort
    governance: GovernanceEngine
