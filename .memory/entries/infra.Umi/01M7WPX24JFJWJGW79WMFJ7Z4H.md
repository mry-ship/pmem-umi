---
id: 01M7WPX24JFJWJGW79WMFJ7Z4H
module: infra.Umi
entity: SafeRecall
kind: feature
status: active
supersedes: []
anchors:
- src/pmem/umi/safe_recall.py#SafeRecall.recall
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: Safe Recall 检索结果补全 module 字段
---
用户要求：safe_recall 返回的 items 必须带上 module；
若底层检索行缺 module，则从 Entry 回填，避免 disposition/allow 项模块名为空。
入口：pmem.umi.safe_recall.SafeRecall.recall。
