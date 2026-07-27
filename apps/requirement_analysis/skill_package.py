"""Skill 技能包导入导出工具。

通用技能包格式 = 一个 .skill.zip，内部：
    manifest.json      # 结构化元数据 + 全部配置
    README.md          # 技能包说明文档
    prompt.md          # 通用系统提示词
    constraint.md      # 约束规则（可选）
    input/             # 输入示例
    assets/            # 资源文件（图标/截图等）
    references/        # 参考资料
    scripts/           # 脚本（预处理/后处理）
    resources/         # 团队模板 / 参考文档（可选）

也兼容纯 .json（单文件 manifest）导入导出。
"""
import io
import json
import os
import zipfile

MANIFEST_FORMAT = "testhub-skill"
MANIFEST_VERSION = "2.0"

# 可从 manifest 安全映射到模型字段的键
_MANIFEST_MODEL_KEYS = (
    "name", "description", "version", "author", "tags", "category",
    "skill_type", "icon", "system_prompt", "constraint_rules",
    "input_spec", "output_spec", "tools", "output_format", "is_active",
    "readme", "trigger_keywords",
)

# 包内目录与 SkillArtifact.artifact_type 的映射
_DIR_TO_TYPE = {
    "assets": "asset",
    "input": "input",
    "references": "reference",
    "scripts": "script",
}


def _file_kind(path: str) -> str:
    """根据路径前缀判断文件类型。"""
    lower = path.lower()
    for prefix, kind in _DIR_TO_TYPE.items():
        if lower.startswith(prefix + "/"):
            return kind
    return "other"


def build_manifest(skill) -> dict:
    """从 TestCaseSkill 实例构造 manifest 字典。"""
    manifest = {
        "format": MANIFEST_FORMAT,
        "format_version": MANIFEST_VERSION,
        "name": skill.name,
        "description": skill.description or "",
        "version": skill.version or "1.0",
        "author": getattr(skill, "author", "") or "",
        "tags": list(getattr(skill, "tags", []) or []),
        "category": skill.category or "general",
        "skill_type": skill.skill_type or "custom",
        "icon": skill.icon or "🎯",
        "system_prompt": skill.system_prompt or "",
        "constraint_rules": skill.constraint_rules or "",
        "input_spec": getattr(skill, "input_spec", {}) or {},
        "output_spec": getattr(skill, "output_spec", {}) or {},
        "tools": list(getattr(skill, "tools", []) or []),
        "output_format": skill.output_format or "markdown",
        "is_active": skill.is_active,
        "is_builtin": skill.is_builtin,
        "readme": getattr(skill, "readme", "") or "",
        "trigger_keywords": list(getattr(skill, "trigger_keywords", []) or []),
    }
    template_columns = list(getattr(skill, "template_columns", []) or [])
    if template_columns:
        manifest["template"] = {"columns": template_columns}
    return manifest


def _read_file_field(file_field):
    """安全读取 FileField 内容。"""
    if not file_field:
        return None
    try:
        file_field.open("rb")
        return file_field.read()
    finally:
        try:
            file_field.close()
        except Exception:
            pass


def build_skill_package(skill) -> bytes:
    """把 Skill 打包成 .skill.zip 的字节流。"""
    manifest = build_manifest(skill)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        if manifest.get("readme"):
            zf.writestr("README.md", manifest["readme"])
        if manifest.get("system_prompt"):
            zf.writestr("prompt.md", manifest["system_prompt"])
        if manifest.get("constraint_rules"):
            zf.writestr("constraint.md", manifest["constraint_rules"])

        # 包内文件：input / assets / references / scripts
        for artifact in skill.artifacts.all():
            path = artifact.path
            if artifact.file and not artifact.is_binary:
                data = _read_file_field(artifact.file)
                if data is not None:
                    zf.writestr(path, data)
            elif artifact.file and artifact.is_binary:
                data = _read_file_field(artifact.file)
                if data is not None:
                    zf.writestr(path, data)
            elif artifact.text_content:
                zf.writestr(path, artifact.text_content)

        # 模板等资源
        template_file = getattr(skill, "template_file", None)
        if template_file:
            data = _read_file_field(template_file)
            if data:
                fname = os.path.basename(template_file.name)
                zf.writestr(f"resources/{fname}", data)
    return buffer.getvalue()


