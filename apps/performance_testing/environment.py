"""压测环境叠加：把「命名环境」应用到脚本配置上，实现一套脚本跨环境复跑。

叠加规则（返回新对象，不修改原 ``jmx_config``）：
- **base_url**：把各采样器 URL 的 ``scheme://host[:port]`` 替换为环境基础地址的 origin；
  若环境基础地址带路径前缀（如 ``https://api.example.com/v1``），则在采样器路径前补上该前缀
  （已包含则不重复补）。
- **variables**：环境变量按 ``name`` 覆盖脚本同名变量；脚本独有的变量保留。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit


def _env_origin(base_url: str) -> str:
    parts = urlsplit((base_url or "").strip())
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def _env_path_prefix(base_url: str) -> str:
    path = (urlsplit((base_url or "").strip()).path or "").rstrip("/")
    return path


def rewrite_url(url: str, base_url: str) -> str:
    """把 ``url`` 的 origin 换成 ``base_url`` 的 origin，并补上 base_url 的路径前缀。"""
    if not url:
        return url
    origin = _env_origin(base_url)
    if not origin:
        return url
    parts = urlsplit(url.strip())
    prefix = _env_path_prefix(base_url)
    if not parts.scheme or not parts.netloc:
        # 相对路径：直接挂到环境地址（含其路径前缀）后面
        base_parts = urlsplit(base_url.strip())
        tail = parts.path.lstrip("/")
        joined = f"{prefix}/{tail}" if (prefix and tail) else (prefix or f"/{tail}")
        return urlunsplit((base_parts.scheme, base_parts.netloc, joined, parts.query, parts.fragment))
    path = parts.path or ""
    if prefix and not path.startswith(prefix):
        path = f"{prefix}{path}"
    origin_parts = urlsplit(origin)
    return urlunsplit((origin_parts.scheme, origin_parts.netloc, path, parts.query, parts.fragment))


def merge_variables(script_variables: Optional[List[Dict[str, Any]]],
                    env_variables: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """合并变量：环境变量按 name 覆盖脚本同名变量（保持脚本原有顺序，新增项追加在后）。"""
    merged: List[Dict[str, Any]] = []
    env_by_name = {}
    for item in (env_variables or []):
        if isinstance(item, dict) and (item.get("name") or "").strip():
            env_by_name[item["name"].strip()] = item

    seen = set()
    for item in (script_variables or []):
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if name and name in env_by_name:
            merged.append({**item, **env_by_name[name]})
            seen.add(name)
        else:
            merged.append(item)
            if name:
                seen.add(name)
    for name, item in env_by_name.items():
        if name not in seen:
            merged.append(item)
    return merged


def build_effective_config(jmx_config: Optional[Dict[str, Any]], environment) -> Dict[str, Any]:
    """按环境叠加出「生效配置」。``environment`` 为空时原样返回（深拷贝）。"""
    config = copy.deepcopy(jmx_config or {})
    if environment is None:
        return config

    base_url = (getattr(environment, "base_url", "") or "").strip()
    env_headers = getattr(environment, "headers", None) or {}
    env_variables = getattr(environment, "variables", None) or []

    for thread_group in (config.get("thread_groups") or []):
        if not isinstance(thread_group, dict):
            continue
        if base_url:
            for sampler in (thread_group.get("samplers") or []):
                if isinstance(sampler, dict) and sampler.get("url"):
                    sampler["url"] = rewrite_url(sampler["url"], base_url)
        # 环境级全局请求头：按 header 名覆盖（脚本已有同名头则覆盖其值）
        if env_headers and isinstance(env_headers, dict):
            for sampler in (thread_group.get("samplers") or []):
                if not isinstance(sampler, dict):
                    continue
                headers = sampler.get("headers") or []
                by_name = {str(h.get("name", "")).strip().lower(): h for h in headers if isinstance(h, dict)}
                for hname, hvalue in env_headers.items():
                    key = str(hname).strip().lower()
                    if key in by_name:
                        by_name[key]["value"] = hvalue
                    else:
                        headers.append({"name": hname, "value": hvalue})
                sampler["headers"] = headers
        # 变量：环境覆盖脚本
        thread_group["variables"] = merge_variables(thread_group.get("variables"), env_variables)

    config["variables"] = merge_variables(config.get("variables"), env_variables)
    config["_environment"] = {
        "id": getattr(environment, "id", None),
        "name": getattr(environment, "name", ""),
        "base_url": base_url,
    }
    return config
