---
id: 01M7WQ0WN7MDKM6VCSTJ0BRXS5
module: infra.Service
entity: UmiOps
kind: decision
status: active
supersedes: []
anchors:
- src/pmem/service/umi_ops.py#UmiOps.controlled_record
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: 默认走 candidate_first，权威写入必须显式晋升
applies: umi.write_mode=candidate_first
---
为什么：用户要求不确定知识不得直接进权威层；
若 controlled_record 默认 active/validated，模型重试和自动整理会快速污染长期记忆。
排除：让模型自行判断是否权威（不可审计）。
选法：先写入 seed/candidate，经 promote_memory（证据+force_authoritative）再升 validated/authoritative；
同 op_id 先查幂等缓存再跑闸门，避免重复写入。
