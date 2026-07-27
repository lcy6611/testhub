/**
 * cURL / fetch / 原始 HTTP 解析器
 * 把 F12 Network 面板 "Copy as cURL/fetch" 复制的内容解析成 { method, url, headers, body }
 *
 * 支持格式：
 *   1. cURL (bash):     curl 'https://...' -H 'Accept: ...' -X POST -d '...'
 *   2. cURL (PowerShell): curl "..." -H "..." -Body "..."
 *   3. fetch (JS):      fetch("https://...", {headers: {...}, method: "POST", body: "..."})
 *   4. 原始 HTTP:       POST /path HTTP/1.1\r\nHost: ...\r\nContent-Type: ...\r\n\r\nbody
 *   5. 原始 headers:    一行/多行 "Key: Value" 列表
 */

function _stripQuotes(s) {
  if (!s) return s
  s = s.trim()
  if ((s.startsWith("'") && s.endsWith("'")) || (s.startsWith('"') && s.endsWith('"'))) {
    return s.slice(1, -1)
  }
  return s
}

function _unescape(s) {
  // 处理常见转义
  return s.replace(/\\"/g, '"').replace(/\\'/g, "'").replace(/\\n/g, '\n').replace(/\\r/g, '\r').replace(/\\\\/g, '\\')
}

/**
 * 解析 cURL 命令
 * @param {string} input cURL 字符串
 * @returns {object} { method, url, headers, body }
 */
