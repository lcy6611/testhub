<template>
  <div class="manual">
    <h1>📘 知识中枢 · 操作手册</h1>
    <p class="subtitle">本手册对照 TestHub 6.0 知识中枢设计，列出 5 大子功能的使用步骤。</p>

    <el-card class="section" shadow="never">
      <template #header>
        <h2>① 让项目上知识库</h2>
      </template>
      <ol class="steps">
        <li>进入「项目管理」→ 编辑项目 → 启用「知识库」模块开关。</li>
        <li>启用后，项目下拉、知识库管理卡片会自动展示该项目下的 KB 列表。</li>
        <li>如尚未创建本地 KB，系统会提示「新建 KB」入口；或绑定 Dify 数据集。</li>
        <li>可见性：KB 可设为「全局共享 / 仅当前项目 / 显式绑定到指定项目」三种粒度。</li>
        <li>对于接口测试场景，可在 AI 用例生成时勾选「启用知识库（业务大脑）」自动检索。</li>
      </ol>
    </el-card>

    <el-card class="section" shadow="never">
      <template #header>
        <h2>② 添加知识源并同步</h2>
      </template>
      <ol class="steps">
        <li>已有 Confluence / 飞书 / OpenAPI 等客户/项目时，可在「知识库管理 → 外部数据源」页签一键接入。</li>
        <li>场景①：AI 团队沉淀的文档（产品需求/市场调研）一键入库（零手动、最快实现）。</li>
        <li>场景②：Confluence/飞书等标准 API + Token 私有可配；同步过程会拉取文档元信息。</li>
        <li>场景③：增量同步机制；同步完成会展示文档数 + 失败数。</li>
        <li>同步失败的文档会标记为「解析失败」，可在文档管理页单独重试。</li>
      </ol>
    </el-card>

    <el-card class="section" shadow="never">
      <template #header>
        <h2>③ 上传专 URL / 文件入库</h2>
      </template>
      <ol class="steps">
        <li>支持 PDF / Word / Markdown / TXT / 图片（v2 已实装 OCR 路径）。</li>
        <li>解析流水线：上传 → 文档解析（Tika / MinerU / TextIn）→ Chunking → Embedding → 写入向量库。</li>
        <li>URL 入库：把一个网页地址直接抓回，自动适配接口文档页面（HTML/Markdown 抽取）。</li>
        <li>SSRF 防护：禁止 127.0.0.1 / 169.254.x 等内网地址，避免误抓内部资源。</li>
        <li>临时权限：URL 抓取需授予 <code>authorize_level=intranet</code> 才允许内网穿透。</li>
      </ol>
    </el-card>

    <el-card class="section" shadow="never">
      <template #header>
        <h2>④ 抽取 / 生成知识（一键提取）</h2>
      </template>
      <ol class="steps">
        <li>入口：文档详情 → 「抽取」按钮 → 选择 LLM 模型（推荐通用抽取模型）。</li>
        <li>对文档逐 chunk 调用模型抽取「业务实体 + 关系」，并写入知识图谱。</li>
        <li>抽取完成后自动发布为「Feature 编译知识卡片」并与项目功能模块对接。</li>
        <li>效果取决于文档质量与项目的领域相关性；与项目需求强相关的文档抽取价值最大。</li>
      </ol>
    </el-card>

    <el-card class="section" shadow="never">
      <template #header>
        <h2>⑤ 文档与实体接门</h2>
      </template>
      <ol class="steps">
        <li>文档生命周期：<strong>draft → published → archived</strong>。published 后才可被检索。</li>
        <li>待提取的文档会自动归档到归档库；不达 corpus / citations / team_standards 的会进入「语料限制」。</li>
        <li>自动随和的实体/关系可被团队成员访问；arch 文档只有创建者可读，1 Context Bundle 可拉取。</li>
        <li>抽取/同步的执行情况可在「知识库管理 → 同步记录」追踪（待补充 UI）。</li>
      </ol>
    </el-card>

    <el-card class="section" shadow="never">
      <template #header>
        <h2>⚙️ 中枢 5 项配置</h2>
      </template>
      <p>前往「<el-link type="primary" @click="$router.push('/configuration/knowledge-hub/config')">知识中枢 → 中枢配置</el-link>」维护以下 5 项：</p>
      <ol class="steps">
        <li><strong>文档解析</strong>：MinerU（私有）/ TextIn（云端）/ Tika（内置兜底）。未配置时系统自动用 Tika。</li>
        <li><strong>Embedding 向量模型</strong>：推荐 Qwen3-Embedding-8B。切换模型需重建索引。</li>
        <li><strong>Rerank 重排模型</strong>：推荐 bge-reranker-v2-m3 或 Qwen3-Reranker-8B。</li>
        <li><strong>生成/抽取模型</strong>：通用 LLM 即可，用于问答生成与文档抽取。</li>
        <li><strong>视觉理解模型</strong>（可选）：用于截图/图表/界面理解。</li>
      </ol>
    </el-card>
  </div>
</template>

<script setup>
// 占位
</script>

<style scoped>
.manual {
  padding: 24px;
  max-width: 980px;
  margin: 0 auto;
}
h1 { margin: 0 0 8px; font-size: 28px; }
.subtitle { color: #909399; margin-bottom: 24px; }
.section { margin-bottom: 16px; }
.section h2 { margin: 0; font-size: 18px; color: #303133; }
.steps { padding-left: 24px; line-height: 1.9; color: #606266; margin: 12px 0; }
.steps li { margin-bottom: 4px; }
code { background: #f5f7fa; padding: 2px 6px; border-radius: 4px; font-size: 12px; color: #d63384; }
</style>