---
id: 01M7WSTTQ1K0N1D8E1RJ6MDA7Z
module: infra.Cli
entity: Doctor
kind: conclusion
status: active
supersedes: []
anchors: []
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: doctor line() 已计数，UMI 段勿再手动加减 problems/warnings
applies: 改 doctor UMI 段时
---
根因：line(BAD/WARN) 内部已 problems/warnings += 1；
UMI recovery/critical/跳过分支再手动累加会双计。
入口：src/pmem/cli/doctor_cmd.py 的 _run_doctor_body。
