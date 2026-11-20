---
id: 01M7WSTPYTGE87GY1YQVDE5TFS
module: infra.Service
entity: UmiOps
kind: decision
status: active
supersedes: []
anchors: []
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: candidate_first 降级不以有无 evidence 为准
applies: umi.write_mode=candidate_first
---
为什么：Pass1 发现有 evidence 对象即可跳过 demote，validated+verified 可直达 active。
排除：用 evidence 有无当 promote 门闩（可被模型伪造）。
选法：candidate_first 下仅 promote=True 或（权威且 force_authoritative）可保留高信任，且写入/晋升都须至少一条 verified 证据。
