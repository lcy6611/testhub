"""层次4：本地代码解析 —— 用 tree-sitter 把源码结构直接入谱（零 LLM 成本）。

解析目录下的 .py/.js/.ts/.tsx/.vue 文件，提取：
- 文件 / 类 / 函数(方法) 实体
- contains（文件→类/函数）、defines（类→方法）
- imports（文件→本地模块）、calls（函数→函数，文件内）
所有关系均为 EXTRACTED（字面 AST 读取），不消耗 token。
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db import transaction

from .constants import (
    CONF_LEVEL_EXTRACTED,
    ENTITY_CODE_CLASS,
    ENTITY_CODE_FILE,
    ENTITY_CODE_FUNCTION,
    ENTITY_CODE_MODULE,
    REL_CALLS,
    REL_CONTAINS,
    REL_DEFINES,
    REL_IMPORTS,
    SOURCE_SYSTEM,
)
from .models import KgEdge, kg_enabled
from .registry import ensure_entity

logger = logging.getLogger(__name__)

# tree-sitter 为可选依赖，未安装时模块仍可导入（parse_directory 会返回提示）
_HAVE_TS = False
_LANG_PY = _LANG_JS = _LANG_TS = _LANG_TSX = None
try:
    from tree_sitter import Language, Parser  # noqa: F401

    _HAVE_TS = True
except Exception as exc:  # pragma: no cover
    logger.warning("tree-sitter 未安装，代码解析不可用: %s", exc)

if _HAVE_TS:
    try:
        import tree_sitter_python as _ts_py

        _LANG_PY = Language(_ts_py.language())
    except Exception as exc:  # pragma: no cover
        logger.warning("tree-sitter-python 不可用: %s", exc)
    try:
        import tree_sitter_javascript as _ts_js

        _LANG_JS = Language(_ts_js.language())
    except Exception:  # pragma: no cover
        pass
    try:
        import tree_sitter_typescript as _ts_ts

        # 0.23+ 拆分为独立函数；旧版用 language_for_grammar_name
        if hasattr(_ts_ts, "language_typescript"):
            _LANG_TS = Language(_ts_ts.language_typescript())
            _LANG_TSX = Language(_ts_ts.language_tsx())
        else:  # pragma: no cover - 兼容旧版 API
            _LANG_TS = Language(_ts_ts.language_for_grammar_name("typescript"))
            _LANG_TSX = Language(_ts_ts.language_for_grammar_name("tsx"))
    except Exception:  # pragma: no cover
        pass

_EXT_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".vue": "typescript",
}

DEFAULT_EXTS = (".py", ".js", ".ts", ".tsx", ".vue")

_PARSERS: Dict[str, Any] = {}

# 解析时跳过的无关目录
_SKIP_DIRS = (".git", "node_modules", "__pycache__", ".venv", "venv", "media", "static", "dist", "build")


def _get_parser(lang_key: str):
    if not _HAVE_TS:
        return None
    if lang_key in _PARSERS:
        return _PARSERS[lang_key]
    mapping = {"python": _LANG_PY, "javascript": _LANG_JS, "typescript": _LANG_TS, "tsx": _LANG_TSX}
    lang = mapping.get(lang_key)
    if lang is None:
        return None
    try:
        parser = Parser(lang)
    except Exception:
        parser = Parser()
        parser.language = lang
    _PARSERS[lang_key] = parser
    return parser


def _field_name(node, field: str) -> Optional[str]:
    child = node.child_by_field_name(field)
    if child is not None and child.text is not None:
        return child.text.decode("utf-8", "replace")
    return None


def _callee_name(node) -> Optional[str]:
    fn = node.child_by_field_name("function")
    if fn is None:
        return None
    if fn.type == "identifier":
        return fn.text.decode("utf-8", "replace")
    if fn.type == "member_expression":
        prop = fn.child_by_field_name("property")
        if prop is not None:
            return prop.text.decode("utf-8", "replace")
    return None


def _py_import_modules(node) -> List[str]:
    text = node.text.decode("utf-8", "replace") if node.text else ""
    mods: List[str] = []
    m = re.match(r"\s*from\s+([\w\.]+)", text)
    if m:
        mods.append(m.group(1))
    m2 = re.match(r"\s*import\s+(.+)", text)
    if m2:
        for part in m2.group(1).split(","):
            part = part.strip().split(" as ")[0].strip()
            if part:
                mods.append(part)
    return mods


def _js_import_modules(node) -> List[str]:
    text = node.text.decode("utf-8", "replace") if node.text else ""
    mods = re.findall(r"from\s+['\"]([^'\"]+)['\"]", text)
    mods += re.findall(r"import\s+['\"]([^'\"]+)['\"]", text)
    return mods


def _extract_vue_script(content: str) -> str:
    m = re.search(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    return m.group(1) if m else content


def _collect(node, lang_key, classes, functions, imports, calls, class_stack, func_stack):
    t = node.type
    if lang_key == "python":
        if t == "class_definition":
            name = _field_name(node, "name")
            if name:
                classes.append(name)
                class_stack.append(name)
                for ch in node.children:
                    _collect(ch, lang_key, classes, functions, imports, calls, class_stack, func_stack)
                class_stack.pop()
                return
        if t == "function_definition":
            name = _field_name(node, "name")
            if name:
                parent = class_stack[-1] if class_stack else None
                functions.append((name, parent))
                func_stack.append(name)
                for ch in node.children:
                    _collect(ch, lang_key, classes, functions, imports, calls, class_stack, func_stack)
                func_stack.pop()
                return
        if t in ("import_statement", "import_from_statement"):
            for mod in _py_import_modules(node):
                imports.add(mod)
    else:
        if t == "class_declaration":
            name = _field_name(node, "name")
            if name:
                classes.append(name)
                class_stack.append(name)
                for ch in node.children:
                    _collect(ch, lang_key, classes, functions, imports, calls, class_stack, func_stack)
                class_stack.pop()
                return
        if t in ("function_declaration", "method_definition"):
            name = _field_name(node, "name")
            if name:
                parent = class_stack[-1] if class_stack else None
                functions.append((name, parent))
                func_stack.append(name)
                for ch in node.children:
                    _collect(ch, lang_key, classes, functions, imports, calls, class_stack, func_stack)
                func_stack.pop()
                return
        if t == "import_statement":
            for mod in _js_import_modules(node):
                imports.add(mod)
    if t == "call_expression":
        caller = func_stack[-1] if func_stack else None
        callee = _callee_name(node)
        if caller and callee:
            calls.append((caller, callee))
    for ch in node.children:
        _collect(ch, lang_key, classes, functions, imports, calls, class_stack, func_stack)


def _match(name: str, func_entities: Dict[str, Any]) -> Optional[Any]:
    if name in func_entities:
        return func_entities[name]
    for label, ent in func_entities.items():
        if label == name or label.endswith("." + name):
            return ent
    return None


def _code_link(src, dst, rel, project_id) -> int:
    if not src or not dst:
        return 0
    _, created = KgEdge.objects.update_or_create(
        src=src,
        dst=dst,
        relation_type=rel,
        defaults={
            "project_id": project_id,
            "source": SOURCE_SYSTEM,
            "confidence_level": CONF_LEVEL_EXTRACTED,
        },
    )
    return 1 if created else 0


def _build_graph_for_file(path, content, classes, functions, imports, calls, project_id, max_entities):
    counts = {"code_files": 0, "classes": 0, "functions": 0, "modules": 0, "edges": 0}
    file_key = f"code_file:{path}"
    file_ent = ensure_entity(
        file_key,
        ENTITY_CODE_FILE,
        label=os.path.basename(path),
        ref_app="code_parser",
        ref_id=path,
        project_id=project_id,
        properties={"path": path, "lines": content.count("\n") + 1},
    )
    if not file_ent:
        return counts
    counts["code_files"] = 1

    class_keys: Dict[str, Any] = {}
    for name in classes[:max_entities]:
        ckey = f"code_class:{path}:{name}"
        cent = ensure_entity(
            ckey, ENTITY_CODE_CLASS, label=name, ref_app="code_parser",
            ref_id=f"{path}::{name}", project_id=project_id,
            properties={"file": path},
        )
        if cent:
            counts["classes"] += 1
            class_keys[name] = cent
            counts["edges"] += _code_link(file_ent, cent, REL_CONTAINS, project_id)

    func_entities: Dict[str, Any] = {}
    for (name, parent) in functions[:max_entities]:
        fkey = f"code_func:{path}:{name}" if not parent else f"code_func:{path}:{parent}.{name}"
        label = name if not parent else f"{parent}.{name}"
        fent = ensure_entity(
            fkey, ENTITY_CODE_FUNCTION, label=label, ref_app="code_parser",
            ref_id=f"{path}::{label}", project_id=project_id,
            properties={"file": path, "parent_class": parent or ""},
        )
        if fent:
            counts["functions"] += 1
            func_entities[label] = fent
            if parent and parent in class_keys:
                counts["edges"] += _code_link(class_keys[parent], fent, REL_DEFINES, project_id)
            else:
                counts["edges"] += _code_link(file_ent, fent, REL_CONTAINS, project_id)

    # 仅保留相对导入（本地模块），避免第三方库噪声
    for mod in imports:
        if not mod.startswith("."):
            continue
        mkey = f"code_module:{mod}"
        ment = ensure_entity(
            mkey, ENTITY_CODE_MODULE, label=mod, ref_app="code_parser",
            ref_id=mod, project_id=project_id, properties={"module": mod},
        )
        if ment:
            counts["modules"] += 1
            counts["edges"] += _code_link(file_ent, ment, REL_IMPORTS, project_id)

    for (caller, callee) in calls:
        caller_ent = _match(caller, func_entities)
        callee_ent = _match(callee, func_entities)
        if caller_ent and callee_ent and caller_ent.pk != callee_ent.pk:
            counts["edges"] += _code_link(caller_ent, callee_ent, REL_CALLS, project_id)
    return counts


def parse_directory(
    root_path: str,
    *,
    project_id=None,
    extensions=DEFAULT_EXTS,
    max_files: int = 200,
    max_entities_per_file: int = 60,
) -> Dict[str, Any]:
    """解析目录下的代码文件并写入知识图谱。返回统计信息。"""
    if not kg_enabled():
        return {"detail": "知识图谱已禁用"}
    if not _HAVE_TS:
        return {
            "detail": "tree-sitter 未安装，请 pip install tree-sitter tree-sitter-python "
            "tree-sitter-javascript tree-sitter-typescript"
        }
    root_path = os.path.abspath(root_path)
    if not os.path.isdir(root_path):
        return {"detail": f"目录不存在: {root_path}"}

    stats = {
        "root": root_path,
        "files_scanned": 0,
        "files_parsed": 0,
        "code_files": 0,
        "classes": 0,
        "functions": 0,
        "modules": 0,
        "edges": 0,
        "errors": [],
    }

    candidates: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in extensions:
                candidates.append(os.path.join(dirpath, fn))
        if len(candidates) >= max_files:
            break
    candidates = candidates[:max_files]

    for path in candidates:
        stats["files_scanned"] += 1
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception as exc:
            stats["errors"].append(f"{path}: 读取失败 {exc}")
            continue
        ext = os.path.splitext(path)[1].lower()
        lang_key = _EXT_LANG.get(ext)
        if ext == ".vue":
            content = _extract_vue_script(content)
            lang_key = "typescript"
        parser = _get_parser(lang_key)
        if parser is None:
            continue
        try:
            tree = parser.parse(content.encode("utf-8"))
        except Exception as exc:
            stats["errors"].append(f"{path}: 解析失败 {exc}")
            continue
        classes: List[str] = []
        functions: List[Tuple[str, Optional[str]]] = []
        imports: Set[str] = set()
        calls: List[Tuple[str, str]] = []
        _collect(tree.root_node, lang_key, classes, functions, imports, calls, [], [])
        with transaction.atomic():
            result = _build_graph_for_file(
                path, content, classes, functions, imports, calls, project_id, max_entities_per_file
            )
        stats["files_parsed"] += 1
        stats["code_files"] += result["code_files"]
        stats["classes"] += result["classes"]
        stats["functions"] += result["functions"]
        stats["modules"] += result["modules"]
        stats["edges"] += result["edges"]

    return stats
