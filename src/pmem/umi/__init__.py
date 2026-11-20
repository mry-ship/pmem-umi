"""Universal Memory Infrastructure：在现有 pmem 上演进的隔离、信任、版本与安全召回底座。

设计原则（不可由模型自行绕过）：
1. 隔离优先：先定归属，再谈相关
2. 原始记录不可覆盖：修正走新版本 / 新事件
3. 不确定不进权威记忆
4. 检索宁缺毋滥（Safe Recall）
5. 所有演化可审计、可回滚
6. 质量持续验证
"""
from __future__ import annotations

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
    "KnowledgeClaim",
    "Provenance",
    "SpaceContext",
    "SpaceManager",
    "SpaceRef",
    "TrustInfo",
    "WriteOpId",
]
