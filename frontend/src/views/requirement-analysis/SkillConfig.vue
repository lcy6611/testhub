<template>
  <div class="skill-config">
    <div class="page-header">
      <div class="header-left">
        <h2>Skill 技能配置</h2>
        <p class="subtitle">技能包 = 系统提示词 + 约束规则 + 结构化元数据（输入/输出规范、工具、标签），支持导入导出为通用 .skill.zip</p>
      </div>
      <div class="header-actions">
        <el-upload
          ref="importUploadRef"
          :auto-upload="false"
          :show-file-list="false"
          accept=".zip,.json"
          :on-change="handleImportPackage"
        >
          <el-button>
            <el-icon><Upload /></el-icon>
            导入技能包
          </el-button>
        </el-upload>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          新建 Skill
        </el-button>
      </div>
    </div>

    <!-- 类型筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="filterType" @change="fetchSkills">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button v-for="t in skillTypeOptions" :key="t.value" :label="t.value">{{ t.label }}</el-radio-button>
      </el-radio-group>
    </div>

    <!-- Skill 卡片网格 -->
    <div v-loading="loading" class="skill-grid">
      <el-empty v-if="!loading && skills.length === 0" description="还没有 Skill，点击右上角新建" />
      <el-card
        v-for="skill in skills"
        :key="skill.id"
        class="skill-card"
        :class="{ 'is-incomplete': !skill.config_complete, 'is-builtin': skill.is_builtin }"
        shadow="hover"
      >
        <div class="skill-card-header">
          <span class="skill-icon">{{ skill.icon || '🎯' }}</span>
          <div class="skill-info">
            <div class="skill-title-row">
              <h3>{{ skill.name }}</h3>
              <el-tag v-if="skill.is_builtin" size="small" type="warning" effect="dark">内置</el-tag>
              <el-tag v-if="skill.version" size="small" type="info">v{{ skill.version }}</el-tag>
            </div>
            <div class="skill-tags">
              <el-tag size="small" :type="skillTypeTagType(skill.skill_type)">
                {{ skill.skill_type_display }}
              </el-tag>
              <el-tag size="small" type="info" effect="plain">
                {{ skill.output_format_display || skill.output_format }}
              </el-tag>
              <el-tag v-if="skill.template_columns && skill.template_columns.length" size="small" type="success" effect="plain">
                模板{{ skill.template_columns.length }}列
              </el-tag>
              <el-tag v-if="skill.file_count" size="small" type="warning" effect="plain">
                {{ skill.file_count }} 个文件
              </el-tag>
            </div>
          </div>
          <div class="skill-actions">
            <el-switch
              v-model="skill.is_active"
              size="small"
              @change="toggleActive(skill)"
            />
            <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, skill)">
              <el-button text size="small">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit" :disabled="skill.is_builtin">
                    {{ skill.is_builtin ? '内置不可编辑' : '编辑' }}
                  </el-dropdown-item>
                  <el-dropdown-item command="duplicate">复制</el-dropdown-item>
                  <el-dropdown-item command="export">导出技能包</el-dropdown-item>
                  <el-dropdown-item command="delete" divided :disabled="skill.is_builtin">
                    {{ skill.is_builtin ? '内置不可删除' : '删除' }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <p class="skill-desc">{{ skill.description || '暂无描述' }}</p>

        <!-- 系统提示词预览 -->
        <div v-if="skill.system_prompt" class="prompt-preview">
          <span class="preview-label">系统提示词</span>
          <p class="preview-text">{{ skill.system_prompt.substring(0, 120) }}{{ skill.system_prompt.length > 120 ? '…' : '' }}</p>
        </div>

        <!-- 约束规则预览 -->
        <div v-if="skill.constraint_rules" class="prompt-preview">
          <span class="preview-label">约束规则</span>
          <p class="preview-text">{{ skill.constraint_rules.substring(0, 80) }}{{ skill.constraint_rules.length > 80 ? '…' : '' }}</p>
        </div>

        <div class="skill-config-list">
          <div class="config-row" :class="{ 'is-set': !!skill.writer_model_name }">
            <span class="config-label">模型配置</span>
            <span class="config-value">{{ skill.writer_model_name || skill.is_builtin ? (skill.writer_model_name || '默认活跃模型') : '未配置' }}</span>
          </div>
          <div class="config-row" :class="{ 'is-set': skill.config_complete }">
            <span class="config-label">配置状态</span>
            <span class="config-value">
              <el-tag :type="skill.config_complete ? 'success' : 'warning'" size="small">
                {{ skill.config_complete ? '完整' : '待完善' }}
              </el-tag>
            </span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 编辑/新建弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑 Skill' : '新建 Skill'"
      width="820px"
      destroy-on-close
      top="5vh"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-divider content-position="left">基本信息</el-divider>

        <el-row :gutter="16">
          <el-col :span="4">
            <el-form-item label="图标" prop="icon">
              <el-popover placement="bottom" :width="280" trigger="click" popper-class="icon-picker-popover">
                <template #reference>
                  <el-input v-model="form.icon" placeholder="🎯" readonly class="icon-input" />
                </template>
                <div class="icon-picker">
                  <div class="icon-picker-title">点击选择图标</div>
                  <div class="icon-grid">
                    <span
                      v-for="ic in iconOptions"
                      :key="ic"
                      class="icon-item"
                      :class="{ active: form.icon === ic }"
                      @click="selectIcon(ic)"
                    >{{ ic }}</span>
                  </div>
                </div>
              </el-popover>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" prop="name">
              <el-input v-model="form.name" placeholder="如：API测试专家" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="技能类型" prop="skill_type">
              <el-select v-model="form.skill_type" style="width: 100%">
                <el-option v-for="t in skillTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="这个 Skill 适用什么场景" />
        </el-form-item>

        <el-divider content-position="left">技能核心</el-divider>

        <el-form-item label="系统提示词" prop="system_prompt">
          <el-input
            v-model="form.system_prompt"
            type="textarea"
            :rows="8"
            placeholder="定义这个 Skill 的角色、职责、输入格式、输出要求…"
          />
          <div class="form-hint">这是 Skill 的核心：告诉 AI 它是谁、要做什么、怎么输出</div>
        </el-form-item>

        <el-form-item label="约束规则" prop="constraint_rules">
          <el-input
            v-model="form.constraint_rules"
            type="textarea"
            :rows="5"
            placeholder="如：每条用例必须包含前置条件 / 输出必须为 markdown 表格 / 用例编号格式为 TC-XXX"
          />
          <div class="form-hint">可选，附加在系统提示词后面的硬性规则</div>
        </el-form-item>

        <el-divider content-position="left">团队模板（自定义输出列）</el-divider>

        <el-form-item label="模板文件">
          <div v-if="templateFilename" class="template-info">
            <el-tag size="small" type="success">{{ templateFilename }}</el-tag>
            <el-button link type="danger" size="small" :icon="Delete" @click="handleDeleteTemplate">移除</el-button>
          </div>
          <el-upload
            v-else
            ref="templateUploadRef"
            :auto-upload="false"
            accept=".xlsx,.xls,.csv"
            :show-file-list="false"
            :on-change="handleTemplateChange"
          >
            <el-button size="small" :icon="Upload">上传 Excel/CSV 模板</el-button>
          </el-upload>
          <div class="form-hint">
            上传后自动解析首行列名；生成用例时将严格按这些列输出（智能字段映射）。不配置则使用默认格式。
          </div>
          <div v-if="templateColumns.length" class="template-cols">
            <el-tag
              v-for="(c, i) in templateColumns"
              :key="i"
              size="small"
              type="info"
              effect="plain"
              style="margin: 2px"
            >{{ c }}</el-tag>
          </div>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="输出格式" prop="output_format">
              <el-select v-model="form.output_format" style="width: 100%">
                <el-option label="Markdown 表格" value="markdown" />
                <el-option label="JSON 结构化" value="json" />
                <el-option label="Excel 表格" value="excel" />
                <el-option label="飞书思维导图 / XMind" value="xmind" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="版本">
              <el-input v-model="form.version" placeholder="1.0" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="排序权重">
              <el-input-number v-model="form.sort_order" :min="0" :max="999" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">结构化配置（技能包元数据）</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="作者">
              <el-input v-model="form.author" placeholder="技能包作者" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标签">
              <el-select v-model="form.tags" multiple filterable allow-create default-first-option placeholder="如 api / security" style="width:100%">
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="输入类型">
              <el-select v-model="form.input_spec.type" style="width:100%">
                <el-option label="自由文本" value="free" />
                <el-option label="PRD/需求文档" value="prd" />
                <el-option label="Swagger/OpenAPI" value="swagger" />
                <el-option label="设计图/截图" value="image" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="输入说明">
              <el-input v-model="form.input_spec.description" placeholder="该技能期望的输入是什么" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="输出说明">
              <el-input v-model="form.output_spec.description" placeholder="该技能产出什么" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联工具">
              <el-select v-model="form.tools" multiple filterable allow-create default-first-option placeholder="可使用的工具标识" style="width:100%">
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">
          <span class="advanced-toggle" @click="showAdvanced = !showAdvanced">
            高级配置（模型 & 提示词关联）
            <el-icon><ArrowDown v-if="!showAdvanced" /><ArrowUp v-else /></el-icon>
          </span>
        </el-divider>

        <div v-show="showAdvanced" class="advanced-section">
          <p class="advanced-hint">不填则使用系统默认活跃配置。填了则以这里为准。</p>

          <el-form-item label="编写模型">
            <el-select v-model="form.writer_model_config" clearable filterable placeholder="选择 writer 角色的模型配置" style="width: 100%">
              <el-option v-for="m in writerModels" :key="m.id" :label="`${m.name} (${m.model_name})`" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="编写提示词">
            <el-select v-model="form.writer_prompt_config" clearable filterable placeholder="如果系统提示词为空，则用此提示词" style="width: 100%">
              <el-option v-for="p in writerPrompts" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="评审模型">
            <el-select v-model="form.reviewer_model_config" clearable filterable placeholder="可选" style="width: 100%">
              <el-option v-for="m in reviewerModels" :key="m.id" :label="`${m.name} (${m.model_name})`" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="评审提示词">
            <el-select v-model="form.reviewer_prompt_config" clearable filterable placeholder="可选" style="width: 100%">
              <el-option v-for="p in reviewerPrompts" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="生成行为配置">
            <el-select v-model="form.generation_config" clearable placeholder="不选则用默认活跃配置" style="width: 100%">
              <el-option v-for="g in genConfigs" :key="g.id" :label="g.name" :value="g.id" />
            </el-select>
          </el-form-item>
        </div>

        <el-divider content-position="left">
          <span class="advanced-toggle" @click="showPackageFiles = !showPackageFiles">
            技能包文件（README / input / assets / references / scripts）
            <el-icon><ArrowDown v-if="!showPackageFiles" /><ArrowUp v-else /></el-icon>
          </span>
        </el-divider>

        <div v-show="showPackageFiles" class="advanced-section">
          <p class="advanced-hint">导出 .skill.zip 时会包含这些文件；导入时也会自动识别 input / assets / references / scripts 目录。</p>

          <el-form-item label="README.md">
            <el-input
              v-model="form.readme"
              type="textarea"
              :rows="4"
              placeholder="技能包说明文档，支持 Markdown"
            />
          </el-form-item>

          <el-form-item label="触发关键词">
            <el-select v-model="form.trigger_keywords" multiple filterable allow-create default-first-option placeholder="如：生成测试用例、PRD转测试用例" style="width:100%">
            </el-select>
          </el-form-item>

          <el-form-item label="包内文件">
            <div class="file-tree-box">
              <div class="file-tree-header">
                <el-radio-group v-model="artifactType" size="small">
                  <el-radio-button label="input">input</el-radio-button>
                  <el-radio-button label="asset">assets</el-radio-button>
                  <el-radio-button label="reference">references</el-radio-button>
                  <el-radio-button label="script">scripts</el-radio-button>
                </el-radio-group>
                <el-button size="small" type="primary" @click="openArtifactDialog()">新增文件</el-button>
              </div>
              <el-table :data="filteredArtifacts" size="small" style="margin-top: 8px;">
                <el-table-column prop="path" label="路径" show-overflow-tooltip />
                <el-table-column label="大小" width="120">
                  <template #default="{ row }">
                    {{ row.text_content ? row.text_content.length + ' 字符' : (row.file_name || '二进制') }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="150">
                  <template #default="{ row }">
                    <el-button link type="primary" size="small" @click="openArtifactDialog(row)">编辑</el-button>
                    <el-button link type="danger" size="small" @click="removeArtifact(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 包内文件编辑弹窗 -->
    <el-dialog v-model="artifactDialogVisible" :title="artifactEditingId ? '编辑文件' : '新增文件'" width="600px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="目录类型">
          <el-select v-model="artifactForm.artifact_type" style="width: 100%">
            <el-option label="input" value="input" />
            <el-option label="assets" value="asset" />
            <el-option label="references" value="reference" />
            <el-option label="scripts" value="script" />
            <el-option label="other" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件路径">
          <el-input v-model="artifactForm.path" placeholder="如：input/example_prd.md" />
        </el-form-item>
        <el-form-item label="文本内容">
          <el-input v-model="artifactForm.text_content" type="textarea" :rows="10" placeholder="文件内容（仅文本文件）" />
        </el-form-item>
        <el-form-item label="或上传">
          <el-upload :auto-upload="false" :show-file-list="false" :on-change="handleArtifactFileChange">
            <el-button size="small">选择文件</el-button>
          </el-upload>
          <span v-if="artifactFile" class="form-hint">已选择：{{ artifactFile.name }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="artifactDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="artifactSaving" @click="saveArtifact">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MoreFilled, ArrowDown, ArrowUp, Upload, Delete } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { uploadSkillTemplate, deleteSkillTemplate, exportSkillPackage, importSkillPackage, addSkillArtifact, removeSkillArtifact } from '@/api/requirement-analysis'

export default {
  name: 'SkillConfig',
  components: { Plus, MoreFilled, ArrowDown, ArrowUp, Upload },
  setup() {
    const loading = ref(false)
    const saving = ref(false)
    const skills = ref([])
    const dialogVisible = ref(false)
    const editingId = ref(null)
    const formRef = ref(null)
    const showAdvanced = ref(false)
    const showPackageFiles = ref(false)
    const filterType = ref('')
    const templateUploadRef = ref(null)
    const templateColumns = ref([])
    const templateFilename = ref('')
    const importUploadRef = ref(null)

    const artifactType = ref('input')
    const artifacts = ref([])
    const artifactDialogVisible = ref(false)
    const artifactEditingId = ref(null)
    const artifactFile = ref(null)
    const artifactSaving = ref(false)
    const artifactForm = reactive({
      artifact_type: 'input',
      path: '',
      text_content: '',
    })

    const writerModels = ref([])
    const reviewerModels = ref([])
    const writerPrompts = ref([])
    const reviewerPrompts = ref([])
    const genConfigs = ref([])

    const skillTypeOptions = [
      { label: '需求分析', value: 'requirements_analysis' },
      { label: '需求评审', value: 'requirement_reviewer' },
      { label: '用例评审', value: 'testcase_reviewer' },
      { label: '用例生成', value: 'testcase_generator' },
      { label: '数字人', value: 'digital_human' },
      { label: '自定义', value: 'custom' },
    ]

    const iconOptions = [
      '🎯','🤖','📝','📊','🔍','🐞','⚡','🧪',
      '🔧','📋','✅','❌','💡','🚀','🛡️','🔑',
      '📁','🌐','💾','🔔','📈','🎓','🏷️','🧩',
      '⚙️','🔥','📚','🗂️','🖥️','🎮','📱','🔬',
      '🧠','🎨','🛠️','📤','📥','🔒','🔓','🧰'
    ]

    const form = reactive({
      icon: '🎯',
      name: '',
      skill_type: 'testcase_generator',
      description: '',
      system_prompt: '',
      constraint_rules: '',
      output_format: 'markdown',
      version: '1.0',
      sort_order: 0,
      // 结构化技能包字段
      author: '',
      tags: [],
        input_spec: { type: 'free', description: '' },
        output_spec: { format: '', description: '', columns: [] },
        tools: [],
        // 技能包文件
        readme: '',
        trigger_keywords: [],
        // 高级配置
        writer_model_config: null,
        reviewer_model_config: null,
        writer_prompt_config: null,
        reviewer_prompt_config: null,
        generation_config: null,
      })

    const rules = {
      name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
      skill_type: [{ required: true, message: '请选择技能类型', trigger: 'change' }],
    }

    const fetchSkills = async () => {
      loading.value = true
      try {
        let url = '/requirement-analysis/skills/'
        if (filterType.value) {
          url += `?skill_type=${filterType.value}`
        }
        const res = await api.get(url)
        skills.value = res.data?.results || res.data || []
      } catch (e) {
        ElMessage.error('加载失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        loading.value = false
      }
    }

    const fetchOptions = async () => {
      try {
        const [modelsRes, promptsRes, genRes] = await Promise.all([
          api.get('/requirement-analysis/ai-models/'),
          api.get('/requirement-analysis/prompts/'),
          api.get('/requirement-analysis/generation-config/'),
        ])
        const allModels = modelsRes.data?.results || modelsRes.data || []
        writerModels.value = allModels.filter(m => m.role === 'writer')
        reviewerModels.value = allModels.filter(m => m.role === 'reviewer')

        const allPrompts = promptsRes.data?.results || promptsRes.data || []
        writerPrompts.value = allPrompts.filter(p => p.prompt_type === 'writer')
        reviewerPrompts.value = allPrompts.filter(p => p.prompt_type === 'reviewer')

        genConfigs.value = genRes.data?.results || genRes.data || []
      } catch (e) {
        console.error('加载选项失败', e)
      }
    }

    const openCreate = () => {
      editingId.value = null
      showAdvanced.value = false
      showPackageFiles.value = false
      templateColumns.value = []
      templateFilename.value = ''
      artifacts.value = []
      Object.assign(form, {
        icon: '🎯', name: '', skill_type: 'testcase_generator', description: '',
        system_prompt: '', constraint_rules: '', output_format: 'markdown',
        version: '1.0', sort_order: 0,
        author: '', tags: [], input_spec: { type: 'free', description: '' },
        output_spec: { format: '', description: '', columns: [] }, tools: [],
        readme: '', trigger_keywords: [],
        writer_model_config: null, reviewer_model_config: null,
        writer_prompt_config: null, reviewer_prompt_config: null,
        generation_config: null,
      })
      dialogVisible.value = true
    }

    const openEdit = (skill) => {
      editingId.value = skill.id
      showAdvanced.value = false
      showPackageFiles.value = false
      templateColumns.value = skill.template_columns || []
      templateFilename.value = skill.template_filename || ''
      artifacts.value = skill.artifacts || []
      Object.assign(form, {
        icon: skill.icon || '🎯',
        name: skill.name,
        skill_type: skill.skill_type || 'custom',
        description: skill.description || '',
        system_prompt: skill.system_prompt || '',
        constraint_rules: skill.constraint_rules || '',
        output_format: skill.output_format || 'markdown',
        version: skill.version || '1.0',
        sort_order: skill.sort_order || 0,
        author: skill.author || '',
        tags: skill.tags || [],
        input_spec: skill.input_spec && Object.keys(skill.input_spec).length ? skill.input_spec : { type: 'free', description: '' },
        output_spec: skill.output_spec && Object.keys(skill.output_spec).length ? skill.output_spec : { format: '', description: '', columns: [] },
        tools: skill.tools || [],
        readme: skill.readme || '',
        trigger_keywords: skill.trigger_keywords || [],
        writer_model_config: skill.writer_model_config || null,
        reviewer_model_config: skill.reviewer_model_config || null,
        writer_prompt_config: skill.writer_prompt_config || null,
        reviewer_prompt_config: skill.reviewer_prompt_config || null,
        generation_config: skill.generation_config || null,
      })
      dialogVisible.value = true
    }

    const handleTemplateChange = async (file) => {
      if (!editingId.value) {
        ElMessage.warning('请先保存 Skill 后再上传模板')
        return
      }
      if (!file || !file.raw) return
      try {
        const res = await uploadSkillTemplate(editingId.value, file.raw)
        templateColumns.value = res.data.template_columns || []
        templateFilename.value = res.data.template_filename || file.name
        ElMessage.success('模板已上传并解析列名')
        await fetchSkills()
      } catch (e) {
        ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const handleDeleteTemplate = async () => {
      if (!editingId.value) return
      try {
        await deleteSkillTemplate(editingId.value)
        templateColumns.value = []
        templateFilename.value = ''
        ElMessage.success('模板已移除')
        await fetchSkills()
      } catch (e) {
        ElMessage.error('移除失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const mapArtifactType = (type) => {
      const map = { input: 'input', asset: 'asset', reference: 'reference', script: 'script' }
      return map[type] || type
    }

    const filteredArtifacts = computed(() => {
      const map = {
        input: 'input',
        asset: 'asset',
        reference: 'reference',
        script: 'script',
      }
      return artifacts.value.filter(a => a.artifact_type === map[artifactType.value])
    })

    const openArtifactDialog = (row) => {
      artifactEditingId.value = row ? row.id : null
      artifactFile.value = null
      if (row) {
        Object.assign(artifactForm, {
          artifact_type: row.artifact_type,
          path: row.path,
          text_content: row.text_content || '',
        })
      } else {
        Object.assign(artifactForm, {
          artifact_type: mapArtifactType(artifactType.value),
          path: `${artifactType.value}/`,
          text_content: '',
        })
      }
      artifactDialogVisible.value = true
    }

    const handleArtifactFileChange = (file) => {
      artifactFile.value = file.raw
    }

    const saveArtifact = async () => {
      if (!editingId.value) {
        ElMessage.warning('请先保存 Skill 基本信息')
        return
      }
      if (!artifactForm.path.trim()) return ElMessage.warning('请填写文件路径')
      artifactSaving.value = true
      try {
        const payload = {
          path: artifactForm.path,
          artifact_type: artifactForm.artifact_type,
          text_content: artifactForm.text_content,
        }
        const res = await addSkillArtifact(editingId.value, payload, artifactFile.value)
        const idx = artifacts.value.findIndex(a => a.id === res.data.id)
        if (idx >= 0) {
          artifacts.value[idx] = res.data
        } else {
          artifacts.value.push(res.data)
        }
        artifactDialogVisible.value = false
        ElMessage.success('文件已保存')
      } catch (e) {
        ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        artifactSaving.value = false
      }
    }

    const removeArtifact = async (row) => {
      try {
        await ElMessageBox.confirm(`确认删除 ${row.path} 吗？`, '删除确认', { type: 'warning' })
        await removeSkillArtifact(editingId.value, { artifact_id: row.id })
        artifacts.value = artifacts.value.filter(a => a.id !== row.id)
        ElMessage.success('已删除')
      } catch (e) {
        if (e !== 'cancel') ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const save = async () => {
      try {
        await formRef.value.validate()
      } catch {
        return
      }
      saving.value = true
      try {
        // template_file / template_columns 由专门的模板上传/删除接口管理，不随表单提交
        const payload = { ...form }
        delete payload.template_file
        delete payload.template_columns
        delete payload.template_filename
        delete payload.template_url
        if (editingId.value) {
          await api.put(`/requirement-analysis/skills/${editingId.value}/`, payload)
          ElMessage.success('已更新')
        } else {
          await api.post('/requirement-analysis/skills/', payload)
          ElMessage.success('已创建')
        }
        dialogVisible.value = false
        await fetchSkills()
      } catch (e) {
        ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        saving.value = false
      }
    }

    const toggleActive = async (skill) => {
      try {
        await api.patch(`/requirement-analysis/skills/${skill.id}/`, { is_active: skill.is_active })
      } catch (e) {
        skill.is_active = !skill.is_active
        ElMessage.error('切换失败')
      }
    }

    const handleCommand = async (cmd, skill) => {
      if (cmd === 'edit') {
        if (skill.is_builtin) {
          ElMessage.warning('内置 Skill 不可编辑，请复制后修改')
          return
        }
        openEdit(skill)
      } else if (cmd === 'duplicate') {
        try {
          await api.post(`/requirement-analysis/skills/${skill.id}/duplicate/`)
          ElMessage.success('已复制')
          await fetchSkills()
        } catch (e) {
          ElMessage.error('复制失败: ' + (e.response?.data?.detail || e.message))
        }
      } else if (cmd === 'delete') {
        if (skill.is_builtin) {
          ElMessage.warning('内置 Skill 不可删除')
          return
        }
        try {
          await ElMessageBox.confirm(`确认删除「${skill.name}」？`, '删除确认', { type: 'warning' })
          await api.delete(`/requirement-analysis/skills/${skill.id}/`)
          ElMessage.success('已删除')
          await fetchSkills()
        } catch (e) {
          if (e !== 'cancel') ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
        }
      } else if (cmd === 'export') {
        await exportPackage(skill)
      }
    }

    const exportPackage = async (skill) => {
      try {
        const res = await exportSkillPackage(skill.id)
        const blob = res.data
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${(skill.name || 'skill').replace(/\s+/g, '_')}.skill.zip`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
        ElMessage.success('技能包已导出')
      } catch (e) {
        ElMessage.error('导出失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const handleImportPackage = async (file) => {
      try {
        const res = await importSkillPackage(file.raw)
        ElMessage.success(res.data.detail || '导入成功')
        await fetchSkills()
      } catch (e) {
        ElMessage.error('导入失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const selectIcon = (ic) => {
      form.icon = ic
    }

    const skillTypeTagType = (type) => {
      const map = {
        requirements_analysis: 'primary',
        requirement_reviewer: 'warning',
        testcase_reviewer: 'success',
        testcase_generator: 'danger',
        custom: 'info',
      }
      return map[type] || ''
    }

    onMounted(() => {
      fetchSkills()
      fetchOptions()
    })

    return {
      loading, saving, skills, dialogVisible, editingId, formRef,
      form, rules, skillTypeOptions, showAdvanced, showPackageFiles, filterType,
      writerModels, reviewerModels, writerPrompts, reviewerPrompts, genConfigs,
      templateUploadRef, templateColumns, templateFilename, importUploadRef,
      iconOptions, selectIcon,
      artifactType, artifacts, artifactDialogVisible, artifactEditingId,
      artifactForm, artifactFile, artifactSaving, filteredArtifacts,
      openCreate, openEdit, save, toggleActive, handleCommand, skillTypeTagType,
      handleTemplateChange, handleDeleteTemplate, exportPackage, handleImportPackage,
      openArtifactDialog, saveArtifact, removeArtifact, handleArtifactFileChange,
      fetchSkills,
    }
  },
}
</script>

<style scoped>
.skill-config { padding: 20px; max-width: 1400px; margin: 0 auto; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.page-header h2 { margin: 0 0 4px 0; color: var(--el-text-color-primary); }
.subtitle { color: var(--el-text-color-secondary); font-size: 13px; margin: 0; }
.header-actions { display: flex; gap: 10px; align-items: center; flex-shrink: 0; }

.filter-bar { margin-bottom: 20px; }

.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}

.skill-card { transition: transform 0.2s; }
.skill-card.is-incomplete { border-color: var(--el-color-warning-light-5); }
.skill-card.is-builtin { border-left: 3px solid var(--el-color-warning); }

.skill-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.skill-icon { font-size: 32px; line-height: 1; }
.skill-info { flex: 1; min-width: 0; }
.skill-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.skill-title-row h3 { margin: 0; font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.skill-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.skill-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.skill-desc {
  color: var(--el-text-color-regular); font-size: 13px; margin: 12px 0 8px;
  min-height: 20px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.prompt-preview {
  background: var(--el-fill-color-light);
  border-radius: 6px;
  padding: 8px 10px;
  margin: 6px 0;
}
.preview-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: 600;
}
.preview-text {
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin: 4px 0 0 0;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.skill-config-list { margin-top: 12px; }
.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 13px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.config-row:last-child { border-bottom: none; }
.config-label { color: var(--el-text-color-secondary); }
.config-value { color: var(--el-text-color-primary); font-weight: 500; }
.config-row.is-set .config-value { color: var(--el-color-primary); }
.config-row:not(.is-set) .config-value { color: var(--el-color-info-light-3); }

.form-hint { margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px; }

.advanced-toggle {
  cursor: pointer;
  color: var(--el-color-primary);
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.advanced-section {
  padding: 0 0 8px 0;
}
.advanced-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px 0;
}

.icon-input :deep(.el-input__wrapper) {
  cursor: pointer;
}
.icon-picker-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.icon-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 4px;
}
.icon-item {
  font-size: 22px;
  cursor: pointer;
  text-align: center;
  padding: 4px;
  border-radius: 4px;
  transition: background 0.15s;
}
.icon-item:hover,
.icon-item.active {
  background: var(--el-color-primary-light-9);
}

.file-tree-box {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 12px;
}
.file-tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
