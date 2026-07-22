<template>
  <div class="fixed inset-0 z-[2100] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
    <section class="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="reverse-analyzer-title">
      <header class="flex shrink-0 items-start justify-between border-b border-slate-100 px-6 py-5">
        <div>
          <h2 id="reverse-analyzer-title" class="text-xl font-bold text-slate-900">海报逆向</h2>
          <p class="mt-1 text-sm text-slate-500">提取文字、排版、配色与视觉风格，生成可复用提示词</p>
        </div>
        <button type="button" title="关闭" aria-label="关闭" class="grid h-9 w-9 place-items-center rounded-md text-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700" @click="requestClose">×</button>
      </header>

      <div class="flex-1 overflow-y-auto px-6 py-5">
        <div v-if="closeConfirmation" class="mb-5 flex items-center justify-between gap-4 border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span>当前分析或编辑内容尚未保存，确定关闭吗？</span>
          <div class="flex shrink-0 gap-2">
            <button type="button" class="px-3 py-1.5 font-medium text-slate-600" @click="closeConfirmation = false">继续编辑</button>
            <button type="button" class="rounded-md bg-amber-600 px-3 py-1.5 font-medium text-white hover:bg-amber-700" @click="confirmClose">确定关闭</button>
          </div>
        </div>

        <div class="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
          <div>
            <input ref="fileInput" class="hidden" type="file" accept="image/jpeg,image/png,image/webp" @change="handleFileChange" />
            <button type="button" class="relative flex aspect-[3/4] w-full items-center justify-center overflow-hidden border-2 border-dashed border-slate-200 bg-slate-50 text-center transition hover:border-blue-400 hover:bg-blue-50/40" @click="fileInput?.click()">
              <img v-if="imagePreview" :src="imagePreview" alt="待分析海报预览" class="h-full w-full object-contain" />
              <span v-else class="px-8">
                <span class="mx-auto grid h-12 w-12 place-items-center rounded-full bg-blue-50 text-2xl">↑</span>
                <strong class="mt-4 block text-sm text-slate-800">上传一张海报</strong>
                <span class="mt-2 block text-xs leading-5 text-slate-500">JPG、PNG、WEBP，最大 10MB<br />超大图片按最长边 4096px 高质量处理</span>
              </span>
            </button>
            <p class="mt-3 text-xs leading-5 text-slate-500">图片将发送至火山方舟 Doubao-Seed-2.1-Pro 分析，请勿上传包含敏感信息的素材。</p>
            <button type="button" :disabled="!imageBase64 || status === 'analyzing'" class="mt-4 w-full rounded-md bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300" @click="analyzePoster">
              {{ status === 'analyzing' ? '正在分析海报…' : result ? '重新分析' : '开始分析' }}
            </button>
          </div>

          <div class="min-h-[500px]">
            <div v-if="status === 'idle'" class="flex h-full min-h-[460px] flex-col items-center justify-center border border-slate-100 bg-slate-50/60 px-8 text-center">
              <span class="text-4xl">⌕</span>
              <h3 class="mt-4 font-semibold text-slate-800">等待分析</h3>
              <p class="mt-2 text-sm text-slate-500">上传海报后，系统会整理出可编辑的生成提示词。</p>
            </div>

            <div v-else-if="status === 'analyzing'" class="flex h-full min-h-[460px] flex-col items-center justify-center border border-blue-100 bg-blue-50/40 text-center">
              <span class="h-9 w-9 animate-spin rounded-full border-4 border-blue-100 border-t-blue-600"></span>
              <h3 class="mt-5 font-semibold text-slate-800">正在识别海报结构</h3>
              <p class="mt-2 text-sm text-slate-500">正在分析文字、布局、配色和视觉风格</p>
            </div>

            <div v-else-if="status === 'not_poster'" class="flex min-h-[460px] flex-col items-center justify-center border border-amber-100 bg-amber-50/50 px-8 text-center">
              <span class="text-4xl">!</span>
              <h3 class="mt-4 font-semibold text-slate-800">未识别为海报</h3>
              <p class="mt-2 text-sm text-slate-600">请上传包含明确标题、信息区和视觉排版的完整海报。</p>
            </div>

            <div v-else-if="status === 'error'" class="flex min-h-[460px] flex-col items-center justify-center border border-red-100 bg-red-50/50 px-8 text-center">
              <span class="text-4xl text-red-500">!</span>
              <h3 class="mt-4 font-semibold text-red-700">分析失败</h3>
              <p class="mt-2 max-w-md text-sm text-red-600">{{ errorMessage }}</p>
              <button type="button" class="mt-5 rounded-md border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50" @click="analyzePoster">重试分析</button>
            </div>

            <div v-else-if="result" class="space-y-5">
              <div class="flex flex-wrap items-center gap-2">
                <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">{{ result.poster_type || '海报' }}</span>
                <span class="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{{ result.aspect_ratio }}</span>
                <span v-for="style in result.visual_style" :key="style" class="rounded-full bg-violet-50 px-3 py-1 text-xs text-violet-700">{{ style }}</span>
              </div>

              <div class="grid gap-4 sm:grid-cols-2">
                <div class="border-l-2 border-blue-500 pl-3">
                  <h4 class="text-xs font-semibold uppercase text-slate-400">版式结构</h4>
                  <p class="mt-1 text-sm leading-6 text-slate-700">{{ result.layout_description || '未识别' }}</p>
                </div>
                <div class="border-l-2 border-emerald-500 pl-3">
                  <h4 class="text-xs font-semibold uppercase text-slate-400">字体特征</h4>
                  <p class="mt-1 text-sm leading-6 text-slate-700">{{ result.typography.join('、') || '未识别' }}</p>
                </div>
              </div>

              <div>
                <h4 class="text-xs font-semibold uppercase text-slate-400">主要配色</h4>
                <div class="mt-2 flex flex-wrap gap-3">
                  <span v-for="color in result.color_palette" :key="color" class="flex items-center gap-1.5 text-xs text-slate-600"><i class="h-5 w-5 border border-black/10" :style="{ backgroundColor: color }"></i>{{ color }}</span>
                </div>
              </div>

              <div>
                <h4 class="text-xs font-semibold uppercase text-slate-400">识别文字</h4>
                <div class="mt-2 max-h-28 overflow-y-auto bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">{{ result.recognized_text.join(' / ') || '未识别' }}</div>
              </div>

              <div>
                <div class="mb-2 flex items-center justify-between">
                  <label for="reverse-generation-prompt" class="text-sm font-semibold text-slate-800">生成提示词</label>
                  <span :class="editedPrompt.length > 4000 ? 'text-red-500' : 'text-slate-400'" class="text-xs">{{ editedPrompt.length }} / 4000</span>
                </div>
                <textarea id="reverse-generation-prompt" v-model="editedPrompt" :disabled="status === 'saved'" rows="9" class="w-full resize-none border border-slate-200 px-4 py-3 text-sm leading-6 text-slate-800 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50"></textarea>
              </div>

              <p v-if="actionMessage" :class="actionError ? 'text-red-600' : 'text-green-600'" class="text-sm">{{ actionMessage }}</p>

              <div class="flex flex-wrap justify-end gap-3 border-t border-slate-100 pt-4">
                <button type="button" class="rounded-md border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50" @click="copyPrompt">{{ copied ? '已复制' : '复制提示词' }}</button>
                <button type="button" :disabled="status === 'saving' || status === 'saved'" class="rounded-md border border-blue-200 px-4 py-2.5 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50" @click="savePrompt">{{ status === 'saved' ? '已保存' : status === 'saving' ? '保存中…' : '保存到我的收藏' }}</button>
                <button type="button" class="rounded-md bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700" @click="applyPrompt">应用到海报生成</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { isNavigationFailure, useRouter } from 'vue-router'
