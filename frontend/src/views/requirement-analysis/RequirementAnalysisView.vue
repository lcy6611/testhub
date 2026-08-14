<template>
  <div class="requirement-analysis">
    <div class="page-header">
      <h1>智能测试用例生成</h1>
      <p>基于需求描述或文档，AI将直接为您生成高质量的测试用例</p>
    </div>

    <!-- 配置引导弹窗（与上游一致：/requirement-analysis/config/check/） -->
    <div v-if="showConfigGuide && !checkingConfig" class="modal-overlay" @click.self="showConfigGuide = false">
      <div class="guide-config-modal">
        <div class="guide-header">
          <h2>开始使用AI用例生成功能</h2>
          <p>在使用前，请先完成：模型配置、提示词配置、生成行为配置</p>
          </div>
        <div class="guide-actions">
          <button class="generate-manual-btn" @click="goToConfig">去配置</button>
          <div class="skip-action" @click="showConfigGuide = false">稍后配置</div>
        </div>
              </div>
              </div>

    <!-- 关联项目 + 知识库（合并为一张卡：先选项目，才能启用 KB） -->
    <div class="project-kb-section" v-if="!isGenerating && !showResults">
      <div class="project-kb-card">
        <h3>📁 关联项目 <span class="card-divider">·</span> 🧠 知识库（业务大脑）</h3>
        <p class="card-desc">
          先选项目——知识库从所选项目下已发布的 KB 中筛选，<strong>未选项目时不可用</strong>。
        </p>

        <!-- 1. 项目选择器 -->
        <div class="form-row project-row">
          <label class="form-label required-mark">项目</label>
          <div class="form-control">
            <select v-model="selectedProject" class="form-select">
              <option value="">— 请选择项目 —</option>
              <option v-for="project in projects" :key="project.id" :value="project.id">
                {{ project.name }}
              </option>
            </select>
            <span v-if="!selectedProject" class="field-hint warn">⚠️ 暂未选择项目</span>
            <span v-else class="field-hint ok">✅ 已选项目，后续将自动加载其下的知识库</span>
          </div>
        </div>

        <!-- 2. 知识库（依赖项目） -->
        <div class="kb-block" :class="{ 'kb-block-disabled': !selectedProject }">
          <div class="kb-block-header">
            <label class="kb-toggle">
              <input
                type="checkbox"
                v-model="enableKnowledgeBase"
                :disabled="!selectedProject">
              <span>启用知识库（业务大脑）</span>
            </label>
            <span class="kb-summary">
              <el-tag size="small" :type="projectEngine === 'dify' ? 'success' : projectEngine === 'native' ? 'warning' : 'info'">
                🔗 按项目自动：{{ projectEngine === 'dify' ? 'Dify 知识库' : projectEngine === 'native' ? '自建知识中枢' : '未选择项目' }}
              </el-tag>
              <el-tag v-if="selectedProject" size="small" type="info">{{ projectKbs.length }} 个可用</el-tag>
            </span>
          </div>

          <div v-if="!selectedProject" class="kb-locked-tip">
            <span class="lock-icon">🔒</span>
            <div class="lock-content">
              <strong>请先在上方「项目」中选择一个项目</strong>
              <div class="lock-sub">选择项目后，系统将自动判定使用 Dify 知识库还是本地自建 KB（项目有 Dify 绑定 → Dify；否则 → 本地）。</div>
            </div>
          </div>

            <div v-else-if="enableKnowledgeBase" class="kb-info-box">
              <div v-if="loadingProjectKbs" class="form-tip">正在检索项目下的知识库...</div>
              <div v-else-if="projectKbs.length === 0" class="kb-empty-tip">
                ⚠️ 当前项目下还没有可用的知识库。请前往
                <router-link to="/configuration/knowledge-hub/kbs">知识中枢 → 知识库管理</router-link>
                ①「知识库与外部数据源」页签新建本地 KB 并发布，或 ②「Dify 知识库绑定」页签绑定 Dify 数据集。
              </div>
            <div v-else class="kb-checklist">
              <div class="kb-checklist-header">
                <span>📚 请勾选要在本次生成中使用的知识库（默认全部勾选）：</span>
                <a class="kb-link" @click.prevent="toggleAllKbs">{{ allKbSelected ? '取消全选' : '全选' }}</a>
              </div>
              <label
                v-for="kb in projectKbs"
                :key="kb.id"
                class="kb-check-item">
                <input
                  type="checkbox"
                  :value="kb.id"
                  v-model="selectedKbIds">
                <span class="kb-check-name">{{ kb.type === 'dify' ? '🔗' : '📘' }} {{ kb.name }}</span>
                <el-tag v-if="kb.type === 'dify'" size="small" type="success" style="margin-left:4px">Dify</el-tag>
                <el-tag v-else-if="kb.source === 'global'" size="small" type="warning" style="margin-left:4px">全局共享</el-tag>
                <el-tag v-else-if="kb.source === 'shared'" size="small" type="info" style="margin-left:4px">跨项目共享</el-tag>
                <el-tag v-else-if="kb.source === 'owned'" size="small" style="margin-left:4px">本项目专属</el-tag>
                <span class="kb-check-meta">
                  <el-tag size="small" type="info">{{ kb.document_count || 0 }} 篇文档</el-tag>
                  <span v-if="kb.description" class="kb-check-desc">{{ kb.description }}</span>
                </span>
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输出模式（与上游一致） -->
    <div class="output-mode-section" v-if="!isGenerating && !showResults">
      <div class="output-mode-card">
        <h3>📤 输出模式</h3>
        <div class="output-mode-selector">
          <label class="mode-option" :class="{ active: globalOutputMode === 'stream' }">
            <input type="radio" v-model="globalOutputMode" value="stream">
            <span>⚡ 实时流式输出</span>
          </label>
          <label class="mode-option" :class="{ active: globalOutputMode === 'complete' }">
            <input type="radio" v-model="globalOutputMode" value="complete">
            <span>📄 完整输出</span>
          </label>
        </div>
      </div>
    </div>

    <!-- Skill 选择 -->
    <div class="skill-section" v-if="!isGenerating && !showResults">
      <div class="skill-card-inline">
        <h3>🎯 Skill 技能包（可选）</h3>
        <p class="skill-desc">选择技能包后，将使用该 Skill 的系统提示词、约束规则和模型配置执行生成</p>
        <div class="skill-selector">
          <select v-model="selectedSkillId" class="form-select skill-select">
            <option value="">使用默认配置（不选 Skill）</option>
            <option v-for="skill in activeSkills" :key="skill.id" :value="skill.id">
              {{ skill.icon }} {{ skill.name }} — {{ skill.skill_type_display || '自定义' }}{{ skill.is_builtin ? '（内置）' : '' }}
            </option>
          </select>
          <a v-if="selectedSkillId" class="skill-manage-link" @click.prevent="goToSkillConfig">管理 Skill</a>
          <a v-else class="skill-manage-link" @click.prevent="goToSkillConfig">+ 新建 Skill</a>
        </div>
      </div>
    </div>

    <!-- 知识库参考预览弹窗 -->
    <div v-if="showKbPreview" class="modal-overlay" @click.self="showKbPreview = false">
      <div class="kb-preview-modal">
        <div class="kb-preview-header">
          <h3>知识库参考预览</h3>
          <button type="button" class="close-btn" @click="showKbPreview = false">✕</button>
        </div>
        <div v-if="kbPreviewMeta" class="kb-preview-meta">
          文档 {{ (kbPreviewMeta.documents || []).length }} 篇 ·
          共 {{ kbPreviewLength }} 字符
        </div>
        <div v-if="kbPreviewWarnings.length" class="kb-preview-warnings">
          <p v-for="(warn, idx) in kbPreviewWarnings" :key="idx">{{ warn }}</p>
        </div>
        <pre class="kb-preview-content">{{ kbPreviewText || '（无有效参考内容）' }}</pre>
      </div>
    </div>

    <!-- 参考截图（可选）：与需求正文分离，需标注用途 -->
    <div class="image-attachment-section" v-if="!isGenerating && !showResults">
      <div class="image-attachment-card">
        <h3>🖼️ 参考截图（可选）</h3>
        <p class="image-attachment-desc">
          上传界面截图时请<strong>选择用途</strong>：「页面样式」用于识别布局与控件；「操作步骤」用于按顺序编写用例步骤。
          截图<strong>不会</strong>当作需求正文，需求仍以上方文字/文档为准。
        </p>
        <div class="image-upload-row">
          <input
            type="file"
            ref="imageInput"
            accept="image/*"
            multiple
            style="display: none"
            @change="handleImageFileSelect">
          <button
            type="button"
            class="select-file-btn"
            :disabled="uploadingImages || imageAttachments.length >= 12"
            @click="$refs.imageInput.click()">
            {{ uploadingImages ? '上传中...' : `添加截图 (${imageAttachments.length}/12)` }}
          </button>
          <span class="image-upload-tip">需配置支持视觉的 writer 模型（如 Qwen-VL、GPT-4o）</span>
        </div>
        <div v-if="imageAttachments.length" class="image-attachment-list">
          <div v-for="(item, idx) in imageAttachments" :key="idx" class="image-attachment-item">
            <img :src="item.previewUrl" :alt="item.name" class="attachment-thumb">
            <div class="attachment-fields">
              <label class="attachment-field-label">用途</label>
              <select v-model="item.role" class="form-select attachment-role" @change="onImageRoleChange(item)">
                <option value="ui_layout">页面样式参考</option>
                <option value="operation_step">操作步骤参考</option>
              </select>
              <label class="attachment-field-label">说明（可选）</label>
              <input
                v-model="item.caption"
                type="text"
                class="form-input attachment-caption"
                :placeholder="item.role === 'operation_step' ? '如：点击登录按钮' : '如：登录页整体布局'">
              <label v-if="item.role === 'operation_step'" class="attachment-field-label">步骤序号</label>
              <input
                v-if="item.role === 'operation_step'"
                v-model.number="item.step_index"
                type="number"
                min="1"
                class="form-input attachment-step"
                placeholder="1">
            </div>
            <button type="button" class="attachment-remove-btn" @click="removeImageAttachment(idx)">删除</button>
          </div>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- 手动输入需求描述区域 -->
      <div class="manual-input-section" v-if="!isGenerating && !showResults">
        <div class="manual-input-card">
          <h2>✍️ 手动输入需求描述</h2>
          <div class="input-form">
            <div class="form-group">
              <label>需求标题 <span class="required">*</span></label>
              <input
                v-model="manualInput.title"
                type="text"
                class="form-input"
                placeholder="请输入需求标题，如：用户登录功能需求">
            </div>

            <div class="form-group">
              <label>需求描述 <span class="required">*</span></label>
              <textarea
                v-model="manualInput.description"
                class="form-textarea"
                rows="8"
                placeholder="请详细描述您的需求，包括功能描述、使用场景、业务流程等。例如：&#10;&#10;1. 用户可以通过用户名和密码登录系统&#10;2. 系统需要验证用户身份&#10;3. 登录成功后跳转到主页面&#10;4. 支持记住登录状态&#10;5. 登录失败要给出明确提示..."></textarea>
              <div class="char-count">{{ manualInput.description.length }}/2000</div>
            </div>

            <div class="form-group">
              <label>关联项目</label>
              <div class="form-static-value">
                {{ selectedProject ? (projects.find(p => String(p.id) === String(selectedProject))?.name || '已选项目 #' + selectedProject) : '未选项目（在顶部「关联项目」选择）' }}
              </div>
            </div>

            <div class="form-group">
              <label>接口文档 Swagger / OpenAPI（可选）</label>
              <textarea
                v-model="manualInput.swaggerText"
                class="form-textarea"
                rows="6"
                placeholder="可直接粘贴 Swagger 2.0 / OpenAPI 3.x 的 JSON 内容，系统将自动识别并据此生成接口测试用例。例如：&#10;{&#10;  &quot;openapi&quot;: &quot;3.0.0&quot;,&#10;  &quot;paths&quot;: { &quot;/api/login&quot;: { &quot;post&quot;: {} } }&#10;}"></textarea>
              <div class="swagger-hint" v-if="manualInput.swaggerText.trim()">
                ✓ 已识别接口文档，将自动并入生成上下文
              </div>
            </div>

            <button
              class="generate-manual-btn"
              @click="generateFromManualInput"
              :disabled="!canGenerateManual || isGenerating">
              <span v-if="isGenerating">🔄 生成中...</span>
              <span v-else>🚀 生成测试用例</span>
            </button>
            </div>
          </div>
        </div>

      <!-- 分隔线 -->
      <div class="divider" v-if="!isGenerating && !showResults">
        <span>或</span>
      </div>

      <!-- 文档上传区域 -->
      <div class="upload-section" v-if="!isGenerating && !showResults">
        <div class="upload-card">
          <h2>📄 上传需求文档</h2>
          <div class="upload-area"
               @dragover.prevent
               @drop="handleDrop"
               :class="{ 'drag-over': isDragOver }"
               @dragenter="isDragOver = true"
               @dragleave="isDragOver = false">
            <div v-if="!selectedFile" class="upload-placeholder">
              <i class="upload-icon">📁</i>
              <p>拖拽文件到此处或点击选择文件</p>
              <p class="upload-hint">支持 PDF、Word、TXT 格式</p>
              <input
                type="file"
                ref="fileInput"
                @change="handleFileSelect"
                accept=".pdf,.doc,.docx,.txt"
                style="display: none;">
              <button class="select-file-btn" @click="$refs.fileInput.click()">
                选择文件
              </button>
            </div>

            <div v-else class="file-selected">
              <div class="file-info">
                <i class="file-icon">📄</i>
                <div class="file-details">
                  <p class="file-name">{{ selectedFile.name }}</p>
                  <p class="file-size">{{ formatFileSize(selectedFile.size) }}</p>
                </div>
                <button class="remove-file" @click="removeFile">❌</button>
              </div>
            </div>
          </div>

          <div v-if="selectedFile" class="document-info">
            <div class="form-group">
              <label>文档标题</label>
              <input
                v-model="documentTitle"
                type="text"
                class="form-input"
                placeholder="请输入文档标题">
            </div>

            <div class="form-group">
              <label>关联项目</label>
              <div class="form-static-value">
                {{ selectedProject ? (projects.find(p => String(p.id) === String(selectedProject))?.name || '已选项目 #' + selectedProject) : '未选项目（在顶部「关联项目」选择）' }}
              </div>
            </div>

            <button
              class="generate-btn"
              @click="generateFromDocument"
              :disabled="!documentTitle || isGenerating">
              <span v-if="isGenerating">🔄 生成中...</span>
              <span v-else>🚀 生成测试用例</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 生成进度和结果（与上游一致：isGenerating || showResults） -->
      <div v-if="isGenerating || showResults" class="generation-progress">
        <div class="progress-card">
          <h3>
            🤖 AI正在为您生成测试用例
            <span v-if="globalOutputMode === 'stream'" class="current-mode-badge">
              (当前模式: ⚡实时流式输出)
            </span>
            <span v-else class="current-mode-badge">
              (当前模式: 📄完整输出)
            </span>
          </h3>

          <!-- 进度步骤：统一放在卡片最上方，两种输出方式共用 -->
          <div class="progress-steps">
            <div class="step" :class="{ active: currentStep >= 1 }">
              <span class="step-number">1</span>
              <span class="step-text">需求分析</span>
            </div>
            <div class="step" :class="{ active: currentStep >= 2 }">
              <span class="step-number">2</span>
              <span class="step-text">用例编写</span>
            </div>
            <div v-if="showReviewStep" class="step" :class="{ active: currentStep >= 3 }">
              <span class="step-number">3</span>
              <span class="step-text">用例评审</span>
            </div>
            <div class="step" :class="{ active: currentStep >= (showReviewStep ? 4 : 3) }">
              <span class="step-number">{{ showReviewStep ? 4 : 3 }}</span>
              <span class="step-text">完成</span>
            </div>
          </div>

          <div class="progress-info">
            <div class="progress-item">
              <span class="label">任务ID:</span>
              <span class="value">{{ currentTaskId || '准备中...' }}</span>
            </div>
            <div class="progress-item">
              <span class="label">当前状态:</span>
              <span class="value">{{ displayStatusText }}</span>
            </div>
          </div>

          <p v-if="graphExpansionHint" class="graph-expansion-hint">
            🔗 知识图谱：{{ graphExpansionHint }}
          </p>

          <!-- 思考过程实时显示区域（模型真实 reasoning_content，深度思考模型可见） -->
          <div v-if="isGenerating && reasoningContent" class="stream-content-display" style="margin-bottom: 15px;">
            <div class="stream-header">
              <span class="stream-title">🧠 AI 思考过程</span>
              <span class="stream-status">{{ reasoningContent.length }} 字符</span>
            </div>
            <div class="stream-content reasoning-content" style="white-space: pre-wrap;">{{ reasoningContent }}</div>
          </div>

          <!-- 流式内容实时显示区域：仅生成中展示，完成后由统一“生成结果”区域承接 -->
          <div v-if="isGenerating && globalOutputMode === 'stream'" class="stream-content-display">
            <div class="stream-header">
              <span class="stream-title">✍️ 实时生成内容</span>
              <span class="stream-status">{{ (streamedContent || '').length }} 字符</span>
            </div>
            <div class="stream-content" v-html="formatMarkdown(streamedContent || '')"></div>
            <div v-if="isGenerating && !streamedContent" class="stream-placeholder">等待内容输出...</div>
          </div>

          <!-- 评审内容显示区域（仅生成中展示预览） -->
          <div v-if="isGenerating && streamedReviewContent" class="stream-content-display" style="margin-top: 15px;">
            <div class="stream-header">
              <span class="stream-title">📝 AI评审意见</span>
              <span class="stream-status">{{ streamedReviewContent.length }} 字符</span>
            </div>
            <div class="stream-content" v-html="formatMarkdown(streamedReviewContent)"></div>
          </div>

          <!-- 最终版用例流式预览（仅生成中展示） -->
          <div v-if="isGenerating && finalTestCases" class="stream-content-display" style="margin-top: 15px;">
            <div class="stream-header">
              <span class="stream-title">
                🎯 最终版用例
                <span v-if="isGenerating" class="streaming-indicator">🔄 正在生成...</span>
              </span>
              <span class="stream-status">{{ finalTestCases.length }} 字符</span>
            </div>
            <div class="stream-content final-testcases" v-html="formatMarkdown(finalTestCases)"></div>
          </div>

          <!-- 任务完成后的操作按钮（与上游一致） -->
          <div v-if="showResults" class="completion-actions">
            <button class="download-btn" @click="downloadTestCases">
              <span>📥 下载测试用例</span>
            </button>
            <button class="save-btn" @click="saveToTestCaseRecords" :disabled="!canSaveToCaseRecords">
              <span>💾 保存到用例库</span>
            </button>
            <button class="continue-refine-btn" @click="scrollToContinueRefine">
              <span>✏️ 继续优化用例</span>
            </button>
            <button class="new-generation-btn" @click="resetGeneration">
              <span>📝 生成新用例</span>
            </button>
          </div>

          <button v-if="isGenerating && !showResults" class="cancel-generation-btn" @click="cancelGeneration">
            取消生成
          </button>
        </div>
      </div>

      <!-- 生成结果（统一一个区域，三块内容格式与流式预览保持一致） -->
      <div v-if="showResults && generationResult" class="generation-result">
          <div class="result-header">
          <h2>{{ resultTitle }}</h2>
          <div class="result-summary">
            <span class="summary-item">
              📊 任务ID: {{ generationResult.task_id }}
            </span>
            <span class="summary-item">
              ⏱️ 生成时间: {{ formatDateTime(generationResult.completed_at) }}
            </span>
          </div>
          <button class="new-generation-btn" @click="resetGeneration">
            📝 生成新的测试用例
          </button>
        </div>

        <!-- 在此基础上继续改（置于结果顶部，便于发现） -->
        <div
          v-if="hasUsableCases"
          id="continue-refine-panel"
          class="continue-refine-section">
          <div class="continue-refine-card">
            <h3>✏️ 在此基础上继续改</h3>
            <p class="refine-desc">
              对<strong>当前用例</strong>追加补充说明或新截图，AI 会在现有基础上增删改，不会从零重写。
              截图请标注「页面样式」或「操作步骤」。
            </p>
            <div class="form-group">
              <label>补充要求</label>
              <textarea
                v-model="refinementInstructions"
                class="form-textarea refine-textarea"
                rows="4"
                placeholder="例如：补充密码错误 3 次锁定的边界用例；按新截图完善登录步骤…"></textarea>
            </div>
            <div class="image-upload-row">
              <input
                type="file"
                ref="refineImageInput"
                accept="image/*"
                multiple
                style="display: none"
                @change="handleRefineImageSelect">
              <button
                type="button"
                class="select-file-btn"
                :disabled="uploadingRefineImages || refineImageAttachments.length >= 12"
                @click="$refs.refineImageInput.click()">
                {{ uploadingRefineImages ? '上传中...' : `添加截图 (${refineImageAttachments.length}/12)` }}
              </button>
              <span class="image-upload-tip">需视觉 writer 模型（如 Qwen-VL、GPT-4o）</span>
            </div>
            <div v-if="refineImageAttachments.length" class="image-attachment-list">
              <div
                v-for="(item, idx) in refineImageAttachments"
                :key="idx"
                class="image-attachment-item">
                <img :src="item.previewUrl" :alt="item.name" class="attachment-thumb">
                <div class="attachment-fields">
                  <label class="attachment-field-label">用途</label>
                  <select
                    v-model="item.role"
                    class="form-select attachment-role"
                    @change="onRefineImageRoleChange(item)">
                    <option value="ui_layout">页面样式参考</option>
                    <option value="operation_step">操作步骤参考</option>
                  </select>
                  <label class="attachment-field-label">说明（可选）</label>
                  <input
                    v-model="item.caption"
                    type="text"
                    class="form-input attachment-caption"
                    :placeholder="item.role === 'operation_step' ? '如：点击登录' : '如：登录页布局'">
                  <label v-if="item.role === 'operation_step'" class="attachment-field-label">步骤序号</label>
                  <input
                    v-if="item.role === 'operation_step'"
                    v-model.number="item.step_index"
                    type="number"
                    min="1"
                    class="form-input attachment-step"
                    placeholder="1">
                </div>
                <button type="button" class="attachment-remove-btn" @click="removeRefineImage(idx)">删除</button>
              </div>
            </div>
            <button
              type="button"
              class="submit-continue-refine-btn"
              :disabled="!canSubmitContinueRefine"
              @click="submitContinueRefine">
              🚀 提交并继续优化
            </button>
          </div>
        </div>

        <!-- 测试用例：初稿与最终版相同时只展示一块 -->
        <template v-if="hasDraftAndFinalDifferent">
          <div class="generated-testcases-section">
            <h3>📋 AI 编写的测试用例（初稿）</h3>
            <div class="testcase-content stream-content-display">
              <div class="stream-content" v-html="formatMarkdown(generationResult.generated_test_cases || '')"></div>
            </div>
          </div>
          <div class="final-testcases-section">
            <h3>🎯 最终测试用例</h3>
            <div class="testcase-content stream-content-display">
              <div class="stream-content final-testcases" v-html="formatMarkdown(generationResult.final_test_cases || '')"></div>
            </div>
          </div>
        </template>
        <div v-else-if="displayCasesContent" class="final-testcases-section">
          <h3>{{ casesSectionTitle }}</h3>
          <div class="testcase-content stream-content-display">
            <div class="stream-content final-testcases" v-html="formatMarkdown(displayCasesContent)"></div>
          </div>
        </div>

        <!-- AI评审意见 -->
        <div v-if="generationResult.review_feedback" class="review-feedback-section">
          <h3>🔍 AI评审意见</h3>
          <div class="review-content stream-content-display">
            <div class="stream-content" v-html="formatMarkdown(generationResult.review_feedback || '')"></div>
          </div>
        </div>

        <div v-if="isPartialSuccess" class="failure-tip">
          <p>评审或最终优化阶段未完成，已保留可用的 AI 初稿。您仍可下载、保存，或在下方继续优化。</p>
          <p v-if="generationResult.error_message" class="failure-detail">{{ generationResult.error_message }}</p>
          <button type="button" class="task-detail-link-btn" @click="goToTaskDetail">
            前往任务详情继续优化 →
          </button>
        </div>

        <!-- 操作按钮 -->
        <div v-if="hasUsableCases" class="actions-section">
          <button class="download-btn" @click="downloadTestCases">
            <span>📥 下载测试用例(.xlsx)</span>
          </button>
          <button class="export-btn" @click="exportResult('feishu')">
            <span>🧠 飞书思维导图</span>
          </button>
          <button class="export-btn" @click="exportResult('xmind')">
            <span>🗺️ XMind</span>
          </button>
          <button class="save-btn" @click="saveToTestCaseRecords">
            <span>💾 保存到用例记录</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api'
