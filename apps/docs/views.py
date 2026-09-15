import logging
import os

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# 文档根目录：项目根下的 docs/docs-center（容器内即 /app/docs/docs-center）
DOCS_ROOT = os.path.join(settings.BASE_DIR, "docs", "docs-center")


def _safe_join(root, rel_path):
    """把相对路径安全拼到 root 下，防止 ../ 目录穿越。"""
    rel_path = (rel_path or "").replace("\\", "/")
    target = os.path.normpath(os.path.join(root, rel_path))
    root_norm = os.path.normpath(root)
    if target != root_norm and not target.startswith(root_norm + os.sep):
        return None
    return target


def _extract_title(file_path, fallback):
    """取文件首行 # 标题；取不到则回退文件名（去扩展名）。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("#"):
                    title = stripped.lstrip("#").strip()
                    return title or fallback
                if stripped:
                    break
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取标题失败 %s: %s", file_path, exc)
    return fallback


def _build_tree(root, current=""):
    """递归构造目录树：dir 节点含 children，file 节点含 title。"""
    abs_current = os.path.join(root, current) if current else root
    try:
        names = os.listdir(abs_current)
    except OSError:
        return []

    dirs = []
    files = []
    for name in names:
        if name.startswith(".") or name.startswith("_"):
            continue
        abs_path = os.path.join(abs_current, name)
        rel_path = os.path.join(current, name) if current else name
        rel_path = rel_path.replace(os.sep, "/")
        if os.path.isdir(abs_path):
            dirs.append({
                "type": "dir",
                "name": name,
                "path": rel_path,
                "children": _build_tree(root, rel_path),
            })
        elif name.lower().endswith(".md"):
            files.append({
                "type": "file",
                "name": name,
                "title": _extract_title(abs_path, name),
                "path": rel_path,
            })

    dirs.sort(key=lambda x: x["name"])
    files.sort(key=lambda x: x["name"])
    return dirs + files


class DocTreeView(APIView):
    """GET /api/docs/tree/ —— 返回 docs-center 下的目录树。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not os.path.isdir(DOCS_ROOT):
            logger.warning("文档根目录不存在: %s", DOCS_ROOT)
            return Response({"tree": [], "root_exists": False})
        tree = _build_tree(DOCS_ROOT)
        return Response({"tree": tree, "root_exists": True})


class DocContentView(APIView):
    """GET /api/docs/content/?path=xxx.md —— 返回单篇 md 原始文本。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rel_path = (request.query_params.get("path") or "").strip()
        if not rel_path:
            return Response(
                {"detail": "缺少 path 参数"}, status=status.HTTP_400_BAD_REQUEST
            )

        abs_path = _safe_join(DOCS_ROOT, rel_path)
        if not abs_path or not abs_path.lower().endswith(".md") or not os.path.isfile(abs_path):
            return Response(
                {"detail": "文档不存在"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:  # noqa: BLE001
            logger.error("读取文档失败 %s: %s", abs_path, exc)
            return Response(
                {"detail": f"读取失败: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            "path": rel_path,
            "title": _extract_title(abs_path, os.path.basename(abs_path)),
            "content": content,
        })