import { createPrompt, reverseAnalyzePrompt } from '../../api'
import {
  buildReversePromptPayload,
  createReverseAnalysisRequestState,
  normalizeReverseAnalysisError,
  preparePosterImage,
  validateReversePrompt,
} from '../../utils/posterReverseAnalysis.js'
import { clearPromptApplyPayload, savePromptApplyPayload } from '../../utils/promptApply.js'

const emit = defineEmits(['close', 'saved'])
const router = useRouter()
const requestState = createReverseAnalysisRequestState()
const fileInput = ref(null)
const imagePreview = ref('')
const imageBase64 = ref('')
const status = ref('idle')
const result = ref(null)
const editedPrompt = ref('')
const errorMessage = ref('')
const actionMessage = ref('')
const actionError = ref(false)
const copied = ref(false)
const savedPromptId = ref('')
const closeConfirmation = ref(false)

function resetResult() {
  result.value = null
  editedPrompt.value = ''
  savedPromptId.value = ''
  actionMessage.value = ''
  actionError.value = false
  copied.value = false
  status.value = 'idle'
}

async function handleFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  resetResult()
  try {
    imageBase64.value = await preparePosterImage(file, { quality: 0.92 })
    imagePreview.value = imageBase64.value
  } catch (error) {
    imageBase64.value = ''
    imagePreview.value = ''
    status.value = 'error'
    errorMessage.value = error.message || '图片处理失败，请重试'
  } finally {
    event.target.value = ''
  }
}

