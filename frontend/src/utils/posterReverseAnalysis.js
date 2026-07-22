export const MAX_POSTER_IMAGE_BYTES = 10 * 1024 * 1024
export const MAX_POSTER_DATA_URL_LENGTH = 14 * 1024 * 1024
export const MAX_POSTER_EDGE = 4096

const ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
const ALLOWED_ERROR_CODES = new Set([
  'MODEL_NOT_CONFIGURED',
  'INVALID_IMAGE',
  'ANALYSIS_RATE_LIMITED',
  'UPSTREAM_AUTH_FAILED',
  'UPSTREAM_RATE_LIMITED',
  'CONTENT_REJECTED',
  'ANALYSIS_TIMEOUT',
  'UPSTREAM_INVALID_RESPONSE',
  'UPSTREAM_ERROR',
])

export function calculatePosterResize(width, height, maxEdge = MAX_POSTER_EDGE) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    throw new Error('图片尺寸无效')
  }
  const longest = Math.max(width, height)
  if (longest <= maxEdge) return { width: Math.round(width), height: Math.round(height) }
  const scale = maxEdge / longest
  return { width: Math.round(width * scale), height: Math.round(height * scale) }
}

export function validateReversePrompt(content) {
  const normalized = typeof content === 'string' ? content.trim() : ''
  if (!normalized) throw new Error('生成提示词不能为空')
  if (normalized.length > 4000) throw new Error('生成提示词不能超过 4000 个字符')
  return normalized
}

export function buildReversePromptPayload(result, editedPrompt = result?.generation_prompt) {
  const content = validateReversePrompt(editedPrompt)
  const posterType = typeof result?.poster_type === 'string' && result.poster_type.trim()
    ? result.poster_type.trim()
    : '海报'
  const tags = [...new Set(
    (Array.isArray(result?.visual_style) ? result.visual_style : [])
      .filter(item => typeof item === 'string')
      .map(item => item.trim())
      .filter(Boolean),
  )].slice(0, 5)
  return {
    title: `${posterType}逆向提示词`,
    content,
    category: 'poster',
    tags,
    source_mode: 'reverse_analysis',
  }
}

export function normalizeReverseAnalysisError(error) {
  const detail = error?.response?.data?.detail
  const code = typeof detail?.code === 'string' && ALLOWED_ERROR_CODES.has(detail.code)
    ? detail.code
    : 'UNKNOWN'
  const message = code !== 'UNKNOWN' && typeof detail?.message === 'string' && detail.message.trim()
    ? detail.message.trim().slice(0, 200)
    : '分析失败，请稍后重试'
  const rawRetryAfter = error?.response?.headers?.['retry-after']
  const parsed = Number.parseInt(rawRetryAfter, 10)
  const retryAfter = Number.isInteger(parsed) && parsed >= 1 && parsed <= 3600 ? parsed : null
  return { code, message, retryAfter }
}

export function createReverseAnalysisRequestState() {
  let sequence = 0
  let open = true
  return {
    begin() {
      open = true
      sequence += 1
      return sequence
    },
    accept(requestId) {
      return open && requestId === sequence
    },
    close() {
      open = false
      sequence += 1
    },
  }
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })
}

export async function preparePosterImage(file, options = {}) {
  if (!file || !ALLOWED_IMAGE_TYPES.has(file.type)) {
    throw new Error('仅支持 JPG、PNG 或 WEBP 图片')
  }
  if (file.size > MAX_POSTER_IMAGE_BYTES) throw new Error('图片不能超过 10MB')

  const createBitmap = options.createImageBitmap || globalThis.createImageBitmap
  const bitmap = await createBitmap(file)
  const dimensions = calculatePosterResize(bitmap.width, bitmap.height)
  if (dimensions.width === bitmap.width && dimensions.height === bitmap.height) {
    bitmap.close?.()
    const original = await readFileAsDataURL(file)
    if (original.length > MAX_POSTER_DATA_URL_LENGTH) throw new Error('图片编码后体积过大')
    return original
  }

  const canvas = document.createElement('canvas')
  canvas.width = dimensions.width
  canvas.height = dimensions.height
  const context = canvas.getContext('2d', { alpha: false })
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close?.()
  const dataUrl = canvas.toDataURL('image/webp', options.quality ?? 0.92)
  if (dataUrl.length > MAX_POSTER_DATA_URL_LENGTH) throw new Error('图片编码后体积过大')
  return dataUrl
}
