<template>
  <div class="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
    <!-- 主配置卡片 -->
    <div class="bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
      <div class="p-8 border-b border-slate-50 bg-slate-50/30">
        <h2 class="text-xl font-bold text-slate-800 tracking-tight">自定义生成</h2>
        <p class="text-xs text-slate-400 mt-1 uppercase tracking-widest font-semibold">Custom Creative Generation</p>
      </div>

      <div class="p-8 space-y-8">
        <!-- 提示词输入 -->
        <div class="space-y-4">
          <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
            <span class="text-blue-500">✍️</span> 提示词描述
          </label>
          <textarea
            v-model="form.prompt"
            class="w-full bg-slate-50 border border-slate-200 rounded-3xl px-6 py-5 text-sm focus:ring-4 focus:ring-blue-500/10 focus:border-blue-600 outline-none transition-all placeholder:text-slate-400 resize-none overflow-y-auto"
            placeholder="描述你想要的海报风格和内容，例如：一张关于春日踏青的小红书封面，清新自然、阳光明媚..."
            rows="5"
          ></textarea>
        </div>

        <!-- 风格标签选择 -->
        <div class="space-y-4">
          <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
            <span class="text-blue-500">🏷️</span> 风格标签
            <span class="text-xs text-slate-400 font-normal">（可多选）</span>
          </label>
          
          <div class="flex flex-wrap gap-2.5" v-if="styleTags.length > 0">
            <button
              v-for="tag in styleTags"
              :key="tag.name"
              class="group flex items-center gap-2 px-4 py-2 rounded-2xl border-2 transition-all"
              :class="form.selectedStyles.includes(tag.name) 
                ? 'border-blue-600 bg-blue-50 shadow-md shadow-blue-600/10' 
                : 'border-slate-100 bg-white hover:border-blue-200 hover:bg-slate-50'"
              @click="toggleStyle(tag.name)"
            >
              <span class="text-base group-hover:scale-110 transition-transform">{{ tag.icon }}</span>
              <span class="text-sm font-bold" :class="form.selectedStyles.includes(tag.name) ? 'text-blue-700' : 'text-slate-600'">{{ tag.name }}</span>
            </button>
          </div>
          <div v-else class="flex items-center gap-3 py-4 text-slate-400 animate-pulse">
            <div class="w-4 h-4 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin"></div>
            <span class="text-sm font-medium">加载审美预设...</span>
          </div>
        </div>

        <!-- 尺寸与色调 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
          <div class="space-y-4">
            <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
              <span class="text-blue-500">📏</span> 输出尺寸
            </label>
            <RatioSelector v-model="form.aspectRatio" :ratios="aspectRatios" />
          </div>
          <div class="space-y-4">
            <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
              <span class="text-blue-500">🎨</span> 色调偏好
            </label>
            <input
              v-model="form.colorTone"
              class="w-full bg-slate-50 border border-slate-200 rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-blue-500/10 focus:border-blue-600 outline-none transition-all placeholder:text-slate-400"
              placeholder="例如：暖色调、莫兰迪色系、黑金色..."
            />
          </div>
        </div>

        <!-- 生成按钮 -->
        <div class="pt-4 border-t border-slate-50">
          <button
            class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed text-white font-bold py-5 rounded-3xl shadow-2xl shadow-blue-600/30 transition-all flex items-center justify-center gap-3 group relative overflow-hidden"
            :disabled="!form.prompt.trim() || generating"
            @click="handleGenerate"
          >
            <span v-if="generating" class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            <span v-else class="text-xl transition-transform group-hover:scale-125 group-hover:rotate-12 duration-300">🎨</span>
            <span class="text-lg tracking-wide">{{ generating ? 'AI 画家构思中...' : '开始生成海报' }}</span>
            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-shimmer" v-if="!generating"></div>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import RatioSelector from './RatioSelector.vue'

const props = defineProps({
  styleTags: { type: Array, default: () => [] },
  aspectRatios: { type: Array, default: () => [] },
  generating: { type: Boolean, default: false }
})

const emit = defineEmits(['generate'])

const form = ref({
  prompt: '',
  selectedStyles: [],
  aspectRatio: '3:4',
  colorTone: '',
})

function toggleStyle(name) {
  const idx = form.value.selectedStyles.indexOf(name)
  if (idx >= 0) {
    form.value.selectedStyles.splice(idx, 1)
  } else {
    form.value.selectedStyles.push(name)
  }
}

function getTagStyle(tag) {
  const palette = tag.color_palette || []
  if (palette.length >= 2) {
    return {
      '--tag-color-1': palette[0],
      '--tag-color-2': palette[1],
    }
  }
  return {}
}

function handleGenerate() {
  if (!form.value.prompt.trim() || props.generating) return
  emit('generate', { ...form.value })
}
</script>
