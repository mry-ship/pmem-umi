---
id: 01M7WSTZ2EG6G9YR4Q90ABKJX5
module: infra.Umi
entity: SafeRecall
kind: conclusion
status: active
supersedes: []
anchors: []
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: as_dict 必须在 payload 展开后强制写 module
applies: 改 Safe Recall 序列化时
---
根因：payload 若带空/错 module 会覆盖 RecallItem.module。入口：src/pmem/umi/safe_recall.py RecallResult.as_dict。
