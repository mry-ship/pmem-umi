---
id: 01M7WPV86ERHWVGTMMVR3B19HB
module: infra.Umi
entity: Architecture
kind: decision
status: active
supersedes: []
anchors: []
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: UMI 以现有 pmem 演变，不推倒重做
trust:
  status: validated
  verification: verified
  evidence:
  - evidence_type: user_confirm
    source_id: ''
    note: 架构决策已确认并落地到本仓库
    verified: true
  confidence_note: ''
version: 2
content_sha256: efbabf892df8fb4a6de3b1c117d29f4fb60b3a2528a2f55b667c6c27920d208a
space:
  profile_id: project
  owner_id: ''
  project_id: Cursor-Pmem-Memory-Universal-Architecture
  module_id: infra.Umi
  entity_id: Architecture
provenance:
  source_type: conversation
  source_id: ''
  extracted_by: ''
  recorded_by: 1002378395@qq.com
---
Universal Memory Infrastructure 在现有 pmem 的 Memory/Spec/Doctor/Health/Report 上演进：新增 Space Manager、Trust&Evidence、Version&Evolution、Safe Retrieval；
AI 可提议修改但不能无限修改权威知识；
默认 Candidate 写入，权威需证据与授权。
