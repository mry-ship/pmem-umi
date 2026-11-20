"""为 Profile 登记默认模块（不覆盖已有模块）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pmem.umi.profiles.base import Profile, get_profile, list_profiles


def _load_modules_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": 1,
            "categories": {
                "feature": {"label": "业务功能"},
                "infra": {"label": "技术底座"},
                "personal": {"label": "个人"},
                "team": {"label": "团队"},
                "domain": {"label": "领域"},
                "art": {"label": "美术"},
                "research": {"label": "研究"},
                "business": {"label": "业务"},
                "agent": {"label": "Agent"},
            },
            "modules": {},
            "candidates": {},
            "synonyms": [],
            "entities": {},
            "third_party": [],
            "ignored": [],
        }
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("modules", {})
    data.setdefault("categories", {})
    return data


def ensure_profile_modules(root: Path | str, profile_id: str) -> dict[str, Any]:
    """把 Profile.bootstrap_modules 追加进 modules.yaml；已存在则跳过。"""
    root = Path(root).resolve()
    profile = get_profile(profile_id)
    path = root / ".memory" / "modules.yaml"
    data = _load_modules_yaml(path)
    modules: dict = data.setdefault("modules", {})
    categories: dict = data.setdefault("categories", {})
    added: list[str] = []
    for mid, glob in profile.bootstrap_modules:
        cat = mid.split(".", 1)[0]
        if cat not in categories:
            categories[cat] = {"label": cat}
        if mid in modules:
            continue
        modules[mid] = {"paths": [glob], "origin": f"profile:{profile.id}"}
        # 确保目录存在，便于后续落盘
        sample = root / glob.replace("/**", "").replace("**", "")
        sample.mkdir(parents=True, exist_ok=True)
        added.append(mid)
    if not profile.require_module and profile.default_module and profile.default_module not in modules:
        mid = profile.default_module
        cat = mid.split(".", 1)[0]
        if cat not in categories:
            categories[cat] = {"label": cat}
        modules[mid] = {"paths": [f"{cat}/**"], "origin": f"profile:{profile.id}"}
        (root / cat).mkdir(parents=True, exist_ok=True)
        added.append(mid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"ok": True, "profile": profile_id, "added": added, "modules_path": str(path)}


def ensure_all_core_profiles(root: Path | str) -> dict[str, Any]:
    results = []
    for pid in ("personal", "project", "team", "domain"):
        if pid in list_profiles():
            results.append(ensure_profile_modules(root, pid))
    return {"ok": True, "results": results}


def describe_profile(profile_id: str) -> dict[str, Any]:
    return get_profile(profile_id).as_dict()