import {
  getDifyKnowledgeBases,
  getDifyKnowledgeBaseDocuments,
  getKbFunctions,
  previewKbReference as previewKbReferenceApi,
  exportTaskResult
} from '@/api/requirement-analysis'
import { getDifyBindings } from '@/api/kb-hub'
import { useKbHubStore } from '@/stores/kb-hub'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import { buildWorksheetFromMarkdown } from '@/utils/testcaseExport'
import { formatGraphExpansionHint } from '@/utils/kgLabels'
import { getKgExpandRefs } from '@/api/knowledge-graph'

export default {
  name: 'RequirementAnalysisView',
  data() {
    return {
      // 手动输入需求
      manualInput: {
        title: '',
        description: '',
        swaggerText: ''
      },

      // 文件上传
      selectedFile: null,
      documentTitle: '',
      selectedProject: '',
      projects: [],
      isDragOver: false,

      // 生成状态
      isGenerating: false,
      currentTaskId: null,
      progressText: '准备开始生成...',
      currentStep: 0,
      pollInterval: null,
      eventSource: null,

      // 配置检查（与上游一致）
      showConfigGuide: false,
      checkingConfig: false,
      configStatus: {
        writer_model: {},
        writer_prompt: {},
        reviewer_model: {},
        reviewer_prompt: {},
        generation_config: {}
      },
      globalOutputMode: 'stream',

      // Skill 预设
      selectedSkillId: '',
      activeSkills: [],

      // 知识库(业务大脑)
      enableKnowledgeBase: false,
      projectKbs: [],
      projectEngine: '',  // 由 store.loadProjectKbs 判定：dify | native
      loadingProjectKbs: false,
      selectedKbIds: [],  // 用户在「项目+知识库」卡里勾选的 KB 子集（默认全选）
      // 知识中枢引擎（dify / native）统一走 stores/kb-hub.js，本页只读
      // 旧 Dify 知识库字段（保留兼容）
      difyConfigs: [],
      selectedDifyConfigId: '',
      knowledgeBases: [],
      selectedDatasetId: '',
      selectedDatasetName: '',
      loadingKnowledgeBases: false,
      kbTopK: 5,
      kbReferenceMode: 'hybrid',
      kbDocuments: [],
      loadingKbDocuments: false,
      selectedDocumentIds: [],
      kbFunctions: [],
      loadingKbFunctions: false,
      selectedFunctionIds: [],
      kgExpandPreview: null,
      kgExpandLoading: false,
      previewingKb: false,
      showKbPreview: false,
      kbPreviewText: '',
      kbPreviewMeta: null,
      kbPreviewWarnings: [],
      kbPreviewLength: 0,

      // 参考截图（带角色，与需求正文分离）
      imageAttachments: [],
      uploadingImages: false,

      // 生成完成后继续优化
      refinementInstructions: '',
      refineImageAttachments: [],
      uploadingRefineImages: false,

      // 流式内容累积（与上游一致）
      streamedContent: '',
      streamedReviewContent: '',
      reasoningContent: '',
      finalTestCases: '',
      showReviewStep: true,
      _localStreamPos: 0,
      _typingTimer: null,
      _typingQueueWriter: '',
      _typingQueueReview: '',
      _typingQueueFinal: '',
      _streamRemainder: '',

      // 生成结果
      showResults: false,
      generationResult: null
    }
  },

  computed: {
    kbHubStore() {
      return useKbHubStore()
    },
    currentProjectId() {
      return this.selectedProject || ''
    },
    canGenerateManual() {
      return this.manualInput.title.trim() &&
             this.manualInput.description.trim() &&
             this.manualInput.description.length <= 2000
    },
    displayStatusText() {
      const s = this.generationResult?.status
      if (this.isPartialSuccess) return '部分完成（已保留初稿）'
      if (s === 'failed') return '生成失败'
      if (this.showResults) return '生成完成'
      return this.progressText
    },
    graphExpansionHint() {
      return formatGraphExpansionHint(this.generationResult?.kb_context_meta)
    },
    kgExpandPreviewText() {
      const preview = this.kgExpandPreview
      if (!preview) return ''
      const fnCount = (preview.function_ids || []).length
      const docCount = (preview.document_ids || []).length
      const parts = []
      if (fnCount > 0) parts.push(`${fnCount} 个功能模块`)
      if (docCount > 0) parts.push(`${docCount} 份文档`)
      if (!parts.length) return ''
      let text = `生成时将参考 ${parts.join('、')}`
      if (preview.expanded) {
        const hint = formatGraphExpansionHint({
          graph_summary: preview.graph_summary,
          graph_expansion: preview.meta
        })
        if (hint) text += `（${hint}）`
      }
      if (preview.prompt_summary_chars > 0) {
        text += `；Prompt 将注入图谱摘要 ${preview.prompt_summary_chars} 字（≤2048）`
      }
      return text
    },
    hasUsableCases() {
      return !!(this.displayCasesContent && String(this.displayCasesContent).trim())
    },
    displayCasesContent() {
      const r = this.generationResult
      return (
        r?.final_test_cases ||
        r?.generated_test_cases ||
        this.finalTestCases ||
        this.streamedContent ||
        ''
      )
    },
    hasDraftAndFinalDifferent() {
      const g = (this.generationResult?.generated_test_cases || '').trim()
      const f = (this.generationResult?.final_test_cases || '').trim()
      return !!(g && f && g !== f)
    },
    casesSectionTitle() {
      const g = (this.generationResult?.generated_test_cases || '').trim()
      const f = (this.generationResult?.final_test_cases || '').trim()
      if (f && (!g || g === f)) return '📋 测试用例'
      if (g && !f) return '📋 测试用例（初稿）'
      return '📋 测试用例'
    },
    displayFinalCases() {
      return this.displayCasesContent
    },
    isPartialSuccess() {
      const r = this.generationResult
      if (!r) return false
      const hasDraft = !!(r.generated_test_cases || r.final_test_cases || this.streamedContent)
      if (r.status === 'failed' && hasDraft) return true
      if (r.status === 'completed' && (r.error_message || '').trim()) return true
      return false
    },
    resultTitle() {
      if (this.isPartialSuccess) return '⚠️ 用例已生成（部分阶段未完成）'
      if (this.generationResult?.status === 'failed') return '❌ 用例生成失败'
      return '✅ 测试用例生成完成'
    },
    canSaveToCaseRecords() {
      return this.hasUsableCases
    },
    canSubmitContinueRefine() {
      const hasText = (this.refinementInstructions || '').trim().length > 0
      const hasImages = this.refineImageAttachments.length > 0
      return (hasText || hasImages) && !!(this.generationResult?.task_id || this.currentTaskId)
    },
    canPreviewKb() {
      return this.enableKnowledgeBase &&
        this.selectedDifyConfigId &&
        this.selectedDatasetId &&
        (this.selectedDocumentIds.length > 0 || this.selectedFunctionIds.length > 0)
    },
    allKbSelected() {
      return this.projectKbs.length > 0 &&
        this.projectKbs.every(kb => this.selectedKbIds.includes(kb.id))
    },
    kbDocumentNameMap() {
      const map = {}
      for (const doc of this.kbDocuments) {
        map[String(doc.id)] = doc.name || String(doc.id)
      }
      return map
    }
  },

  watch: {
    selectedDatasetId: 'scheduleKgExpandPreview',
    selectedDocumentIds: { handler: 'scheduleKgExpandPreview', deep: true },
    selectedFunctionIds: { handler: 'scheduleKgExpandPreview', deep: true },
    currentProjectId: {
      handler(val) {
        if (val && this.enableKnowledgeBase) {
          this.loadProjectKbs(val)
        } else {
          this.projectKbs = []
        }
      },
      immediate: false,
    },
    enableKnowledgeBase: {
      handler(val) {
        if (val && this.currentProjectId) {
          this.loadProjectKbs(this.currentProjectId)
        }
      },
    },
  },

  mounted() {
    this.loadProjects()
    this.checkConfigStatus()
    this.loadDifyConfigs()
    this.kbHubStore.loadDefaultEngine()
    this.loadActiveSkills()
  },

  beforeUnmount() {
    if (this.pollInterval) clearInterval(this.pollInterval)
    if (this._kgExpandTimer) clearTimeout(this._kgExpandTimer)
    if (this._typingTimer) {
      clearInterval(this._typingTimer)
      this._typingTimer = null
    }
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
  },

  methods: {
    async loadProjectKbs(projectId) {
      if (!projectId) {
        this.projectKbs = []
        this.projectEngine = ''
        this.selectedKbIds = []
        return
      }
      this.loadingProjectKbs = true
      try {
        // 调用 /api/kb-hub/config/project-kbs/，后端自动判定引擎
        const data = await this.kbHubStore.loadProjectKbs(projectId)
        if (data) {
          this.projectKbs = data.items || []
          this.projectEngine = data.engine || ''
          this.selectedKbIds = this.projectKbs.map(kb => kb.id)
          // 把 Dify 数据集 id 和 native KB id 区分开（兼容后端 dataset_id/kb_id 字段）
          // project-kbs API 返回的 id 形如 'dify:dataset_xxx' 或 'native:123'
        } else {
          this.projectKbs = []
          this.projectEngine = ''
          this.selectedKbIds = []
        }
      } catch (err) {
        console.warn('加载项目知识库失败:', err)
        this.projectKbs = []
        this.projectEngine = ''
        this.selectedKbIds = []
      } finally {
        this.loadingProjectKbs = false
      }
    },

    toggleAllKbs() {
      if (this.allKbSelected) {
        this.selectedKbIds = []
      } else {
        this.selectedKbIds = this.projectKbs.map(kb => kb.id)
      }
    },

    scheduleKgExpandPreview() {
      if (this._kgExpandTimer) clearTimeout(this._kgExpandTimer)
      this._kgExpandTimer = setTimeout(() => this.refreshKgExpandPreview(), 400)
    },

    async refreshKgExpandPreview() {
      if (!this.enableKnowledgeBase || !this.selectedDatasetId) {
        this.kgExpandPreview = null
        return
      }
      const fnIds = this.selectedFunctionIds || []
      const docIds = this.selectedDocumentIds || []
      if (fnIds.length === 0 && docIds.length === 0) {
        this.kgExpandPreview = null
        return
      }
      this.kgExpandLoading = true
      try {
        const response = await getKgExpandRefs({
          datasetId: this.selectedDatasetId,
          functionIds: fnIds,
          documentIds: docIds,
          depth: 2
        })
        this.kgExpandPreview = response.data
      } catch {
        this.kgExpandPreview = null
      } finally {
        this.kgExpandLoading = false
      }
    },

    async checkConfigStatus() {
      try {
        this.checkingConfig = true
        const response = await api.get('/requirement-analysis/config/check/')
        this.configStatus = response.data
        const w = response.data.writer_model
        const wp = response.data.writer_prompt
        const r = response.data.reviewer_model
        const rp = response.data.reviewer_prompt
        const gc = response.data.generation_config
        const ready = (w && w.configured && w.enabled) && (wp && wp.configured && wp.enabled) &&
          (r && r.configured && r.enabled) && (rp && rp.configured && rp.enabled) &&
          (gc && gc.configured)
        this.showConfigGuide = !ready
        if (ready && gc) {
          if (gc.default_output_mode) this.globalOutputMode = gc.default_output_mode
          // 根据生成配置的enable_auto_review决定是否显示评审步骤
          if (gc.enable_auto_review !== null && gc.enable_auto_review !== undefined) {
            this.showReviewStep = gc.enable_auto_review
          } else {
            this.showReviewStep = true  // 默认显示
          }
        }
      } catch {
        this.showConfigGuide = false
      } finally {
        this.checkingConfig = false
      }
    },

    goToConfig() {
      if (!this.configStatus.generation_config || !this.configStatus.generation_config.configured) {
        this.$router.push('/configuration/generation-config')
        return
      }
      if (!this.configStatus.writer_prompt?.configured || !this.configStatus.writer_prompt?.enabled) {
        this.$router.push('/ai-generation/prompt-config')
        return
      }
      if (!this.configStatus.writer_model?.configured || !this.configStatus.writer_model?.enabled) {
        this.$router.push('/configuration/ai-model')
        return
      }
      this.$router.push('/configuration/ai-model')
    },

    goToSkillConfig() {
      this.$router.push('/ai-generation/skill-config')
    },

    async loadActiveSkills() {
      try {
        const response = await api.get('/requirement-analysis/skills/active/')
        this.activeSkills = response.data || []
      } catch (error) {
        console.error('加载 Skill 列表失败:', error)
      }
    },

    async loadProjects() {
      try {
        const response = await api.get('/projects/')
        this.projects = response.data.results || response.data
      } catch (error) {
        console.error('加载项目失败:', error)
      }
    },

    handleDrop(event) {
      event.preventDefault()
      this.isDragOver = false
      const files = event.dataTransfer.files
      if (files.length > 0) {
        this.handleFileSelect({ target: { files } })
      }
    },

    handleFileSelect(event) {
      const file = event.target.files[0]
      if (file) {
        const allowedTypes = [
          'application/pdf',
          'application/msword',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'text/plain'
        ]

        if (allowedTypes.includes(file.type) ||
            file.name.match(/\.(pdf|doc|docx|txt)$/i)) {
        this.selectedFile = file
          this.documentTitle = file.name.replace(/\.[^/.]+$/, "")
        } else {
          ElMessage.error('请选择 PDF、Word 或 TXT 格式的文件')
        }
      }
    },

    removeFile() {
      this.selectedFile = null
      this.documentTitle = ''
      this.$refs.fileInput.value = ''
    },

    async loadDifyConfigs() {
      try {
        const response = await api.get('/assistant/config/dify/all/')
        this.difyConfigs = Array.isArray(response.data) ? response.data : []
        const active = this.difyConfigs.find(cfg => cfg.is_active)
        if (active && !this.selectedDifyConfigId) {
          this.selectedDifyConfigId = active.id
        }
      } catch (error) {
        console.error('加载 Dify 配置失败:', error)
        this.difyConfigs = []
      }
    },

    onKnowledgeBaseToggle() {
      if (!this.enableKnowledgeBase) {
        this.resetKbSelection()
        return
      }
      if (this.selectedDifyConfigId) {
        this.loadKnowledgeBases()
      }
    },

    resetKbSelection() {
      this.selectedDatasetId = ''
      this.selectedDatasetName = ''
      this.knowledgeBases = []
      this.kbDocuments = []
      this.kbFunctions = []
      this.selectedDocumentIds = []
      this.selectedFunctionIds = []
      this.kbPreviewText = ''
      this.kbPreviewMeta = null
      this.showKbPreview = false
    },

    async onDifyConfigChange() {
      this.resetKbSelection()
      if (this.selectedDifyConfigId) {
        await this.loadKnowledgeBases()
      }
    },

    async onDatasetChange() {
      const selected = this.knowledgeBases.find(kb => String(kb.id) === String(this.selectedDatasetId))
      this.selectedDatasetName = selected ? selected.name : ''
      this.selectedDocumentIds = []
      this.selectedFunctionIds = []
      this.kbDocuments = []
      this.kbFunctions = []
      if (this.selectedDatasetId) {
        await Promise.all([this.loadKbDocuments(), this.loadKbFunctions()])
      }
    },

    async loadKbDocuments() {
      if (!this.selectedDifyConfigId || !this.selectedDatasetId) return
      this.loadingKbDocuments = true
      try {
        const response = await getDifyKnowledgeBaseDocuments({
          dify_config_id: this.selectedDifyConfigId,
          dataset_id: this.selectedDatasetId,
          limit: 200
        })
        this.kbDocuments = response.data?.data || []
      } catch (error) {
        console.error('加载知识库文档失败:', error)
        this.kbDocuments = []
        ElMessage.error(error.response?.data?.detail || '加载知识库文档失败')
      } finally {
        this.loadingKbDocuments = false
      }
    },

    async loadKbFunctions() {
      if (!this.selectedDatasetId) return
      this.loadingKbFunctions = true
      try {
        const response = await getKbFunctions({
          dify_dataset_id: this.selectedDatasetId,
          is_active: 'true'
        })
        this.kbFunctions = response.data?.results || response.data || []
      } catch (error) {
        console.error('加载功能模块失败:', error)
        this.kbFunctions = []
      } finally {
        this.loadingKbFunctions = false
      }
    },

    buildKbPayload(title, requirementText) {
      if (!this.enableKnowledgeBase) {
        return {}
      }
      const projectId = this.currentProjectId
      if (!projectId) {
        return {}
      }
      return {
        enable_knowledge_base: true,
        project: projectId,
        title: title || '',
        requirement_text: requirementText || '',
        kb_top_k: 5,
        // 告知后端当前引擎（按项目自动判定）与用户勾选的 KB 列表（id 形如 'dify:xxx' 或 'native:xxx'）
        kb_engine: this.projectEngine,
        selected_kb_ids: this.selectedKbIds || [],
      }
    },

    validateKbSelection() {
      if (!this.enableKnowledgeBase) return true
      if (!this.currentProjectId) {
        ElMessage.error('请先选择项目')
        return false
      }
      if (this.projectKbs.length === 0) {
        ElMessage.error('该项目下没有可用的知识库，请先到「知识中枢 → 知识库管理」新建/绑定')
        return false
      }
      if (!this.selectedKbIds || this.selectedKbIds.length === 0) {
        ElMessage.error('请至少勾选一个知识库')
        return false
      }
      return true
    },

    async previewKbReference() {
      if (!this.canPreviewKb) {
        ElMessage.warning('请先选择参考文档或功能模块')
        return
      }

      this.previewingKb = true
      try {
        const title = this.manualInput.title || this.documentTitle || '预览'
        const requirementText = this.manualInput.description
          ? `需求标题: ${this.manualInput.title}\n\n需求描述:\n${this.manualInput.description}`
          : (this.documentTitle ? `文档标题: ${this.documentTitle}` : title)
        const payload = this.buildKbPayload(title, requirementText)
        const response = await previewKbReferenceApi(payload)
        this.kbPreviewText = response.data?.context_preview || ''
        this.kbPreviewMeta = response.data?.meta || null
        this.kbPreviewWarnings = response.data?.meta?.warnings || []
        this.kbPreviewLength = response.data?.context_length || 0
        this.showKbPreview = true
        if (!response.data?.has_content) {
          ElMessage.warning('未能获取有效参考内容，请检查文档或检索配置')
        } else if (this.kbPreviewWarnings.length) {
          ElMessage.warning(this.kbPreviewWarnings[0])
        }
      } catch (error) {
        console.error('预览知识库参考失败:', error)
        ElMessage.error(error.response?.data?.detail || '预览失败')
      } finally {
        this.previewingKb = false
      }
    },

    async loadKnowledgeBases() {
      if (!this.selectedDifyConfigId) return
      this.loadingKnowledgeBases = true
      try {
        const response = await getDifyKnowledgeBases({
          dify_config_id: this.selectedDifyConfigId,
          limit: 100
        })
        this.knowledgeBases = response.data?.data || []
        if (this.knowledgeBases.length === 0) {
          ElMessage.warning('未找到可用知识库，请确认 Dify 中已创建知识库并开启 API 访问')
        }
      } catch (error) {
        console.error('加载知识库失败:', error)
        this.knowledgeBases = []
        ElMessage.error(error.response?.data?.detail || '加载 Dify 知识库失败')
      } finally {
        this.loadingKnowledgeBases = false
      }
    },

    buildImageAttachmentsPayload() {
      return this.imageAttachments.map((item) => {
        const entry = {
          url: item.url,
          role: item.role || 'ui_layout'
        }
        if ((item.caption || '').trim()) {
          entry.caption = item.caption.trim()
        }
        if (entry.role === 'operation_step') {
          entry.step_index = item.step_index || 1
        }
        return entry
      })
    },

    reindexOperationSteps() {
      let step = 1
      for (const item of this.imageAttachments) {
        if (item.role === 'operation_step') {
          item.step_index = step
          step += 1
        }
      }
    },

    onImageRoleChange(item) {
      if (item.role === 'operation_step' && !item.step_index) {
        item.step_index = this.imageAttachments.filter(a => a.role === 'operation_step').length
      }
      this.reindexOperationSteps()
    },

    removeImageAttachment(idx) {
      const item = this.imageAttachments[idx]
      if (item?.previewUrl) {
        URL.revokeObjectURL(item.previewUrl)
      }
      this.imageAttachments.splice(idx, 1)
      this.reindexOperationSteps()
    },

    async handleImageFileSelect(event) {
      const files = Array.from(event.target.files || [])
      event.target.value = ''
      if (!files.length) return

      for (const file of files) {
        if (this.imageAttachments.length >= 12) {
          ElMessage.warning('最多上传 12 张截图')
          break
        }
        if (!file.type?.startsWith('image/')) {
          ElMessage.warning(`${file.name} 不是图片文件，已跳过`)
          continue
        }
        await this.uploadSingleImage(file)
      }
    },

    async uploadSingleImage(file) {
      this.uploadingImages = true
      try {
        const fd = new FormData()
        fd.append('files', file)
        const resp = await api.post('/requirement-analysis/testcase-generation/upload-images/', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        const url = (resp.data?.image_data_urls || [])[0]
        if (!url) {
          ElMessage.error('图片解析失败')
          return
        }
        this.imageAttachments.push({
          url,
          role: 'ui_layout',
          caption: '',
          step_index: null,
          previewUrl: URL.createObjectURL(file),
          name: file.name
        })
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '上传截图失败')
      } finally {
        this.uploadingImages = false
      }
    },

    formatFileSize(bytes) {
      if (bytes === 0) return '0 Bytes'
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    },

    async generateFromManualInput() {
      if (!this.canGenerateManual) {
        ElMessage.error('请填写完整的需求信息')
        return
      }

      const requirementText = `需求标题: ${this.manualInput.title}\n\n需求描述:\n${this.manualInput.description}`

      // 解析可选的 Swagger / OpenAPI 接口文档
      let swaggerData = null
      const rawSwagger = (this.manualInput.swaggerText || '').trim()
      if (rawSwagger) {
        try {
          swaggerData = JSON.parse(rawSwagger)
        } catch (e) {
          ElMessage.error('接口文档 JSON 解析失败，请检查 Swagger/OpenAPI 内容格式')
          return
        }
      }

      await this.startGeneration(this.manualInput.title, requirementText, this.selectedProject, swaggerData)
    },

    async generateFromDocument() {
      if (!this.selectedFile || !this.documentTitle) {
        ElMessage.error('请选择文件并输入文档标题')
        return
      }

      try {
        // 首先上传并提取文档内容
        const formData = new FormData()
        formData.append('title', this.documentTitle)
        formData.append('file', this.selectedFile)
        if (this.selectedProject) {
          formData.append('project', this.selectedProject)
        }

        ElMessage.info('正在提取文档内容...')
        const uploadResponse = await api.post('/requirement-analysis/documents/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        })

        // 提取文档内容
        const extractResponse = await api.get(`/requirement-analysis/documents/${uploadResponse.data.id}/extract_text/`)
        const extractedText = extractResponse.data.extracted_text

        if (!extractedText || extractedText.trim().length === 0) {
          ElMessage.error('无法从文档中提取到有效内容，请检查文档格式')
          return
        }

        const requirementText = `文档标题: ${this.documentTitle}\n\n文档内容:\n${extractedText}`

        await this.startGeneration(this.documentTitle, requirementText, this.selectedProject)

      } catch (error) {
        console.error('文档处理失败:', error)
        ElMessage.error('文档处理失败: ' + (error.response?.data?.error || error.message))
      }
    },

    async startGeneration(title, requirementText, projectId, swaggerData) {
      if (!this.validateKbSelection()) {
        return
      }

      this.isGenerating = true
      this.currentStep = 1
      this.progressText = '正在创建生成任务...'

      // 重置流式内容（与上游一致）
      this.streamedContent = ''
      this.streamedReviewContent = ''
      this.reasoningContent = ''
      this.finalTestCases = ''
      this._streamRemainder = ''

      try {
        // 调用新的生成API（传递 output_mode 以便后端做流式/完整输出）
        const requestData = {
          title: title,
          requirement_text: requirementText,
          use_writer_model: true,
          use_reviewer_model: true,
          output_mode: this.globalOutputMode || 'stream'
        }

        // 如果选择了 Skill，传递 skill_id
        if (this.selectedSkillId) {
          requestData.skill_id = this.selectedSkillId
        }

        // 如果选择了项目，添加到请求中
        if (projectId) {
          requestData.project = projectId
        }

        // 如果粘贴了 Swagger / OpenAPI 接口文档，传入后端自动识别
        if (swaggerData && typeof swaggerData === 'object') {
          requestData.swagger_data = swaggerData
        }

        Object.assign(requestData, this.buildKbPayload(title, requirementText))

        const imagePayload = this.buildImageAttachmentsPayload()
        if (imagePayload.length) {
          requestData.image_attachments = imagePayload
        }

        const response = await api.post('/requirement-analysis/testcase-generation/generate/', requestData)

        this.currentTaskId = response.data.task_id
        this.progressText = '任务已创建，正在处理中...'

        ElMessage.success('测试用例生成任务已启动')

        if (this.globalOutputMode === 'stream') {
          this.startStreamingProgress()
        } else {
          this.startPolling()
        }
      } catch (error) {
        console.error('创建生成任务失败:', error)
        ElMessage.error('创建任务失败: ' + (error.response?.data?.detail || error.response?.data?.error || error.message))
        this.isGenerating = false
      }
    },

    startPolling() {
      this.pollInterval = setInterval(async () => {
        try {
          const response = await api.get(`/requirement-analysis/testcase-generation/${this.currentTaskId}/progress/`)
          const task = response.data

          console.log(`任务状态: ${task.status}, 进度: ${task.progress}%`)

          // 轮询模式下也支持“流式输出”：从后端 stream_buffer 增量解析事件并更新 UI
          this.applyStreamBuffer(task)

          // 更新进度显示
          if (task.status === 'generating') {
            this.currentStep = 2
            this.progressText = `正在编写测试用例... ${task.progress || 0}%`
          } else if (task.status === 'reviewing') {
            this.currentStep = 3
            this.progressText = `正在评审测试用例... ${task.progress || 0}%`
          } else if (task.status === 'revising') {
            this.currentStep = 3
            this.progressText = `正在生成最终版用例... ${task.progress || 0}%`
          } else if (task.status === 'completed') {
            this.currentStep = 4
            this.progressText = '生成完成！'

            // 任务完成，显示结果
            this.generationResult = task
            this.showResults = true
            this.isGenerating = false

            clearInterval(this.pollInterval)
            this.pollInterval = null

            ElMessage.success('测试用例生成完成！')
            return
          } else if (task.status === 'failed') {
            this.progressText = '生成失败'
            this.isGenerating = false
            this.generationResult = task
            this.showResults = true
            this.currentStep = 4

            clearInterval(this.pollInterval)
            this.pollInterval = null

            const hasDraft = !!(task.generated_test_cases || task.final_test_cases || this.streamedContent)
            if (hasDraft) {
              ElMessage.warning('评审/最终阶段未完成，已保留可用初稿')
            } else {
              ElMessage.error('测试用例生成失败: ' + (task.error_message || '未知错误'))
            }
            return
          }

        } catch (error) {
          console.error('检查任务进度失败:', error)
          // 401（token 过期/无效）时停止轮询，避免一直刷请求导致“流式最后报错”的错觉
          const status = error?.response?.status
          const code = error?.response?.data?.code
          if (status === 401 || code === 'token_not_valid') {
            this.progressText = '登录已过期，请重新登录后再试'
            this.isGenerating = false
            if (this.pollInterval) {
              clearInterval(this.pollInterval)
              this.pollInterval = null
            }
            return
          }
          // 其他错误：继续轮询，不中断（网络波动/临时 5xx）
        }
      }, 1500)
    },

    applyStreamBuffer(task) {
      try {
        const buf = task?.stream_buffer || ''
        if (!buf) {
          // complete 模式兜底：后端完成后会写 final_test_cases
          if (!this.finalTestCases && task?.final_test_cases) this.finalTestCases = task.final_test_cases
          if (!this.streamedReviewContent && task?.review_feedback) this.streamedReviewContent = task.review_feedback
          return
        }

        const startPos = Number.isFinite(this._localStreamPos) ? this._localStreamPos : 0
        if (startPos >= buf.length) return

        const chunk = buf.slice(startPos)
        this._localStreamPos = buf.length

        // 跨轮询切片可能把一条 JSON 事件截断，先与上次残片拼接再解析
        const merged = (this._streamRemainder || '') + chunk
        const parts = merged.split('\n')
        this._streamRemainder = parts.pop() || ''
        const lines = parts.map(l => l.trim()).filter(Boolean)
        for (const line of lines) {
          let data
          try {
            data = JSON.parse(line)
      } catch {
            continue
          }
          if (!data || typeof data !== 'object') continue

          if (data.type === 'content' && data.content) {
            this.enqueueTyping(data.content, 'writer')
          } else if (data.type === 'review_content' && data.content) {
            this.enqueueTyping(data.content, 'review')
          } else if (data.type === 'final_content' && data.content) {
            this.enqueueTyping(data.content, 'final')
          } else if (data.type === 'reasoning' && data.content) {
            this.reasoningContent += data.content
          }
        }

        // 兜底：如果后端已经写入最终文本但没有 event（例如 complete 模式）
        if (!this.finalTestCases && task?.final_test_cases) this.finalTestCases = task.final_test_cases
        if (!this.streamedReviewContent && task?.review_feedback) this.streamedReviewContent = task.review_feedback
      } catch (e) {
        // ignore
      }
    },

    enqueueTyping(text, channel) {
      // “逐字输出”用前端打字机效果实现，避免后端每字一写数据库造成性能问题
      if (!text) return
      const s = String(text)
      if (channel === 'review') this._typingQueueReview += s
      else if (channel === 'final') this._typingQueueFinal += s
      else this._typingQueueWriter += s
      if (this._typingTimer) return

      const drainQueue = (queueKey, targetKey, batchSize = 1) => {
        const queue = this[queueKey]
        if (!queue) return false
        const n = Math.min(batchSize, queue.length)
        this[targetKey] += queue.slice(0, n)
        this[queueKey] = queue.slice(n)
        return true
      }

      // 队列积压时加速展示，避免“后端已写完、前端还在打字”
      this._typingTimer = setInterval(() => {
        if (!this._typingQueueWriter && !this._typingQueueReview && !this._typingQueueFinal) {
          clearInterval(this._typingTimer)
          this._typingTimer = null
          return
        }
        const backlog = (this._typingQueueWriter?.length || 0)
          + (this._typingQueueReview?.length || 0)
          + (this._typingQueueFinal?.length || 0)
        const batchSize = backlog > 500 ? 40 : backlog > 100 ? 15 : 1

        if (drainQueue('_typingQueueFinal', 'finalTestCases', batchSize)) return
        if (drainQueue('_typingQueueReview', 'streamedReviewContent', batchSize)) return
        drainQueue('_typingQueueWriter', 'streamedContent', batchSize)
      }, 16)
    },

    startStreamingProgress() {
      // JWT 鉴权下 EventSource 无法携带 Bearer Header，且旧代码固定端口 8001，
      // 会导致“流式输出错误/一直 0 字符”。这里改为统一用轮询+stream_buffer 实现流式展示。
      this.startPolling()
      return
    },

    // 旧 SSE 逻辑已移除：当前项目使用 JWT，EventSource 无法携带 Bearer Token，
    // 统一使用轮询 + 后端 stream_buffer 实现流式展示。

    async fetchFinalResult() {
      try {
        const response = await api.get(`/requirement-analysis/testcase-generation/${this.currentTaskId}/progress/`)
        const task = response.data

        this.generationResult = task
        this.showResults = true
        this.isGenerating = false
        this.currentStep = 4

        if (task.status === 'failed') {
          this.progressText = '生成失败'
          ElMessage.error('测试用例生成失败: ' + (task.error_message || '未知错误'))
          return
        }

        this.progressText = '生成完成！'

        // 设置最终版用例（如果还没有通过流式接收完整）- 与上游一致
        if (task.final_test_cases) {
          console.log('📝 从task对象获取最终用例')
          // 无论this.finalTestCases是否已有值，都用最新的final_test_cases覆盖
          // 这样确保完整输出模式下也能正确显示最终版用例
          this.finalTestCases = task.final_test_cases
        }

        // 如果评审内容为空，从task对象中获取
        if (!this.streamedReviewContent && task.review_feedback) {
          console.log('📝 从task对象获取评审内容')
          this.streamedReviewContent = task.review_feedback
        }

        ElMessage.success('测试用例生成完成！')
      } catch (e) {
        this.isGenerating = false
        ElMessage.error('获取结果失败')
      }
    },

    formatMarkdown(text) {
      // 简单的 Markdown 格式化（与上游一致）
      if (!text) return ''
      let html = text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
      return html
    },

    cancelGeneration() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
        this.pollInterval = null
      }
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
      this.isGenerating = false
      this.currentTaskId = null
      ElMessage.info('已取消生成任务')
    },

    // 下载测试用例为xlsx文件（与页面展示使用同一正文源）
    async downloadTestCases() {
      try {
        const rawContent = this.displayCasesContent
        const taskId = this.generationResult?.task_id || this.currentTaskId
        if (!rawContent || !String(rawContent).trim()) {
          ElMessage.warning('当前没有可下载的用例内容')
          return
        }

        const worksheetData = buildWorksheetFromMarkdown(rawContent)
        const workbook = XLSX.utils.book_new()
        const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)

        const colCount = worksheetData[0]?.length || 6
        worksheet['!cols'] = Array.from({ length: colCount }, (_, i) => ({
          wch: i === 0 ? 14 : i === 1 ? 28 : i >= 3 && i <= 4 ? 36 : 12
        }))

        XLSX.utils.book_append_sheet(workbook, worksheet, '测试用例')
        const fileName = `测试用例_${taskId || 'export'}_${new Date().toISOString().slice(0, 10)}.xlsx`
        XLSX.writeFile(workbook, fileName)
        ElMessage.success('测试用例下载成功')
      } catch (error) {
        console.error('下载测试用例失败:', error)
        ElMessage.error('下载测试用例失败: ' + (error.message || '未知错误'))
      }
    },

    // 通过后端导出（支持团队模板列映射）：excel / feishu / xmind
    async exportResult(format) {
      const taskId = this.generationResult?.task_id || this.currentTaskId
      if (!taskId) {
        ElMessage.warning('当前没有可导出的任务')
        return
      }
      const labelMap = { excel: 'Excel', feishu: '飞书思维导图', xmind: 'XMind' }
      try {
        const res = await exportTaskResult(taskId, format)
        const blob = res.data
        const contentDisp = res.headers?.['content-disposition'] || ''
        let filename = `testcases.${format === 'excel' ? 'xlsx' : format === 'xmind' ? 'xmind' : 'md'}`
        const m = contentDisp.match(/filename\*=UTF-8''([^;]+)/)
        if (m) filename = decodeURIComponent(m[1])
        const url = window.URL.createObjectURL(new Blob([blob]))
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
        ElMessage.success(`${labelMap[format] || format} 导出成功`)
      } catch (error) {
        console.error('导出失败:', error)
        ElMessage.error('导出失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
      }
    },

    // 保存到用例记录
    async saveToTestCaseRecords() {
      try {
        // 调用后端API保存到记录
        const response = await api.post(`/requirement-analysis/testcase-generation/${this.generationResult.task_id}/save_to_records/`)

        if (response.data.already_saved) {
          ElMessage.info('测试用例已经保存过了')
        } else {
          const importedCount = response.data.imported_count || 0
          ElMessage.success(`测试用例已保存！已导入 ${importedCount} 条测试用例到测试用例管理系统`)
        }

        // 不跳转，留在当前页面
        // this.$router.push('/generated-testcases')
      } catch (error) {
        console.error('保存测试用例失败:', error)
        ElMessage.error('保存测试用例失败: ' + (error.response?.data?.error || error.message))
      }
    },

    goToTaskDetail() {
      const taskId = this.generationResult?.task_id || this.currentTaskId
      if (!taskId) {
        ElMessage.warning('暂无任务 ID')
        return
      }
      this.$router.push(`/ai-generation/task-detail/${taskId}`)
    },

    scrollToContinueRefine() {
      this.$nextTick(() => {
        const el = document.getElementById('continue-refine-panel')
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      })
    },

    buildRefineImagePayload() {
      return this.refineImageAttachments.map((item) => {
        const entry = { url: item.url, role: item.role || 'ui_layout' }
        if ((item.caption || '').trim()) entry.caption = item.caption.trim()
        if (entry.role === 'operation_step') entry.step_index = item.step_index || 1
        return entry
      })
    },

    reindexRefineOperationSteps() {
      let step = 1
      for (const item of this.refineImageAttachments) {
        if (item.role === 'operation_step') {
          item.step_index = step
          step += 1
        }
      }
    },

    onRefineImageRoleChange(item) {
      if (item.role === 'operation_step' && !item.step_index) {
        item.step_index = this.refineImageAttachments.filter(a => a.role === 'operation_step').length
      }
      this.reindexRefineOperationSteps()
    },

    removeRefineImage(idx) {
      const item = this.refineImageAttachments[idx]
      if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl)
      this.refineImageAttachments.splice(idx, 1)
      this.reindexRefineOperationSteps()
    },

    async handleRefineImageSelect(event) {
      const files = Array.from(event.target.files || [])
      event.target.value = ''
      for (const file of files) {
        if (this.refineImageAttachments.length >= 12) {
          ElMessage.warning('最多上传 12 张截图')
          break
        }
        if (!file.type?.startsWith('image/')) continue
        await this.uploadRefineImage(file)
      }
    },

    async uploadRefineImage(file) {
      this.uploadingRefineImages = true
      try {
        const fd = new FormData()
        fd.append('files', file)
        const resp = await api.post('/requirement-analysis/testcase-generation/upload-images/', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        const url = (resp.data?.image_data_urls || [])[0]
        if (!url) {
          ElMessage.error('图片解析失败')
          return
        }
        this.refineImageAttachments.push({
          url,
          role: 'ui_layout',
          caption: '',
          step_index: null,
          previewUrl: URL.createObjectURL(file),
          name: file.name
        })
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '上传截图失败')
      } finally {
        this.uploadingRefineImages = false
      }
    },

    async submitContinueRefine() {
      if (!this.canSubmitContinueRefine) {
        ElMessage.warning('请填写补充要求或上传新截图')
        return
      }
      const taskId = this.generationResult?.task_id || this.currentTaskId
      if (!taskId) {
        ElMessage.warning('暂无任务 ID')
        return
      }
      if (!confirm('将基于当前用例按您的补充要求重新优化，是否继续？')) {
        return
      }

      const payload = {
        refinement_instructions: (this.refinementInstructions || '').trim()
      }
      const images = this.buildRefineImagePayload()
      if (images.length) payload.image_attachments = images

      try {
        await api.post(`/requirement-analysis/testcase-generation/${taskId}/continue-refine/`, payload)

        for (const item of this.refineImageAttachments) {
          if (item.previewUrl) URL.revokeObjectURL(item.previewUrl)
        }
        this.refinementInstructions = ''
        this.refineImageAttachments = []

        this.showResults = false
        this.isGenerating = true
        this.currentStep = 2
        this.progressText = '正在根据补充要求优化用例...'
        this.streamedContent = ''
        this.streamedReviewContent = ''
        this.finalTestCases = ''
        this._localStreamPos = 0
        this._streamRemainder = ''
        this.generationResult = null

        ElMessage.success('已开始优化，请稍候…')
        this.startPolling()
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '继续优化失败')
      }
    },

    resetGeneration() {
      // 重置生成状态
      this.isGenerating = false;
      this.currentTaskId = null;
      this.progressText = '准备开始生成...';
      this.currentStep = 0;
      this.showResults = false;
      this.generationResult = null;
      this.refinementInstructions = '';
      for (const item of this.refineImageAttachments) {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      }
      this.refineImageAttachments = [];

      // 重置流式内容（与上游一致）
      this.streamedContent = ''
      this.streamedReviewContent = ''
      this.reasoningContent = ''
      this.finalTestCases = ''
      this._streamRemainder = ''

      if (this.pollInterval) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
      }
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
    },

    // 格式化日期时间
    formatDateTime(dateTimeString) {
      if (!dateTimeString) return '';

      try {
        const date = new Date(dateTimeString);
        return date.toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        });
      } catch (error) {
        console.error('日期格式化失败:', error);
        return dateTimeString;
      }
    }
  }
}
</script>

