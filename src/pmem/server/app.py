from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from pmem.core.config import find_root

INSTRUCTIONS = (
    "项目研发记忆：按模块（category.Module）沉淀根因、排除项、决定与风险。"
    "改代码前用 search_memory（跨项目防污染用 safe_search_memory）按文件路径或模块查一次；"
    "写入优先 controlled_record_memory（默认进入 candidate，不直接污染权威知识），"
    "也可用 record_memory（UMI 开启且 candidate_first 时同样走受控写入）。"
    "改了模块就写一条功能记录（kind=feature，需求来源与必须保持的行为）；"
    "排除了某个方向、确认了根因、发现看代码看不出的约束或风险时另记一条教训。"
    "候选升权威用 promote_memory（需证据；权威还需 force_authoritative）；错写用 rollback_memory。"
)


def _dump(data: dict) -> str:
    # 来源标记：Cursor 传给 Hook 的工具名不带服务名，闸门靠它区分别家记忆服务的同名工具
    return json.dumps({**data, "server": "pmem"}, ensure_ascii=False, separators=(",", ":"))


def _workspace_folder_paths() -> list[str]:
    """Cursor 用户级 MCP 常在 Temp 启动，但会带 WORKSPACE_FOLDER_PATHS。"""
    raw = os.environ.get("WORKSPACE_FOLDER_PATHS") or ""
    out: list[str] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip().strip('"')
        if part and "${" not in part:
            out.append(part)
    return out


