---
id: 01M7WQCD0D8EPT6RRV5G8Z1MNF
module: infra.Umi
entity: LoopCheck
kind: conclusion
status: archived
supersedes: []
anchors: []
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: 循环检查幂等写入探针
archived:
  'on': '2026-11-20'
  from: seed
  by: 1002378395@qq.com
trust:
  status: candidate
  verification: unverified
version: 1
content_sha256: 3fa0f5ec3618df847d206b67afec926662f1db18670db31c0b7f10f613f5af21
space:
  profile_id: project
  owner_id: ''
  project_id: Cursor-Pmem-Memory-Universal-Architecture
  module_id: infra.Umi
  entity_id: LoopCheck
provenance:
  source_type: conversation
  source_id: ''
  extracted_by: ''
  recorded_by: 1002378395@qq.com
---
循环检查：同一 op_id 重复受控写入必须返回已有结果，不能生成重复候选记忆污染库。