<style scoped>
.requirement-analysis {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  text-align: center;
  margin-bottom: 40px;
}

.page-header h1 {
  font-size: 2.5rem;
  color: #2c3e50;
  margin-bottom: 10px;
}

.page-header p {
  color: #666;
  font-size: 1.1rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.guide-config-modal {
  background: white;
  border-radius: 12px;
  padding: 24px;
  max-width: 420px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
}
.guide-header h2 { margin: 0 0 8px 0; font-size: 1.25rem; color: #2c3e50; }
.guide-header p { margin: 0; color: #666; font-size: 0.95rem; }
.guide-actions { margin-top: 20px; display: flex; gap: 12px; align-items: center; }
.guide-actions .generate-manual-btn { margin: 0; }
.skip-action { cursor: pointer; color: #666; font-size: 0.9rem; text-decoration: underline; }

.output-mode-section { margin-bottom: 24px; }

/* ====== 项目 + 知识库 合并卡 ====== */
.project-kb-section { margin-bottom: 24px; }
.project-kb-card {
  background: #fff;
  border: 1px solid #e1e8ed;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}
.project-kb-card h3 {
  margin: 0 0 6px 0;
  font-size: 1.05rem;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
}
.project-kb-card .card-divider { color: #c0c4cc; font-weight: 400; margin: 0 2px; }
.project-kb-card .card-desc { margin: 0 0 16px 0; color: #606266; font-size: 13px; line-height: 1.6; }
.project-kb-card .form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.project-kb-card .form-row:last-child { margin-bottom: 0; }
.project-kb-card .form-label {
  flex-shrink: 0;
  width: 70px;
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  text-align: right;
}
.project-kb-card .required-mark::before { content: '*'; color: #f56c6c; margin-right: 2px; }
.project-kb-card .form-control { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.project-kb-card .field-hint { font-size: 12px; }
.project-kb-card .field-hint.warn { color: #e6a23c; }
.project-kb-card .field-hint.ok { color: #67c23a; }

.kb-block {
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  padding: 14px 16px;
  background: #fafbfc;
  transition: all 0.2s ease;
}
.kb-block-disabled {
  opacity: 0.55;
  filter: grayscale(0.5);
  background: #f5f7fa;
  border-color: #e4e7ed;
  position: relative;
}
.kb-block-disabled .kb-toggle { cursor: not-allowed; }
.kb-block-disabled .kb-toggle input { cursor: not-allowed; }
.kb-block-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.kb-block .kb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #303133;
  cursor: pointer;
}
.kb-block .kb-toggle input { width: 16px; height: 16px; cursor: pointer; }
.kb-block .kb-toggle input:disabled { cursor: not-allowed; }
.kb-block .kb-summary { font-size: 12px; }

.kb-locked-tip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #fff7e6;
  border: 1px solid #ffe7ba;
  border-radius: 6px;
  margin-top: 4px;
}
.kb-locked-tip .lock-icon {
  font-size: 24px;
  flex-shrink: 0;
  line-height: 1;
}
.kb-locked-tip .lock-content { display: flex; flex-direction: column; gap: 2px; }
.kb-locked-tip .lock-content strong { color: #d48806; font-size: 13px; }
.kb-locked-tip .lock-content .lock-sub { color: #8c6e3a; font-size: 12px; }

.kb-empty-tip {
  padding: 12px 14px;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 6px;
  color: #b88230;
  font-size: 13px;
  line-height: 1.6;
  margin-top: 8px;
}
.kb-empty-tip a { color: var(--el-color-primary); text-decoration: underline; margin: 0 2px; }

.kb-checklist { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.kb-checklist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #606266;
  padding: 0 4px;
}
.kb-checklist-header .kb-link {
  color: var(--el-color-primary);
  cursor: pointer;
  font-size: 12px;
}
.kb-checklist-header .kb-link:hover { text-decoration: underline; }
.kb-check-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.kb-check-item:hover { border-color: var(--el-color-primary-light-5); background: #f0f9ff; }
.kb-check-item input { width: 16px; height: 16px; cursor: pointer; flex-shrink: 0; }
.kb-check-name { font-weight: 500; color: #303133; flex-shrink: 0; }
.kb-check-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #909399; min-width: 0; }
.kb-check-desc { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 360px; }

.skill-section { margin-bottom: 24px; }
.skill-card-inline {
  background: #f0f9ff;
  border: 1px solid #d0e8fc;
  border-radius: 8px;
  padding: 16px 20px;
}
.skill-card-inline h3 { margin: 0 0 4px 0; font-size: 16px; }
.skill-desc { color: #606266; font-size: 13px; margin: 0 0 12px 0; }
.skill-selector { display: flex; align-items: center; gap: 12px; }
.skill-select { flex: 1; max-width: 500px; }
.skill-manage-link { color: var(--el-color-primary); cursor: pointer; font-size: 13px; white-space: nowrap; }
.skill-manage-link:hover { text-decoration: underline; }
.kb-section { margin-bottom: 24px; }

.image-attachment-section { margin-bottom: 24px; }
.image-attachment-card {
  background: white;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.08);
  border: 1px solid #e1e8ed;
}
.image-attachment-card h3 { margin: 0 0 8px 0; font-size: 1.1rem; color: #2c3e50; }
.image-attachment-desc {
  margin: 0 0 16px 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}
.image-upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.image-upload-tip { font-size: 12px; color: #909399; }
.image-attachment-list { display: flex; flex-direction: column; gap: 12px; }
.image-attachment-item {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
}
.attachment-thumb {
  width: 96px;
  height: 64px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
  flex-shrink: 0;
}
.attachment-fields { flex: 1; display: grid; gap: 6px; min-width: 0; }
.attachment-field-label { font-size: 12px; color: #606266; }
.attachment-role, .attachment-caption, .attachment-step { max-width: 320px; }
.attachment-remove-btn {
  flex-shrink: 0;
  border: none;
  background: #fee;
  color: #c0392b;
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.attachment-remove-btn:hover { background: #fdd; }

.continue-refine-section { margin: 0 0 24px 0; }
.continue-refine-card {
  background: linear-gradient(180deg, #f0f7ff 0%, #fff 100%);
  border: 2px solid #2563eb;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.12);
}
.continue-refine-card h3 {
  margin: 0 0 8px 0;
  color: #1e40af;
  font-size: 1.15rem;
}
.refine-desc {
  margin: 0 0 16px 0;
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
}
.refine-textarea { min-height: 96px; }
.submit-continue-refine-btn {
  margin-top: 16px;
  padding: 12px 24px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}
.submit-continue-refine-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.submit-continue-refine-btn:not(:disabled):hover { background: #1d4ed8; }

.kb-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.08);
  border: 1px solid #e1e8ed;
}
.kb-card h3 { margin: 0 0 8px 0; font-size: 1.1rem; color: #2c3e50; }
.kb-desc { margin: 0 0 16px 0; color: #666; font-size: 0.92rem; }
.kb-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 500;
  color: #2c3e50;
}
.kb-form .form-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #888;
  line-height: 1.5;
}
.kb-info-box {
  margin-top: 8px;
  padding: 12px 16px;
  background: #f0f7ff;
  border-radius: 8px;
  border: 1px solid #d0e3ff;
}
.kb-empty-tip {
  color: #e6a23c;
  font-size: 0.9rem;
  line-height: 1.6;
}
.kb-empty-tip a { color: #409eff; }
.kb-found-header {
  font-weight: 600;
  color: #67c23a;
  margin-bottom: 8px;
  font-size: 0.92rem;
}
.kb-found-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px dashed #e1e8ed;
  font-size: 0.88rem;
}
.kb-found-item:last-child { border-bottom: none; }
.kb-found-name { font-weight: 500; color: #2c3e50; }
.kb-found-meta { color: #999; font-size: 0.82rem; }
.kb-found-desc { color: #888; font-size: 0.82rem; flex: 1; }
.kb-doc-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid #e1e8ed;
  border-radius: 8px;
  padding: 8px;
  background: #fafbfc;
}
.kb-doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}
.kb-doc-item:hover,
.kb-doc-item.selected {
  background: #eef6ff;
}
.kb-doc-name {
  flex: 1;
  font-size: 0.92rem;
  color: #2c3e50;
}
.kb-doc-meta {
  font-size: 12px;
  color: #999;
}
.kg-expand-preview {
  margin: 8px 0 0;
  padding: 8px 12px;
  font-size: 13px;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  line-height: 1.5;
}

.kb-preview-actions {
  margin-top: 12px;
}
.preview-kb-btn {
  background: #3498db;
  color: white;
  border: none;
  padding: 10px 18px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.92rem;
}
.preview-kb-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.kb-preview-modal {
  background: white;
  border-radius: 12px;
  width: min(900px, 92vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
}
.kb-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e1e8ed;
}
.kb-preview-header h3 { margin: 0; font-size: 1.1rem; }
.kb-preview-header .close-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: #666;
}
.kb-preview-meta {
  padding: 10px 20px;
  font-size: 12px;
  color: #666;
  background: #f8f9fa;
  border-bottom: 1px solid #eee;
}
.kb-preview-warnings {
  padding: 8px 20px;
  background: #fff8e6;
  border-bottom: 1px solid #ffe58f;
  font-size: 12px;
  color: #ad6800;
}
.kb-preview-warnings p { margin: 4px 0; }
.kb-preview-content {
  margin: 0;
  padding: 16px 20px;
  overflow: auto;
  flex: 1;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
}
.output-mode-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.08);
  border: 1px solid #e1e8ed;
}
.output-mode-card h3 { margin: 0 0 12px 0; font-size: 1.1rem; color: #2c3e50; }
.output-mode-selector { display: flex; gap: 16px; flex-wrap: wrap; }
.mode-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 2px solid #e1e8ed;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.mode-option.active { border-color: #27ae60; background: #f0fdf4; }
.mode-option input { margin: 0; }

.manual-input-card, .upload-card {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #e1e8ed;
  margin-bottom: 30px;
}

.manual-input-card h2, .upload-card h2 {
  color: #2c3e50;
  margin-bottom: 20px;
  font-size: 1.5rem;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #2c3e50;
}

.form-input, .form-select, .form-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 1rem;
  transition: border-color 0.3s ease;
}

.form-input:focus, .form-select:focus, .form-textarea:focus {
  outline: none;
  border-color: #3498db;
  box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
}

.form-textarea {
  resize: vertical;
  font-family: inherit;
}

.char-count {
  text-align: right;
  font-size: 0.85rem;
  color: #666;
  margin-top: 5px;
}

.swagger-hint {
  margin-top: 5px;
  font-size: 0.85rem;
  color: #1a7f37;
}

.required {
  color: #e74c3c;
}

.generate-manual-btn, .generate-btn {
  background: #27ae60;
  color: white;
  border: none;
  padding: 15px 30px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1.1rem;
  transition: background 0.3s ease;
  width: 100%;
  margin-top: 10px;
}

.generate-manual-btn:hover:not(:disabled), .generate-btn:hover:not(:disabled) {
  background: #219a52;
}

.generate-manual-btn:disabled, .generate-btn:disabled {
  background: #bdc3c7;
  cursor: not-allowed;
}

.divider {
  text-align: center;
  margin: 40px 0;
  position: relative;
}

.divider::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background: #ddd;
}

.divider span {
  background: white;
  padding: 0 20px;
  color: #666;
  font-size: 1rem;
}

.upload-area {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  transition: border-color 0.3s ease;
  margin-bottom: 20px;
}

.upload-area.drag-over {
  border-color: #3498db;
  background: #f8f9fa;
}

.upload-placeholder {
  color: #666;
}

.upload-icon {
  font-size: 3rem;
  margin-bottom: 15px;
  display: block;
}

.upload-hint {
  color: #999;
  font-size: 0.9rem;
  margin-top: 5px;
}

.select-file-btn {
  background: #3498db;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  margin-top: 15px;
}

.file-selected {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 6px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.file-icon {
  font-size: 2rem;
}

.file-details {
  flex: 1;
}

.file-name {
  font-weight: 600;
  margin: 0;
}

.file-size {
  color: #666;
  font-size: 0.9rem;
  margin: 5px 0 0 0;
}

.remove-file {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
}

.generation-progress {
  margin: 40px 0;
}

.progress-card {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #e1e8ed;
  text-align: center;
}

.progress-card h3 {
  color: #2c3e50;
  margin-bottom: 20px;
  font-size: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}

.current-mode-badge {
  font-size: 0.85rem;
  color: #666;
  background: #f0f0f0;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: normal;
}

.progress-info {
  display: flex;
  justify-content: center;
  gap: 30px;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.graph-expansion-hint {
  margin: 0 0 16px;
  padding: 8px 12px;
  font-size: 13px;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  line-height: 1.5;
}

.progress-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.progress-item .label {
  font-size: 0.9rem;
  color: #666;
}

.progress-item .value {
  font-weight: 600;
  color: #2c3e50;
}

.progress-steps {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  opacity: 0.4;
  transition: opacity 0.3s ease;
}

.step.active {
  opacity: 1;
}

.step-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #ddd;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: white;
}

.step.active .step-number {
  background: #3498db;
}

.step-text {
  font-size: 0.9rem;
  color: #666;
}

.cancel-generation-btn {
  background: #e74c3c;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
}

.completion-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 20px;
  flex-wrap: wrap;
}

.completion-actions .download-btn,
.completion-actions .save-btn,
.completion-actions .new-generation-btn,
.completion-actions .continue-refine-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.95rem;
  transition: background 0.3s ease;
}

.completion-actions .continue-refine-btn {
  background: #2563eb;
  color: white;
}

.completion-actions .continue-refine-btn:hover {
  background: #1d4ed8;
}

.completion-actions .new-generation-btn {
  background: #27ae60;
  color: white;
}

.completion-actions .new-generation-btn:hover {
  background: #219a52;
}

.generation-result {
  margin: 40px 0;
}

.result-header {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #e1e8ed;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
}

.result-header h2 {
  color: #27ae60;
  margin: 0;
}

.result-summary {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.summary-item {
  color: #666;
  font-size: 0.9rem;
}

.new-generation-btn {
  background: #3498db;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
}

.generated-testcases-section, .review-feedback-section, .final-testcases-section {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #e1e8ed;
  margin-bottom: 20px;
}

.generated-testcases-section h3, .review-feedback-section h3, .final-testcases-section h3 {
  color: #2c3e50;
  margin-bottom: 20px;
}

.testcase-content, .review-content {
  background: #f8f9fa;
  border-radius: 6px;
  padding: 20px;
  border-left: 4px solid #3498db;
}

.testcase-content pre, .review-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.9rem;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .result-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .progress-info, .result-summary {
    flex-direction: column;
    gap: 10px;
  }

  .progress-steps {
    gap: 10px;
  }
}

.actions-section {
  display: flex;
  gap: 20px;
  justify-content: center;
  margin-top: 30px;
  flex-wrap: wrap;
}

.download-btn, .save-btn {
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.download-btn {
  background-color: #1abc9c;
  color: white;
}

.download-btn:hover {
  background-color: #16a085;
}

.save-btn {
  background-color: #3498db;
  color: white;
}

.save-btn:hover {
  background-color: #2980b9;
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.failure-tip {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  color: #ad6800;
  font-size: 14px;
  line-height: 1.6;
}
.failure-tip p { margin: 0 0 8px 0; }
.failure-detail {
  font-size: 13px;
  color: #874d00;
  word-break: break-word;
}
.task-detail-link-btn {
  margin-top: 4px;
  padding: 6px 12px;
  border: 1px solid #ffa940;
  background: #fff;
  color: #d46b08;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.task-detail-link-btn:hover { background: #fff1e6; }

@media (max-width: 768px) {
  .actions-section {
  flex-direction: column;
  align-items: center;
  }

  .download-btn, .save-btn {
    width: 100%;
    max-width: 300px;
    justify-content: center;
  }
}

/* 流式内容显示样式（与上游一致） */
.stream-content-display {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  margin-top: 15px;
  border: 1px solid #e1e8ed;
  /* 不固定高度：内容撑开区域，与完整输出一致 */
  max-height: none;
  overflow: visible;
}

.stream-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #dee2e6;
}

.stream-title {
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 8px;
}

.streaming-indicator {
  font-size: 0.85rem;
  color: #27ae60;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.stream-status {
  font-size: 0.85rem;
  color: #666;
  background: #e9ecef;
  padding: 4px 8px;
  border-radius: 4px;
}

.stream-placeholder {
  color: #6c757d;
  font-size: 0.9rem;
  padding: 12px 0;
}

.stream-content {
  color: #2c3e50;
  line-height: 1.6;
  font-size: 0.9rem;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.stream-content code {
  background: #f1f3f5;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.85em;
}

.stream-content strong {
  font-weight: 600;
  color: #1a202c;
}

/* 顶部 关联项目 卡 */
.project-section { margin-bottom: 16px; }
.project-card {
  background: #fff; border: 1px solid #e4e7ed; border-radius: 8px;
  padding: 16px 20px; box-shadow: 0 1px 4px rgba(0,0,0,.04);
}
.project-card h3 { margin: 0 0 6px 0; font-size: 16px; }
.project-desc { margin: 0 0 12px 0; color: #606266; font-size: 13px; line-height: 1.6; }
.project-selector { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.project-selector .form-select { width: 320px; max-width: 100%; }
.project-hint { color: #909399; font-size: 12px; }

.form-static-value {
  display: inline-block; padding: 6px 12px;
  background: #f5f7fa; border: 1px dashed #dcdfe6; border-radius: 4px;
  color: #606266; font-size: 13px;
}

.stream-content.final-testcases {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #dee2e6;
}
</style>