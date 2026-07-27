import * as curlconverter from 'curlconverter'

/**
 * @typedef {{ key: string, value: string, enabled: boolean }} QueryParam
 * @typedef {{ key: string, value: string, enabled: boolean }} Header
 * @typedef {{ mode: string, raw?: string, json?: string, formdata?: any[], urlencoded?: any[] }} Body
 * @typedef {{ method: string, baseURL: string, path: string, query: QueryParam[], headers: Header[], body: Body, timeout?: number }} RequestModel
 */

export class RequestModelParser {
  /**
   * @param {string} curlCommand
   * @returns {Promise<RequestModel>}
   */
  static async parseCurl(curlCommand) {
    try {
      const harData = curlconverter.toHarString(curlCommand)
      const har = JSON.parse(harData)

      if (!har.log || !har.log.entries || har.log.entries.length === 0) {
        throw new Error('无法解析CURL命令，请检查格式')
      }

      const entry = har.log.entries[0]
      const request = entry.request
      const url = new URL(request.url)
      const baseURL = `${url.protocol}//${url.host}`
      const path = url.pathname

      const query = []
      if (request.queryString && request.queryString.length > 0) {
        request.queryString.forEach((param) => {
          query.push({ key: param.name, value: param.value || '', enabled: true })
        })
      } else {
        url.searchParams.forEach((value, key) => {
          query.push({ key, value, enabled: true })
        })
      }

      const headers = []
      if (request.cookies && request.cookies.length > 0) {
        const cookieValue = request.cookies
          .map((c) => `${c.name}=${c.value}`)
          .join('; ')
        headers.push({ key: 'Cookie', value: cookieValue, enabled: true })
      }
      request.headers.forEach((header) => {
        headers.push({ key: header.name, value: header.value, enabled: true })
      })

      const body = { mode: 'none' }
      if (request.postData) {
        const postData = request.postData
        const contentType = headers.find((h) => h.key.toLowerCase() === 'content-type')?.value

        if (contentType && contentType.includes('application/json')) {
          body.mode = 'json'
          body.json = postData.text || ''
        } else if (contentType && contentType.includes('application/x-www-form-urlencoded')) {
          body.mode = 'urlencoded'
          body.urlencoded = []
          if (postData.params) {
            postData.params.forEach((param) => {
              body.urlencoded.push({
                key: param.name,
                value: param.value || '',
                type: 'text',
                enabled: true
              })
            })
          }
        } else if (contentType && contentType.includes('multipart/form-data')) {
          body.mode = 'formdata'
          body.formdata = []
          if (postData.params) {
            postData.params.forEach((param) => {
              body.formdata.push({
                key: param.name,
                value: param.value || param.fileName || '',
                type: param.fileName ? 'file' : 'text',
                enabled: true
              })
            })
          }
        } else {
          body.mode = 'raw'
          body.raw = postData.text || ''
        }
      }

      return {
        method: request.method || 'GET',
        baseURL,
        path,
        query,
        headers,
        body,
        timeout: 30000
      }
    } catch (error) {
      console.error('Failed to parse cURL command:', error)
      const msg = error?.message || error?.toString() || 'Unknown error'
      throw new Error(`cURL命令解析失败: ${msg}，请检查命令格式`)
    }
  }

  /**
   * @param {RequestModel} model
   * @returns {string}
   */
  static toCurl(model) {
    let url
    if (model.baseURL && model.path) {
      url = new URL(model.baseURL + model.path)
    } else if (model.baseURL) {
      url = new URL(model.baseURL)
    } else if (model.path) {
      url = new URL(model.path)
    } else {
      throw new Error('Invalid URL: both baseURL and path are empty')
    }

    model.query.forEach((param) => {
      if (param.enabled && param.key) {
        url.searchParams.append(param.key, param.value)
      }
    })
    let curl = `curl -X ${model.method} '${url.toString()}'`

    model.headers.forEach((header) => {
      if (header.enabled && header.key) {
        const val = (header.value || '').replace(/'/g, "'\\''")
        curl += ` -H '${header.key}: ${val}'`
      }
    })

    if (model.body.mode !== 'none') {
      const raw = model.body.raw || model.body.json || ''
      if (raw) {
        curl += ` -d '${String(raw).replace(/'/g, "'\\''")}'`
      }
    }

    if (model.timeout) {
      curl += ` --max-time ${model.timeout / 1000}`
    }
    return curl
  }
}