def resolve_root(raw: str | None) -> Path | None:
    """优先用 --root（忽略未被替换的 ${...} 变量），再环境变量与工作区路径，最后从 cwd 向上找 .memory。"""
    candidates: list[str | None] = [
        raw,
        os.environ.get("PMEM_ROOT"),
        os.environ.get("CLAUDE_PROJECT_DIR"),
        *_workspace_folder_paths(),
        os.getcwd(),
    ]
    for candidate in candidates:
        if candidate and "${" not in candidate:
            root = find_root(candidate)
            if root is not None:
                return root
    return None


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def build_server(root: Path | None) -> MCPServer:
    from pmem.core.config import CONFIG_FILE, MEMORY_DIR, ConfigError
    from pmem.service import MemoryService

    missing = {"ok": False, "error": "当前工作区还没有接入 pmem：请在项目根目录运行 pmem init"}
    holder: dict = {}
    # 框架在线程池里并发执行同步工具；索引、sqlite 连接、模型懒加载都不是线程安全的
    lock = threading.Lock()
    config_path = root / MEMORY_DIR / CONFIG_FILE if root is not None else None

    def call(action) -> str:
        if root is None:
            return _dump(missing)
        with lock:
            try:
                # 服务常驻：config.yaml 改了就整个重建，检索、写入、嵌入等设置下一次调用即生效
                stamp = _stamp(config_path)
                if "service" in holder and holder.get("stamp") != stamp:
                    holder.pop("service").close()
                if "service" not in holder:
                    holder["service"] = MemoryService(root, source="mcp")
                    holder["stamp"] = stamp
                return _dump(action(holder["service"]))
            except ConfigError as exc:
                return _dump({"ok": False, "error": f"pmem 配置有误：{exc}；改好后再调用即可，无需重启"})
            except Exception as exc:  # noqa: BLE001  未预料的错误也要带来源标记返回，闸门才认得出是 pmem 的结果
                return _dump({"ok": False, "error": f"pmem 内部错误：{type(exc).__name__}: {exc}"})

    server = MCPServer("pmem", instructions=INSTRUCTIONS)

    @server.tool()
    def search_memory(
        module: str = "",
        path: str = "",
        entity: str = "",
        query: str = "",
        limit: int = 0,
        as_of: str = "",
        full: bool = False,
        ids: list[str] | None = None,
        when: dict | None = None,
        source_conversation: str = "",
    ) -> str:
        """检索项目研发记忆。改代码前传 path（要改的文件）或 module（category.Module，子模块用点号续写，最多 4 段，
        如 system.Ads.AdMob；查子模块会带上上级模块的教训，查父模块会列出下级模块和各自最新的记忆标题）；entity 是模块内议题，可省；
        query 是关键词或问题描述（按同义词表展开），都不确定时只传 query 全局检索。as_of=YYYY-MM-DD 看那天有效的记忆；
        limit 不传按项目配置。ids=[...] 按 id 取全文，优先于其他参数；full=true 时本对话给过的也给全文。
        when：结构化适用条件过滤（如 {"platform":"android"}），需项目在 config.yaml 声明 facets；
        明确冲突的记忆排除，没写 when 的保留。返回 items（教训，全文）和 features（功能记录与规划，只有标题）；
        seen=true 的只给标题，要全文带 full=true；stale、applies、when 等字段见 *_hint。
        source_conversation 由系统填写，无需传。"""
        return call(lambda s: s.search(module or None, path or None, entity or None, query or None, limit,
                                       source_conversation or None, as_of or None, full=bool(full),
                                       ids=ids or None, when=when or None))

    @server.tool()
    def record_memory(
        module: str,
        entity: str,
        kind: str,
        content: str,
        supersedes: list[str] | None = None,
        anchors: list[str] | None = None,
        aliases: list[str] | None = None,
        summary: str = "",
        verify: str = "",
        applies: str = "",
        when: dict | None = None,
        enforced_by: list[str] | None = None,
        scope: str = "",
        draft_id: str = "",
        source_conversation: str = "",
    ) -> str:
        """记录一条研发记忆。kind：feature 功能记录（改了模块就写：需求来源、必须保持的行为、适用条件、入口）、
        plan 未实现的需求；教训 exclusion 排除的方向、conclusion 根因或坑、correction 推翻旧结论、risk 看代码看不出的约束、
        decision 方案取舍。module：category.Module（子模块用点号续写，最多 4 段）；结论写在适用的最高一层，
        对所有下级都成立的写到父模块；entity：模块内议题短名。
        content 自包含（现象、原因、证据、影响范围），不写“改了哪个方法”。summary：一句话结论或必须保持的行为（60 字内），
        摘要、Wiki 和去重后的检索只显示它。verify：怎么确认结论仍成立（命令、测试名、现象），结论和更正尽量填。
        applies：自由文字成立前提（120 字内）。when：结构化适用条件（如 {"platform":["android"]}），
        需项目在 config.yaml 声明 facets；能枚举的前提优先写 when。enforced_by：已由工程规则保障（路径#规则名）；
        规则文件改了会标需核实，摘要标「已由规则拦截」并靠后排。scope=project：编码、环境、跨模块约定这类全项目都会踩的坑。
        aliases：现象和术语的其他叫法（如 ["闪退", "崩溃"]），换说法也能搜到。
        anchors：相关代码，尽量写到函数（路径#函数名；只写文件时该文件任何改动都会标需核实），不填按本对话改过的文件补。
        supersedes：本模块（或其下级模块）里被推翻的旧结论、说同一件事的旧功能记录、已实现的规划（plan）的 id。
        同一任务再写同一模块时带上次返回的 draft_id 覆盖，没填的可选字段沿用原值。
        返回的 similar 是同议题已有记忆：重复或被推翻时带 draft_id 重写并填 supersedes。"""
        # 模型常给可选数组顺手填 []，且 draft_id 可能是闸门补的：空列表按“没传”处理，覆盖时沿用原值。
        # UMI candidate_first：默认走受控写入，避免 Agent 直接落 active/权威层。
        def _write(s):
            umi_on = s.umi_enabled() and s.write_mode() == "candidate_first"
            if umi_on:
                return s.controlled_record(
                    module, entity, kind, content,
                    summary=summary or None, trust_status="candidate",
                    supersedes=supersedes or None, anchors=anchors or None, aliases=aliases or None,
                    draft_id=draft_id or None, source_conversation=source_conversation or None,
                    applies=applies or None, when=when if when is not None else None,
                    verify=verify or None, scope=scope or None, enforced_by=enforced_by or None,
                )
            return s.record(module, entity, kind, content, supersedes or None, anchors or None,
                            draft_id or None, source_conversation or None, aliases or None,
                            summary=summary or None, scope=scope or None, verify=verify or None,
                            applies=applies or None, enforced_by=enforced_by or None,
                            when=when if when is not None else None)

        return call(_write)

    @server.tool()
    def confirm_memory(ids: list[str], source_conversation: str = "") -> str:
        """确认记忆仍然成立：对照关联代码核对过 stale=true 的记忆、结论依然正确时调用，核对日期记为今天，
        之后不再因更早的代码改动标为 stale，排序时也按核对日期计算新旧。已不成立的不要确认，改写 correction。"""
        return call(lambda s: s.confirm(ids, source_conversation or None))

    @server.tool()
    def memory_graph(module: str, entity: str = "") -> str:
        """查看模块的记忆图谱。只传 module：模块概览，列出各议题（现行/已被替代条数、首末日期、最新两条现行结论摘要）
        和相关模块（共享代码或正文提及），用于一次看清模块全貌；再传 entity：给出该议题的时间线（谁在哪天替代了谁）和相关模块。"""
        return call(lambda s: s.graph(module, entity or None))

    @server.tool()
    def list_modules(category: str = "") -> str:
        """列出项目的模块与记忆数量、常用议题、上级（parent）和下级（children）。不确定模块名时先调用它。"""
        return call(lambda s: {**s.list_modules(category or None), "project_root": str(s.root)})

    @server.tool()
    def safe_search_memory(
        module: str = "",
        path: str = "",
        entity: str = "",
        query: str = "",
        limit: int = 0,
        as_of: str = "",
        full: bool = False,
        ids: list[str] | None = None,
        when: dict | None = None,
        source_conversation: str = "",
    ) -> str:
        """Safe Recall：先硬隔离与信任过滤，再返回记忆。disposition=reference 仅作参考，不可当本项目事实；
        withheld / refusals 表示拒答或不适用。优先于普通 search_memory 用于跨项目防污染场景。"""
        return call(lambda s: s.safe_search(
            module=module or None, path=path or None, entity=entity or None, query=query or None,
            limit=limit or None, source_conversation=source_conversation or None, as_of=as_of or None,
            full=bool(full), ids=ids or None, when=when or None,
        ))

    @server.tool()
    def controlled_record_memory(
        module: str = "",
        entity: str = "",
        kind: str = "",
        content: str = "",
        summary: str = "",
        trust_status: str = "candidate",
        verification: str = "unverified",
        evidence: list[dict] | None = None,
        claim: dict | None = None,
        op_id: str = "",
        supersedes: list[str] | None = None,
        anchors: list[str] | None = None,
        applies: str = "",
        when: dict | None = None,
        draft_id: str = "",
        source_conversation: str = "",
        force_authoritative: bool = False,
        promote: bool = False,
        layer: str = "memory",
        profile_id: str = "",
        agent_id: str = "default",
    ) -> str:
        """受控写入：默认进入 candidate 暂存区，不直接污染权威知识。需要用户确认/代码验证后再 promote。
        module 可空（Personal/Team/Domain 等用 Profile 默认模块）。
        layer=memory|knowledge|spec；profile_id 指定 personal/project/team/domain…；
        agent_id 走 Profile Agent 权限。evidence 如 [{"evidence_type":"user_confirm","verified":true}]。
        op_id 保证幂等。candidate_first 下未经 promote 的 validated/authoritative 会降为 candidate；
        force_authoritative 仅在有明确授权时直达权威。AI 可提议，但不能获得无限修改权威知识的权限。"""
        return call(lambda s: s.controlled_record(
            module or "", entity, kind, content, summary=summary or None, trust_status=trust_status or "candidate",
            verification=verification or "unverified", evidence=evidence or None, claim=claim,
            op_id=op_id or None, supersedes=supersedes or None, anchors=anchors or None,
            applies=applies or None, when=when if when is not None else None, draft_id=draft_id or None,
            source_conversation=source_conversation or None,
            force_authoritative=bool(force_authoritative), promote=bool(promote),
            layer=layer or "memory", agent_id=agent_id or "default",
            profile_id=profile_id or None,
        ))

    @server.tool()
    def promote_memory(
        memory_id: str,
        to_status: str = "validated",
        evidence_type: str = "user_confirm",
        note: str = "",
        force_authoritative: bool = False,
    ) -> str:
        """将候选记忆晋升为 validated 或 authoritative。权威晋升必须 force_authoritative=true。"""
        evidence = [{"evidence_type": evidence_type or "user_confirm", "note": note or "", "verified": True}]
        return call(lambda s: s.promote_memory(
            memory_id, to_status=to_status or "validated", evidence=evidence,
            force_authoritative=bool(force_authoritative),
        ))

    @server.tool()
    def rollback_memory(memory_id: str, to_version: int) -> str:
        """回滚到指定历史版本（Event Log + Versioned Knowledge）。"""
        return call(lambda s: s.rollback_memory(memory_id, int(to_version)))

    @server.tool()
    def memory_governance() -> str:
        """UMI 治理审计：隔离、完整性、冲突、漂移、候选积压。发现严重问题时建议 Recovery Mode。"""
        return call(lambda s: s.governance_report())

    return server


def serve(raw_root: str | None, worker: bool = False) -> None:
    root = resolve_root(raw_root)
    config = _load_config(root)
    settings = (config.get("server") if config else None) or {}
    if worker or not settings.get("watchdog", True):
        build_server(root).run("stdio")
        return
    import sys

    from pmem.server.watchdog import DEFAULT_TIMEOUT, Watchdog

    command = [sys.executable, "-m", "pmem.cli.main", "serve", "--worker"]
    if root is not None:
        command += ["--root", str(root)]
    try:
        timeout = float(settings.get("request_timeout") or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT
    on_restart = None
    if config is not None:
        from pmem.metrics.events import log_event

        cache_dir = config.cache_dir
        on_restart = lambda kind, reason: log_event(cache_dir, "server_restart", kind=kind, reason=reason)
    Watchdog(command, sys.stdin.buffer, sys.stdout.buffer, timeout, on_restart).run()


def _load_config(root: Path | None):
    if root is None:
        return None
    from pmem.core.config import Config, ConfigError

    try:
        return Config.load(root)
    except (ConfigError, OSError, ValueError):
        return None
