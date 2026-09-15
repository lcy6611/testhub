import request from '@/utils/api'

// 文档中心：目录树 + 单篇正文（后端扫描 docs/docs-center 下的 Markdown）
export function getDocTree() {
  return request.get('/docs/tree/')
}

export function getDocContent(path) {
  return request.get('/docs/content/', { params: { path } })
}
