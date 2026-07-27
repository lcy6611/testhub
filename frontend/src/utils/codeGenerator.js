import * as curlconverter from 'curlconverter'

/**
 * 根据当前请求构建 curl 命令字符串，供 curlconverter 转成各语言
 * @param {object} model - { method, baseURL, path, query, headers, body }
 * @returns {string}
 */
function buildCurlCommand(model) {
  const url = buildUrl(model)
  const method = (model.method || 'GET').toUpperCase()
  const headers = buildCurlHeaders(model)
  const body = buildCurlBody(model)

  let curl = `curl -X ${method}`
  if (headers) curl += ` ${headers}`
  if (body) curl += ` ${body}`
  curl += ` '${url.replace(/'/g, "'\\''")}'`
  return curl
}

function buildUrl(model) {
  try {
    const base = model.baseURL || ''
    const path = model.path || ''
    const full = base + (path.startsWith('/') ? path : `/${path}`)
    const url = new URL(full)
    const list = Array.isArray(model.query) ? model.query : []
    list.forEach((param) => {
      if (param.enabled !== false && param.key) {
        url.searchParams.append(param.key, param.value || '')
      }
    })
    return url.toString()
  } catch (e) {
    return (model.baseURL || '') + (model.path || '')
  }
}

function buildCurlHeaders(model) {
  const list = Array.isArray(model.headers) ? model.headers : []
  return list
    .filter((h) => h.enabled !== false && h.key)
    .map((h) => {
      const value = (h.value || '').replace(/"/g, '\\"')
      return `-H "${h.key}: ${value}"`
    })
    .join(' ')
}

function buildCurlBody(model) {
  const body = model.body || {}
  if (body.mode === 'none' || !body.mode) return ''

  const raw = body.raw || body.json || ''
  if (raw) {
    if (body.mode === 'json' || body.mode === 'raw') {
      return `-d '${String(raw).replace(/'/g, "'\\''")}'`
    }
  }
  if (body.mode === 'formdata' && body.formdata && body.formdata.length) {
    return body.formdata
      .filter((f) => f.enabled !== false && f.key)
      .map((f) => `-F "${f.key}=${(f.value || '').replace(/"/g, '\\"')}"`)
      .join(' ')
  }
  if (body.mode === 'urlencoded' && body.urlencoded && body.urlencoded.length) {
    const parts = body.urlencoded
      .filter((f) => f.enabled !== false && f.key)
      .map((f) => `${encodeURIComponent(f.key)}=${encodeURIComponent(f.value || '')}`)
    return `-d '${parts.join('&')}'`
  }
  return ''
}

const languageMap = {
  javascript: 'javascript',
  python: 'python',
  java: 'java',
  node: 'node',
  curl: 'http',
  php: 'php',
  go: 'go',
  csharp: 'csharp',
  ruby: 'ruby',
  swift: 'swift',
  kotlin: 'kotlin',
  rust: 'rust'
}

export class CodeGenerator {
  /**
   * @param {object} model - RequestModel
   * @param {string} language - javascript | python | java | curl | ...
   * @returns {Promise<string>}
   */
  static async generateCode(model, language) {
    const curlCommand = buildCurlCommand(model)

    if (language === 'curl') {
      return curlCommand
    }

    const mapped = languageMap[language] || language
    try {
      switch (mapped) {
        case 'javascript':
          return curlconverter.toJavaScript(curlCommand)
        case 'python':
          return curlconverter.toPython(curlCommand)
        case 'java':
          return curlconverter.toJava(curlCommand)
        case 'node':
          return curlconverter.toNode(curlCommand)
        case 'http':
          return curlconverter.toHTTP(curlCommand)
        case 'php':
          return curlconverter.toPhp(curlCommand)
        case 'go':
          return curlconverter.toGo(curlCommand)
        case 'csharp':
          return curlconverter.toCSharp(curlCommand)
        case 'ruby':
          return curlconverter.toRuby(curlCommand)
        case 'swift':
          return curlconverter.toSwift(curlCommand)
        case 'kotlin':
          return curlconverter.toKotlin(curlCommand)
        case 'rust':
          return curlconverter.toRust(curlCommand)
        default:
          return curlconverter.toPython(curlCommand)
      }
    } catch (err) {
      console.error('Error generating code:', err)
      return `// 生成失败: ${err?.message || err}`
    }
  }
}
