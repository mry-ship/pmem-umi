"""可插拔 Profile：定义知识类型、生命周期、验证与检索规则；引擎只执行规则。"""
from __future__ import annotations

from pmem.umi.profiles.base import (
    AgentPolicy,
    CrossSpacePolicy,
    LifecyclePolicy,
    Profile,
    all_profiles,
    get_profile,
    list_profiles,
    register_profile,
)
from pmem.umi.profiles import domain as _domain  # noqa: F401
from pmem.umi.profiles import personal as _personal  # noqa: F401
from pmem.umi.profiles import project as _project  # noqa: F401
from pmem.umi.profiles import team as _team  # noqa: F401
from pmem.umi.profiles.extensions import register_extensions

register_extensions()

__all__ = [
    "AgentPolicy",
    "CrossSpacePolicy",
    "LifecyclePolicy",
    "Profile",
    "all_profiles",
    "get_profile",
    "list_profiles",
    "register_profile",
    "register_extensions",
]
