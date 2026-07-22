import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import {
  MAX_POSTER_DATA_URL_LENGTH,
  buildReversePromptPayload,
  calculatePosterResize,
  createReverseAnalysisRequestState,
  normalizeReverseAnalysisError,
  validateReversePrompt,
} from '../src/utils/posterReverseAnalysis.js'

test('poster resize keeps small images and limits the longest edge to 4096', () => {
  assert.deepEqual(calculatePosterResize(1536, 2048), { width: 1536, height: 2048 })
  assert.deepEqual(calculatePosterResize(8000, 4000), { width: 4096, height: 2048 })
  assert.throws(() => calculatePosterResize(0, 100), /图片尺寸无效/)
})

test('reverse prompt validation trims content and enforces 4000 characters', () => {
  assert.equal(validateReversePrompt('  海报提示词  '), '海报提示词')
  assert.throws(() => validateReversePrompt('   '), /不能为空/)
  assert.throws(() => validateReversePrompt('x'.repeat(4001)), /4000/)
})

test('saved reverse prompt payload has stable category, source and deduplicated tags', () => {
  assert.deepEqual(buildReversePromptPayload({
    poster_type: '喜报',
    visual_style: ['孟菲斯', '孟菲斯', '明快', '', '几何', '高对比', '商业', '多余'],
    generation_prompt: '  生成喜报  ',
  }), {
    title: '喜报逆向提示词',
    content: '生成喜报',
    category: 'poster',
    tags: ['孟菲斯', '明快', '几何', '高对比', '商业'],
    source_mode: 'reverse_analysis',
  })
})

test('reverse analysis error exposes only stable API messages and safe retry delay', () => {
  assert.deepEqual(normalizeReverseAnalysisError({
    response: {
      data: { detail: { code: 'UPSTREAM_RATE_LIMITED', message: '模型繁忙，请稍后重试' } },
      headers: { 'retry-after': '30' },
    },
  }), { code: 'UPSTREAM_RATE_LIMITED', message: '模型繁忙，请稍后重试', retryAfter: 30 })

  assert.deepEqual(normalizeReverseAnalysisError({
    response: { data: { detail: { message: { secret: 'do not expose' } } }, headers: { 'retry-after': '-5' } },
  }), { code: 'UNKNOWN', message: '分析失败，请稍后重试', retryAfter: null })
  assert.ok(MAX_POSTER_DATA_URL_LENGTH > 10 * 1024 * 1024)
})

test('request state ignores stale and closed modal responses', () => {
  const state = createReverseAnalysisRequestState()
  const first = state.begin()
  const second = state.begin()
  assert.equal(state.accept(first), false)
  assert.equal(state.accept(second), true)
  state.close()
  assert.equal(state.accept(second), false)
})

test('poster reverse modal and prompt library expose the complete workflow', async () => {
  const [modal, library, api] = await Promise.all([
    readFile(new URL('../src/components/prompt/PosterPromptAnalyzerModal.vue', import.meta.url), 'utf8'),
    readFile(new URL('../src/PromptLibraryPage.vue', import.meta.url), 'utf8'),
    readFile(new URL('../src/api.js', import.meta.url), 'utf8'),
  ])

  assert.match(api, /export async function reverseAnalyzePrompt\(data\)/)
  assert.match(api, /post\('\/prompts\/reverse-analyze'/)
  assert.match(library, /PosterPromptAnalyzerModal/)
  assert.match(library, /海报逆向/)
  assert.match(library, /showReverseAnalyzer/)

  assert.match(modal, /图片将发送至火山方舟/)
  assert.match(modal, /accept="image\/jpeg,image\/png,image\/webp"/)
  assert.match(modal, /quality:\s*0\.92/)
  assert.match(modal, /requestState\.accept/)
  assert.match(modal, /imagePreparationState\.accept/)
  assert.match(modal, /saveRequestState\.accept/)
  assert.match(modal, /async function handleFileChange[\s\S]*?requestState\.close\(\)/)
  assert.match(modal, /:disabled="imagePreparing \|\| status === 'saving'"/)
  assert.match(modal, /createPrompt/)
  assert.match(modal, /buildReversePromptPayload/)
  assert.match(modal, /reverse-analysis:/)
  assert.match(modal, /savePromptApplyPayload/)
  assert.match(modal, /clearPromptApplyPayload/)
  assert.match(modal, /tab:\s*'custom'/)
  assert.doesNotMatch(modal, /usePrompt/)
  assert.doesNotMatch(modal, /v-html/)
  assert.doesNotMatch(modal, /@click\.self=/)
  assert.doesNotMatch(modal, /@keyup\.esc|@keydown\.esc/)
  assert.match(modal, /result\.negative_prompt/)
  assert.match(modal, /status === 'saving' \|\| status === 'analyzing'/)
  assert.match(modal, /<textarea[^>]*:disabled="status === 'saving' \|\| status === 'saved'"/)
  assert.match(modal, /normalizeReverseAnalysisError\(error\)/)
  assert.match(modal, /v-if="imageBase64"[\s\S]*?>重试分析</)
  assert.match(modal, /fixed inset-0 z-\[2200\]/)
})
