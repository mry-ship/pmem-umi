"""底层适配器：当前仅 pmem；未来可增 sqlite / 远端等实现而不改 UMI 业务。"""
from __future__ import annotations

from pmem.umi.adapters.pmem import PmemAdapter, build_pmem_runtime

__all__ = ["PmemAdapter", "build_pmem_runtime"]
