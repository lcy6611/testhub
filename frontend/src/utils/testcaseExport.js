/**
 * 测试用例 Markdown → Excel 导出（与页面展示同源解析）
 */

/** 去掉总结段，保留用例表格 */
export function filterTestCasesOnly(content) {
  if (!content) return ''
  const lines = []
  for (const line of String(content).split('\n')) {
    const trimmed = line.trim()
    if (
      /^#{1,3}\s*(最后总结|总结与建议|总结|建议)/.test(trimmed) ||
      /^(\*\*)?(最后总结|总结与建议)/.test(trimmed) ||
      /^[-*]\s*(总结|建议)/.test(trimmed)
    ) {
      break
    }
    lines.push(line)
  }
  return lines.join('\n')
}

/** 单元格：Markdown/HTML → Excel 纯文本 */
export function normalizeExportCell(value) {
  if (value == null) return ''
  let text = String(value).trim()
  text = text.replace(/<br\s*\/?>/gi, '\n')
  text = text.replace(/\*\*(.+?)\*\*/g, '$1')
  text = text.replace(/\*(.+?)\*/g, '$1')
  text = text.replace(/`(.+?)`/g, '$1')
  text = text.replace(/\\([|])/g, '$1')
  return text.trim()
}

function splitMarkdownTableRow(line) {
  const trimmed = line.trim()
  if (!trimmed.includes('|')) return null
  let cells = trimmed.split('|').map(c => normalizeExportCell(c))
  if (cells.length && cells[0] === '') cells.shift()
  if (cells.length && cells[cells.length - 1] === '') cells.pop()
  return cells.length > 1 ? cells : null
}

function isSeparatorRow(cells) {
  return cells.every(c => /^:?-{2,}:?$/.test(c.replace(/\s/g, '')))
}

/** 取正文中行数最多的 Markdown 表格（避免导出旧表/示例表） */
export function extractMainMarkdownTable(content) {
  const filtered = filterTestCasesOnly(content)
  const lines = filtered.split('\n')
  let bestBlock = []
  let bestDataCount = -1
  let current = []

  const flush = () => {
    if (current.length < 2) {
      current = []
      return
    }
    const rows = current.map(splitMarkdownTableRow).filter(Boolean)
    let dataCount = 0
    for (let i = 0; i < rows.length; i++) {
      if (i === 0) continue
      if (isSeparatorRow(rows[i])) continue
      dataCount++
    }
    if (dataCount > bestDataCount) {
      bestDataCount = dataCount
      bestBlock = [...current]
    }
    current = []
  }

  for (const line of lines) {
    if (splitMarkdownTableRow(line)) {
      current.push(line)
    } else {
      flush()
    }
  }
  flush()
  return bestBlock.join('\n')
}

/**
 * 解析 Markdown 表格为二维数组（含表头行）
 * @returns {string[][]}
 */
export function parseMarkdownTableForExport(content) {
  const tableText = extractMainMarkdownTable(content)
  if (!tableText) return []

  const rows = []
  for (const line of tableText.split('\n')) {
    const cells = splitMarkdownTableRow(line)
    if (!cells) continue
    if (isSeparatorRow(cells)) continue
    rows.push(cells)
  }
  return rows.length >= 2 ? rows : []
}

/**
 * @param {string} content 与页面展示相同的 Markdown 正文
 * @returns {string[][]} worksheet 数据（含表头）
 */
export function buildWorksheetFromMarkdown(content) {
  const table = parseMarkdownTableForExport(content)
  if (table.length >= 2) {
    return table
  }
  return [['测试用例内容'], [normalizeExportCell(filterTestCasesOnly(content) || content)]]
}
