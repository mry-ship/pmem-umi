---
id: 01M7WQ0XMVKTJ3SXDW3TM0G0PY
module: infra.Cli
entity: Doctor
kind: exclusion
status: active
supersedes: []
anchors:
- src/pmem/cli/doctor_cmd.py
revision: none
author: 1002378395@qq.com
note_date: '2026-11-20'
summary: 不要在 doctor 函数体内再次 import detect_vcs
applies: Windows/CPython 函数作用域
---
试过不行：在 _run_doctor_body 后半段 UMI 分支里 from pmem.vcs.detect import detect_vcs，会导致整函数把 detect_vcs 当局部变量，开头 vcs=detect_vcs(...) 直接 UnboundLocalError，doctor 崩溃。
应使用文件顶部已导入的 detect_vcs / FilesStorage。
