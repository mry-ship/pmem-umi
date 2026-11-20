"""Universal Memory Infrastructure：通用记忆基础设施。

设计原则（不可由模型自行绕过）：
1. 隔离优先：先定归属，再谈相关
2. 原始记录不可覆盖：修正走新版本 / 新事件
3. 不确定不进权威记忆
4. 检索宁缺毋滥（Safe Recall）
5. 所有演化可审计、可回滚
6. 质量持续验证

演进原则：pmem 是技术起点，不是永远的技术依赖。
业务依赖 umi.core 端口；pmem 实现放在 umi.adapters。
"""
from __future__ import annotations

from pmem.umi.core import (
    GovernanceEngine,
    KnowledgeRepository,
    MemoryHit,
    MemoryRecord,
    MemoryRetriever,
    MemoryStore,
    SpaceManagerPort,
    TrustManager,
)
from pmem.umi.core.runtime import UmiRuntime
from pmem.umi.models import (
    TRUST_STATUSES,
    Evidence,
    KnowledgeClaim,
    Provenance,
    SpaceRef,
    TrustInfo,
    WriteOpId,
)
from pmem.umi.space import SpaceContext, SpaceManager

__all__ = [
    "TRUST_STATUSES",
    "Evidence",
    "GovernanceEngine",
    "KnowledgeClaim",
    "KnowledgeRepository",
    "MemoryHit",
    "MemoryRecord",
    "MemoryRetriever",
    "MemoryStore",
    "Provenance",
    "SpaceContext",
    "SpaceManager",
    "SpaceManagerPort",
    "SpaceRef",
    "TrustInfo",
    "TrustManager",
    "UmiRuntime",
    "WriteOpId",
]