def parse_skill_package(uploaded_file):
    """解析上传的 .zip 或 .json 技能包，返回 (manifest_dict, resources_dict, artifact_files)。

    resources_dict 形如 {"template": (filename, bytes)}（可选）。
    artifact_files 形如 [(path, bytes), ...]。
    """
    raw = uploaded_file.read()
    name = getattr(uploaded_file, "name", "") or ""
    is_zip = name.lower().endswith(".zip") or raw[:4] == b"PK\x03\x04"

    manifest = None
    resources = {}
    artifact_files = []

    if is_zip:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            # manifest：优先 manifest.json
            if "manifest.json" in zf.namelist():
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            # prompt.md / constraint.md / README.md 可补到 manifest
            if manifest is not None:
                if "prompt.md" in zf.namelist() and not manifest.get("system_prompt"):
                    manifest["system_prompt"] = zf.read("prompt.md").decode("utf-8")
                if "constraint.md" in zf.namelist() and not manifest.get("constraint_rules"):
                    manifest["constraint_rules"] = zf.read("constraint.md").decode("utf-8")
                if "README.md" in zf.namelist() and not manifest.get("readme"):
                    manifest["readme"] = zf.read("README.md").decode("utf-8")
            # 分类收集包内文件
            for item in zf.namelist():
                if item.endswith("/") or item == "manifest.json":
                    continue
                lower = item.lower()
                data = zf.read(item)
                if lower.startswith("resources/"):
                    base = os.path.basename(item)
                    if lower.endswith((".xlsx", ".xls", ".csv")):
                        resources["template"] = (base, data)
                elif lower.startswith("input/") or lower.startswith("assets/") or \
                        lower.startswith("references/") or lower.startswith("scripts/"):
                    artifact_files.append((item, data))
                elif lower == "readme.md":
                    pass  # 已合并到 manifest
                elif lower == "prompt.md":
                    pass
                elif lower == "constraint.md":
                    pass
    else:
        # 纯 JSON
        manifest = json.loads(raw.decode("utf-8"))

    if not isinstance(manifest, dict):
        raise ValueError("技能包 manifest 必须是 JSON 对象")

    # 兜底默认值
    manifest.setdefault("name", "")
    manifest.setdefault("skill_type", "custom")
    manifest.setdefault("output_format", "markdown")
    manifest.setdefault("category", "general")
    manifest.setdefault("tags", [])
    manifest.setdefault("tools", [])
    manifest.setdefault("input_spec", {})
    manifest.setdefault("output_spec", {})
    manifest.setdefault("readme", "")
    manifest.setdefault("trigger_keywords", [])
    return manifest, resources, artifact_files


def manifest_to_model_kwargs(manifest: dict, resources: dict, model_cls):
    """把 manifest + resources 转成 TestCaseSkill 模型字段 kwargs。"""
    kwargs = {}
    for key in _MANIFEST_MODEL_KEYS:
        if key in manifest:
            kwargs[key] = manifest[key]

    # 模板列：优先 manifest.template.columns，其次 resources 解析
    template_columns = None
    tpl = manifest.get("template")
    if isinstance(tpl, dict) and tpl.get("columns"):
        template_columns = list(tpl["columns"])

    # 处理模板文件资源
    template_file_obj = None
    if "template" in resources:
        fname, data = resources["template"]
        from django.core.files.base import ContentFile
        template_file_obj = ContentFile(data, name=fname)
        # 若无现成列定义，尝试解析
        if template_columns is None:
            try:
                from .views import _parse_template_columns
                template_columns = _parse_template_columns(type("F", (), {"read": lambda self: data, "name": fname})())
            except Exception:
                template_columns = []

    if template_columns is not None:
        kwargs["template_columns"] = template_columns

    return kwargs, template_file_obj


def save_artifact_files(skill, artifact_files):
    """把解包得到的文件保存为 SkillArtifact。"""
    if not artifact_files:
        return
    from django.core.files.base import ContentFile
    SkillArtifact = skill.artifacts.model
    # 清空旧 artifacts（re-import 语义）
    skill.artifacts.all().delete()
    for path, data in artifact_files:
        kind = _file_kind(path)
        is_binary = not data.startswith(b'\xef\xbb\xbf') and b'\x00' in data[:1024]
        artifact = SkillArtifact(
            skill=skill,
            artifact_type=kind,
            path=path,
            is_binary=is_binary,
        )
        if is_binary:
            artifact.file.save(os.path.basename(path), ContentFile(data), save=False)
        else:
            try:
                artifact.text_content = data.decode("utf-8")
            except UnicodeDecodeError:
                artifact.file.save(os.path.basename(path), ContentFile(data), save=False)
        artifact.save()
