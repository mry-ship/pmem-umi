"""UMI Core 端口：稳定接口，业务只依赖 Protocol，不依赖 pmem 内部类型。

边界（必须坚持）：
- 存储 / 检索 / 事件 / 版本 / 权限 → UMI Core（本文件 + types）
- 项目模块、代码映射、Spec、研发拦截 → pmem（Adapter 之外）
- 记忆策略、信任规则、治理策略 → Profile / Policy

原则：pmem 是 UMI 的技术起点，不是永远的技术依赖。
换底层时只换 Adapter，不重写 UMI 业务逻辑。
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pmem.umi.core.types import MemoryRecord, RetrieveResult
from pmem.umi.models import SpaceRef, TrustInfo
from pmem.umi.space import SpaceContext, SpaceManager


@runtime_checkable
class MemoryStore(Protocol):
    """原始/工作记忆的读写面：按 id 取、列举、落盘元数据与正文。"""

    def get(self, memory_id: str) -> MemoryRecord | None: ...

    def list(
        self,
        *,
        module: str | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[MemoryRecord]: ...

    def save(self, record: MemoryRecord) -> MemoryRecord: ...


@runtime_checkable
class MemoryRetriever(Protocol):
    """检索面：返回命中，不解释领域语义；Safe Recall 在其上做隔离与信任过滤。"""

    def search(
        self,
        *,
        module: str | None = None,
        path: str | None = None,
        entity: str | None = None,
        query: str | None = None,
        limit: int | None = None,
        when: dict | None = None,
        as_of: str | None = None,
        full: bool = False,
        ids: list[str] | None = None,
        source_conversation: str | None = None,
    ) -> RetrieveResult: ...


@runtime_checkable
class KnowledgeRepository(Protocol):
    """权威知识版本库：提交新版本、回滚、读历史；append-only 事件由实现保证。"""

    def commit(
        self,
        memory_id: str,
        content: str,
        *,
        trust: TrustInfo,
        meta: dict[str, Any],
        actor: str,
        space_key: str,
        op_id: str,
        event_type: str = "updated",
        expected_version: int | None = None,
    ) -> Any: ...

    def rollback(
        self,
        memory_id: str,
        to_version: int,
        *,
        actor: str,
        space_key: str,
        op_id: str,
    ) -> Any: ...

    def latest_version(self, memory_id: str) -> int: ...


@runtime_checkable
class TrustManager(Protocol):
    """信任与证据：解析、晋升风险、召回处置；规则可来自 Profile，不写死在存储层。"""

    def parse(self, record: MemoryRecord) -> TrustInfo: ...

    def disposition(self, trust: TrustInfo) -> str: ...

    def promotion_risk(
        self, trust_status: str, *, is_spec: bool = False, is_decision: bool = False
    ) -> str: ...


@runtime_checkable
class SpaceManagerPort(Protocol):
    """空间隔离：当前空间、可写断言、跨空间校验。"""

    project_id: str

    def current(self, *, profile: str | None = None, module_id: str = "", entity_id: str = "") -> SpaceRef: ...

    def context(
        self,
        *,
        profile: str | None = None,
        module_id: str = "",
        entity_id: str = "",
        agent_id: str = "",
        user_id: str = "",
        recovery_mode: bool = False,
    ) -> SpaceContext: ...


@runtime_checkable
class GovernanceEngine(Protocol):
    """治理审计：隔离 / 完整性 / 冲突 / 漂移 / 候选；不擅自改权威知识。"""

    def report(
        self,
        records: list[MemoryRecord],
        *,
        spaces: SpaceManager | SpaceManagerPort,
        recovery_mode: bool = False,
        doctor_checks: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, Any]: ...
