"""知识图谱实体与关系类型常量。"""

ENTITY_PROJECT = "Project"
ENTITY_REQUIREMENT_DOCUMENT = "RequirementDocument"
ENTITY_GENERATION_TASK = "TestCaseGenerationTask"
ENTITY_TEST_CASE = "TestCase"
ENTITY_KB_FUNCTION = "KbFunction"
ENTITY_KB_DOCUMENT = "KbDocument"
ENTITY_KB_DATASET = "KbDataset"
ENTITY_KB_CHAT_SESSION = "KbChatSession"
ENTITY_BUSINESS_REQUIREMENT = "BusinessRequirement"
ENTITY_API_REQUEST = "ApiRequest"
ENTITY_UI_PAGE = "UiPageObject"
ENTITY_FUNCTION_POINT = "FunctionPoint"
ENTITY_CODE_FILE = "CodeFile"
ENTITY_CODE_CLASS = "CodeClass"
ENTITY_CODE_FUNCTION = "CodeFunction"
ENTITY_CODE_MODULE = "CodeModule"
# 自建知识中枢（NativeKb）
ENTITY_NATIVE_KB = "NativeKb"
ENTITY_NATIVE_KB_DOCUMENT = "NativeKbDocument"

REL_BELONGS_TO = "belongs_to"
REL_DERIVED_FROM = "derived_from"
REL_USED_REFERENCE = "used_reference"
REL_PROVENANCE = "provenance"
REL_COVERS = "covers"
REL_MAPS_TO = "maps_to"
REL_REFERENCES = "references"
REL_DEPENDS_ON = "depends_on"
REL_RELATED = "related"
REL_IMPACTS = "impacts"
REL_AUTOMATES = "automates"
REL_CONTAINS = "contains"
REL_SIMILAR_TO = "similar_to"
REL_DEFINES = "defines"
REL_IMPORTS = "imports"
REL_CALLS = "calls"

SOURCE_SYSTEM = "system"
SOURCE_MANUAL = "manual"
SOURCE_AI = "ai_suggested"

# 置信度等级（对齐 Graphify 的 EXTRACTED / INFERRED / AMBIGUOUS）
CONF_LEVEL_EXTRACTED = "EXTRACTED"
CONF_LEVEL_INFERRED = "INFERRED"
CONF_LEVEL_AMBIGUOUS = "AMBIGUOUS"
CONFIDENCE_LEVEL_CHOICES = [
    (CONF_LEVEL_EXTRACTED, "字面提取"),
    (CONF_LEVEL_INFERRED, "推断"),
    (CONF_LEVEL_AMBIGUOUS, "歧义"),
]