async function analyzePoster() {
  if (!imageBase64.value || status.value === 'analyzing') return
  const requestId = requestState.begin()
  status.value = 'analyzing'
  result.value = null
  savedPromptId.value = ''
  actionMessage.value = ''
  try {
    const analysis = await reverseAnalyzePrompt({ image_base64: imageBase64.value })
    if (!requestState.accept(requestId)) return
    if (!analysis.is_poster) {
      status.value = 'not_poster'
      return
    }
    result.value = analysis
    editedPrompt.value = analysis.generation_prompt || ''
    status.value = 'success'
  } catch (error) {
    if (!requestState.accept(requestId)) return
    const normalized = normalizeReverseAnalysisError(error)
    errorMessage.value = normalized.retryAfter
      ? `${normalized.message}（约 ${normalized.retryAfter} 秒后可重试）`
      : normalized.message
    status.value = 'error'
  }
}

async function copyPrompt() {
  try {
    const content = validateReversePrompt(editedPrompt.value)
    await navigator.clipboard.writeText(content)
    copied.value = true
    setTimeout(() => { copied.value = false }, 1800)
  } catch (error) {
    actionError.value = true
    actionMessage.value = error.message || '复制失败，请重试'
  }
}

async function savePrompt() {
  if (!result.value || status.value === 'saving' || status.value === 'saved') return
  actionMessage.value = ''
  try {
    const payload = buildReversePromptPayload(result.value, editedPrompt.value)
    status.value = 'saving'
    const saved = await createPrompt(payload)
    savedPromptId.value = saved.id
    status.value = 'saved'
    actionError.value = false
    actionMessage.value = '已保存到我的收藏'
    emit('saved', saved)
  } catch (error) {
    status.value = 'success'
    actionError.value = true
    actionMessage.value = error?.response?.data?.detail || error.message || '保存失败，请重试'
  }
}

async function applyPrompt() {
  actionMessage.value = ''
  try {
    const content = validateReversePrompt(editedPrompt.value)
    const transientId = `reverse-analysis:${crypto.randomUUID()}`
    savePromptApplyPayload(sessionStorage, {
      prompt_id: transientId,
      category: 'poster',
      content,
      created_at: Date.now(),
    })
    const navigationFailure = await router.push({ name: 'poster', query: { tab: 'custom' } })
    if (isNavigationFailure(navigationFailure)) throw navigationFailure
    requestState.close()
    emit('close')
  } catch (error) {
    clearPromptApplyPayload(sessionStorage)
    actionError.value = true
    actionMessage.value = error.message || '应用失败，请重试'
  }
}

function requestClose() {
  const hasUnsavedWork = status.value === 'analyzing'
    || Boolean(result.value && status.value !== 'saved')
  if (hasUnsavedWork) {
    closeConfirmation.value = true
    return
  }
  confirmClose()
}

function confirmClose() {
  requestState.close()
  closeConfirmation.value = false
  emit('close')
}

onBeforeUnmount(() => requestState.close())
</script>
