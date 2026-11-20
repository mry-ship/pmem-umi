# PMEM · Universal Memory Infrastructure（v0.1.0）

面向长期 AI Agent 的记忆、知识与上下文治理基础设施。

> 本仓库是**全新产品线的 v0.1.0**，不是上游 pmem 的后续小版本。  
> 可参考既有项目研发记忆工作流的经验，但产品定位、版本号与演进路线独立。

## 五个同时成立的目标

1. **隔离性**：先定归属，再谈相关；模型不能绕过 Scope。
2. **准确性**：推测 ≠ 事实；证据不足不进权威层。
3. **稳定性**：多次整理后含义不漂移；原始记录不可静默覆盖。
4. **连续性**：跨会话 / 模型 / Agent 依赖数据结构与规则。
5. **可恢复性**：合并错、删错、写错可追溯和回滚。

## 核心原则

> AI 可以提出修改记忆的建议，但不能直接获得修改权威知识的无限权限。

## 六层架构

| 层 | 职责 | 代码 |
|---|---|---|
| L6 Quality & Governance | Doctor / Health / 审计 / Recovery | `pmem/umi/governance.py` |
| L5 Knowledge Evolution | 修正、合并、版本、回滚 | `pmem/umi/versions.py` + EventLog |
| L4 Retrieval & Context | Safe Recall | `pmem/umi/safe_recall.py` |
| L3 Knowledge Spaces | Personal / Project / Team / Domain | `pmem/umi/space.py` + `profiles/` |
| L2 Immutable Record | 事件日志、版本、hash | `pmem/umi/events.py` |
| L1 Universal Memory Core | 协议与接口 | `pmem/umi/models.py` |

Memory Core 只提供通用基础设施，不解释领域语义；Knowledge Space / Profile 各自拥有规则、生命周期与检索边界。

## 信任生命周期

`Observation → Candidate → Validated → Authoritative`  
（另有 Rejected / Superseded / Archived）

- Observation：仅事件日志
- Candidate：默认可写入口（对应 `Entry.status=seed`）
- Validated / Authoritative：需证据与（权威时）显式授权
- **验证一条主张 ≠ 其推论自动成立**

## 数据三分

| 层 | 载体 | 规则 |
|---|---|---|
| 原始记录 | `.memory/umi/events.sqlite` | Append-only |
| 权威知识 | `.memory/entries/**/*.md` | 版本化更新，不静默覆盖 |
| 派生索引 | 现有 index 缓存 | 可删除重建 |

## 命令与 MCP（v0.1）

```bash
pmem umi record --module infra.Umi --entity Trust --kind decision --content "..." --trust candidate
pmem umi search --module infra.Umi "隔离"
pmem umi promote <id> --to validated --evidence user_confirm
pmem umi rollback <id> <version>
pmem umi governance
pmem umi recovery --enable|--disable
pmem umi eval
pmem umi profiles
```

MCP：`safe_search_memory`、`controlled_record_memory`（支持 `profile_id` / `layer` / `agent_id`，module 可空）、`promote_memory`、`rollback_memory`、`memory_governance`。

## 自动化风险等级

| 等级 | 操作 | 策略 |
|---|---|---|
| L1 | 去重建议、索引重建、格式整理 | 可自动 |
| L2 | 合并、修正、关系建立 | 审核后执行 |
| L3 | 权威决策、删除、跨项目迁移 | 必须授权（`--force`） |

## Profile（可插拔）

| Profile | 用途 | 默认模块 |
|---|---|---|
| personal | 个人偏好/习惯（不可外泄到项目） | personal.Prefs |
| project | 项目研发（最完整） | 现有 infra.* / feature.* |
| team | 团队规范/playbook | team.Norms |
| domain | 跨项目领域知识 | domain.Patterns |
| game / art / research / business / agent_workflow | 行业扩展 | 各自 bootstrap |

Memory / Knowledge / Spec 分层：`--layer memory|knowledge|spec`；**禁止 Memory 自动生成 Spec**。

```bash
pmem umi bootstrap                  # 登记 personal/team/domain 默认模块
pmem umi profiles --full            # 查看全部 Profile 规则
pmem umi record --profile personal --kind preference --entity X --content "..."
pmem umi cross --mode reference --source-id ... --source-profile domain --source-project ...
```

跨空间：`reference`（默认）/ `adaptation` / `copy`（需授权）；personal → 其他 Profile 默认拒绝。

## v0.1 范围

已具备：隔离骨架、信任/候选写入、事件版本与回滚、Safe Recall、治理审计、评测套件、**Personal/Team/Domain/行业扩展 Profile**、跨空间引用策略、Agent 权限策略。

后续：默认 MCP 入口强制 Safe Path、Report 四分册与标注版错误召回率、Adaptation 自动生成本地候选草稿。