function _parseCurl(input) {
  // 规范化：去除行续符 ^\n (PowerShell) 和 \
  const normalized = input
    .replace(/\r\n/g, ' ')
    .replace(/\n/g, ' ')
    .replace(/\s*\^\s*/g, ' ')   // PowerShell line continuation
    .replace(/\s*\\\s*/g, ' ')    // bash line continuation
    .trim()

  // 1) 提取 URL：找第一个以 http:// / https:// / / 开头的 token
  let url = ''
  const cmd = normalized.replace(/^curl\s+/i, '')
  const tokens = _tokenize(cmd)

  // 先看是否有 -X/--request 后的 method
  let method = ''
  for (let i = 0; i < tokens.length; i++) {
    if ((tokens[i] === '-X' || tokens[i] === '--request') && tokens[i + 1]) {
      method = tokens[i + 1].replace(/^['"]|['"]$/g, '').toUpperCase()
      break
    }
  }

  // 扫描所有 token，找 URL（http(s):// 或 / 开头）
  for (const t of tokens) {
    const v = t.replace(/^['"]|['"]$/g, '')
    if (/^https?:\/\//i.test(v) || v.startsWith('/')) {
      url = v
      break
    }
  }

  // 2) 解析 flags
  let body = ''
  const headers = []

  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i]
    const next = tokens[i + 1]

    if (t === '-X' || t === '--request') {
      if (next) method = next.replace(/^['"]|['"]$/g, '').toUpperCase()
      i++
    } else if (t === '-H' || t === '--header') {
      if (next) {
        const hv = next.replace(/^['"]|['"]$/g, '').replace(/\\"/g, '"').replace(/\\'/g, "'")
        const idx = hv.indexOf(':')
        if (idx > 0) {
          headers.push({ name: hv.slice(0, idx).trim(), value: hv.slice(idx + 1).trim() })
        }
      }
      i++
    } else if (t === '-d' || t === '--data' || t === '--data-raw' || t === '--data-binary' || t === '--data-ascii' || t === '-body' || t === '--body') {
      if (next !== undefined) {
        body = next.replace(/^['"]|['"]$/g, '').replace(/\\"/g, '"').replace(/\\'/g, "'").replace(/\\n/g, '\n').replace(/\\r/g, '\r')
        if (!method) method = 'POST'
        i++
      }
    } else if (t === '-u' || t === '--user') {
      if (next) {
        const v = next.replace(/^['"]|['"]$/g, '')
        const enc = (typeof btoa !== 'undefined') ? btoa(v) : Buffer.from(v).toString('base64')
        headers.push({ name: 'Authorization', value: `Basic ${enc}` })
        i++
      }
    }
  }

  if (!method) method = 'GET'
  return { method, url, headers, body }
}

/**
 * 简单 tokenize：按空格切分，但保留单/双引号内的内容为一个 token
 */
function _tokenize(s) {
  const out = []
  let cur = ''
  let inQuote = null
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (inQuote) {
      if (c === inQuote) {
        inQuote = null
        // 不立即 push，等下一个空格
      } else {
        cur += c
      }
    } else if (c === "'" || c === '"') {
      inQuote = c
    } else if (c === ' ' || c === '\t') {
      if (cur.length) {
        out.push(cur)
        cur = ''
      }
    } else {
      cur += c
    }
  }
  if (cur.length) out.push(cur)
  return out
}

/**
 * 解析 fetch 调用
 *   fetch("url", { method: "POST", headers: { ... }, body: ... })
 *   fetch("url", { method: "POST" }).then(...)
 */
function _parseFetch(input) {
  const urlMatch = input.match(/fetch\s*\(\s*['"`]([^'"`]+)['"`]/)
  let url = urlMatch ? urlMatch[1] : ''

  // 找 options 块：从第一个 '{' 开始配对（注意跳过 fetch URL 中的 ${...}）
  const startIdx = input.indexOf('{', input.indexOf('fetch'))
  if (startIdx === -1) return { method: 'GET', url, headers: [], body: '' }

  let depth = 0
  let endIdx = -1
  let inStr = null
  for (let i = startIdx; i < input.length; i++) {
    const c = input[i]
    if (inStr) {
      if (c === '\\') { i++; continue }
      if (c === inStr) inStr = null
    } else if (c === '"' || c === "'" || c === '`') {
      inStr = c
    } else if (c === '{') {
      depth++
    } else if (c === '}') {
      depth--
      if (depth === 0) { endIdx = i; break }
    }
  }
  if (endIdx === -1) return { method: 'GET', url, headers: [], body: '' }
  const opts = input.slice(startIdx, endIdx + 1)

  let method = 'GET'
  const m = opts.match(/method\s*:\s*['"`]([A-Z]+)['"`]/i)
  if (m) method = m[1].toUpperCase()

  const headers = []
  // 解析 headers 块（嵌套对象）
  const hStart = opts.indexOf('headers')
  if (hStart !== -1) {
    const braceStart = opts.indexOf('{', hStart)
    if (braceStart !== -1) {
      let hd = 0, hdEnd = -1, hStr = null
      for (let i = braceStart; i < opts.length; i++) {
        const c = opts[i]
        if (hStr) {
          if (c === '\\') { i++; continue }
          if (c === hStr) hStr = null
        } else if (c === '"' || c === "'" || c === '`') {
          hStr = c
        } else if (c === '{') hd++
        else if (c === '}') {
          hd--
          if (hd === 0) { hdEnd = i; break }
        }
      }
      if (hdEnd !== -1) {
        const hBlock = opts.slice(braceStart + 1, hdEnd)
        // 匹配 "k": "v" 或 "k": v
        const re = /['"`]([^'"`]+)['"`]\s*:\s*(?:\{\s*[\s\S]*?\}\s*|(?:new\s+\w+\s*\([^)]*\)\s*)|['"`]([^'"`]*)['"`])/g
        let mm
        while ((mm = re.exec(hBlock)) !== null) {
          const name = mm[1]
          // 如果是嵌套对象（如 Headers 实例），value 留空字符串
          let value = mm[2] !== undefined ? mm[2] : ''
          // 简化处理：常见是字符串 value
          if (mm[2] === undefined) {
            // 嵌套对象（new Headers 或 {...}），value 取原始
            const nested = hBlock.slice(mm.index + mm[0].length)
            value = '(nested object)'
          }
          headers.push({ name, value })
        }
      }
    }
  }

  // 解析 body
  let body = ''
  const bodyMatch = opts.match(/body\s*:\s*([\s\S]+?)(?=\n\s*[a-zA-Z_]+\s*:|\}\s*$)/)
  if (bodyMatch) {
    body = bodyMatch[1].trim()
    // 去引号
    if ((body.startsWith('"') && body.endsWith('"')) || (body.startsWith("'") && body.endsWith("'")) || (body.startsWith('`') && body.endsWith('`'))) {
      body = body.slice(1, -1)
    }
    // 去 JSON.stringify() 包裹
    const sm = body.match(/^JSON\.stringify\s*\(\s*(.*?)\s*\)$/s)
    if (sm) body = sm[1]
  }

  return { method, url, headers, body }
}

/**
 * 解析原始 HTTP 请求行
 * POST /path HTTP/1.1
 * Host: ...
 * Content-Type: ...
 *
 * body
 */
function _parseRawHttp(input) {
  const text = input.replace(/\r\n/g, '\n').trim()
  const lines = text.split('\n')
  const requestLine = lines[0] || ''
  const m = requestLine.match(/^([A-Z]+)\s+(\S+)(?:\s+HTTP\/[\d.]+)?/i)
  let method = 'GET'
  let url = ''
  if (m) {
    method = m[1].toUpperCase()
    url = m[2]
  }
  const headers = []
  let i = 1
  let bodyStart = -1
  for (; i < lines.length; i++) {
    const line = lines[i]
    if (line.trim() === '') {
      bodyStart = i + 1
      break
    }
    const idx = line.indexOf(':')
    if (idx > 0) {
      headers.push({ name: line.slice(0, idx).trim(), value: line.slice(idx + 1).trim() })
    }
  }
  const body = bodyStart >= 0 ? lines.slice(bodyStart).join('\n') : ''

  // 相对 URL 自动拼 Host 头
  if (url && url.startsWith('/')) {
    const hostHeader = headers.find(h => h.name.toLowerCase() === 'host')
    if (hostHeader) {
      url = `http://${hostHeader.value}${url}`
    }
  }
  return { method, url, headers, body }
}

/**
 * 解析"原始 headers 列表"（用户截图场景：F12 复制 Header 列表，粘过来是单行）
 * 启发式：以"大写开头的 Key:"作边界切分每个 header
 */
function _parseRawHeaders(input) {
  // 找所有 "Key:" 的位置（Key 是标准 HTTP header 格式：大写字母开头 + 中划线/字母数字 + 冒号）
  const text = input.trim().replace(/\r\n/g, '\n')
  const headerPositions = []
  const re = /\b([A-Z][A-Za-z0-9-]{1,40})\s*:/g
  let mm
  while ((mm = re.exec(text)) !== null) {
    headerPositions.push({ name: mm[1], start: mm.index, colonEnd: mm.index + mm[0].length })
  }

  if (headerPositions.length === 0) {
    return { method: 'GET', url: '', headers: [], body: '' }
  }

  // 如果有换行，按行模式处理（更准确）
  if (text.includes('\n')) {
    return _parseKeyValueLines(text.split('\n'))
  }

  // 单行：基于 header 位置切分
  const headers = []
  for (let i = 0; i < headerPositions.length; i++) {
    const start = headerPositions[i].colonEnd
    const end = i + 1 < headerPositions.length ? headerPositions[i + 1].start : text.length
    const value = text.slice(start, end).trim()
    if (value) {
      headers.push({ name: headerPositions[i].name, value })
    }
  }
  return { method: 'GET', url: '', headers, body: '' }
}

function _parseKeyValueLines(lines) {
  const headers = []
  for (const line of lines) {
    const idx = line.indexOf(':')
    if (idx > 0) {
      const name = line.slice(0, idx).trim()
      const value = line.slice(idx + 1).trim()
      if (name && !name.startsWith('//') && !name.startsWith('#')) {
        headers.push({ name, value })
      }
    }
  }
  return { method: 'GET', url: '', headers, body: '' }
}

/**
 * 主入口：自动检测格式并解析
 * @param {string} input
 * @returns {object} { method, url, headers, body }
 */
export function parseCurl(input) {
  if (!input || typeof input !== 'string') {
    return { method: 'GET', url: '', headers: [], body: '' }
  }
  const text = input.trim()

  // 格式探测
  if (/^curl\s+/i.test(text)) {
    return _parseCurl(text)
  }
  if (/^fetch\s*\(/i.test(text)) {
    return _parseFetch(text)
  }
  if (/^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\S+/i.test(text) && /HTTP\/[\d.]+/.test(text)) {
    return _parseRawHttp(text)
  }
  // 默认按原始 headers 解析
  return _parseRawHeaders(text)
}
