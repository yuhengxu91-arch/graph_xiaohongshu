<template>
  <div v-if="result" class="animate-in fade-in zoom-in duration-700 bg-white rounded-[2rem] shadow-2xl shadow-blue-900/10 border border-slate-100 overflow-hidden">
    <!-- 头部标识 -->
    <div class="p-8 border-b border-slate-50 flex items-center justify-between bg-slate-50/30">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 flex items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/30">
          <span class="text-xl">✨</span>
        </div>
        <div>
          <h3 class="text-xl font-black text-slate-800 tracking-tight">创意生成结果</h3>
          <p class="text-[10px] text-slate-400 uppercase tracking-widest font-black mt-0.5">Creative Generation Result</p>
        </div>
      </div>
      <div 
        class="px-5 py-2 rounded-full text-xs font-black tracking-tight shadow-sm"
        :class="badgeTailwindClass"
      >
        {{ modeLabel }}
      </div>
    </div>

    <!-- 成功态内容 -->
    <div v-if="result.success" class="p-8 space-y-10">
      <!-- 单图展示 (Premium Preview) -->
      <div v-if="result.mode !== 'batch' && result.mode !== 'export_all'" class="relative group">
        <div class="absolute -inset-4 bg-gradient-to-r from-blue-500/10 to-indigo-500/10 rounded-[3rem] blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-1000"></div>
        <div class="relative bg-slate-900 rounded-[2.5rem] p-4 shadow-2xl overflow-hidden border-8 border-slate-900 mx-auto max-w-lg lg:max-w-2xl transform transition-transform duration-700 hover:scale-[1.02]">
          <img
            :src="getImageUrl(result.image_url)"
            alt="生成的海报"
            class="w-full h-auto rounded-[1.5rem] shadow-inner"
          />
          <div class="absolute top-8 right-8 flex flex-col gap-2">
            <a 
              :href="getImageUrl(result.image_url)" 
              download 
              class="w-12 h-12 bg-white/90 backdrop-blur-md rounded-2xl flex items-center justify-center shadow-xl hover:bg-white hover:scale-110 active:scale-95 transition-all"
              title="下载原始图像"
            >
              <span class="text-xl">⬇️</span>
            </a>
          </div>
        </div>
      </div>

      <!-- 全平台套装展示 -->
      <div v-else-if="result.mode === 'export_all'" class="space-y-6">
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-6">
          <div 
            v-for="(imgInfo, idx) in result.images" 
            :key="idx" 
            class="group bg-slate-50 border border-slate-200 rounded-3xl p-4 hover:bg-white hover:shadow-xl hover:-translate-y-1 transition-all"
          >
            <div class="aspect-[3/4] bg-slate-200 rounded-2xl overflow-hidden mb-4 relative shadow-inner">
              <img :src="getImageUrl(imgInfo.url)" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" alt="适配图片" />
              <div class="absolute inset-0 bg-slate-900/0 group-hover:bg-slate-900/20 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100">
                <a :href="getImageUrl(imgInfo.url)" download class="p-3 bg-white rounded-xl shadow-xl hover:scale-110 transition-transform">
                  📥
                </a>
              </div>
            </div>
            <div class="text-center">
              <div class="text-[13px] font-black text-slate-700">{{ imgInfo.ratio }}</div>
              <div class="text-[10px] text-slate-400 mt-0.5">Optimized for Platform</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 批量提交成功 -->
      <div v-else class="py-12 flex flex-col items-center text-center space-y-6 bg-blue-50/50 rounded-[2.5rem] border border-blue-100">
        <div class="w-24 h-24 bg-white rounded-full flex items-center justify-center text-5xl shadow-xl shadow-blue-600/10 animate-bounce">
          ✅
        </div>
        <div class="space-y-2">
          <h3 class="text-2xl font-black text-slate-800 italic">批量生成任务已正式启航！</h3>
          <div class="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 text-white rounded-xl text-xs font-mono tracking-widest">
            TASK ID: {{ result.task_id }}
          </div>
        </div>
        <p class="max-w-md text-slate-500 font-medium leading-relaxed px-8">
          AI 艺术家正在为您处理海量创意。您可以现在离开，稍后至“作品库”查看您的成果。
        </p>
      </div>

      <!-- 元数据卡片 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-if="result.aspect_ratio" class="bg-slate-50 rounded-2xl p-4 border border-slate-100">
          <div class="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">尺寸比例</div>
          <div class="text-sm font-bold text-slate-700 mt-1">{{ result.aspect_ratio }}</div>
        </div>
        <div v-if="result.width" class="bg-slate-50 rounded-2xl p-4 border border-slate-100">
          <div class="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">物理分辨率</div>
          <div class="text-sm font-bold text-slate-700 mt-1">{{ result.width }} × {{ result.height }}</div>
        </div>
        <div v-if="result.template_name" class="bg-slate-50 rounded-2xl p-4 border border-slate-100">
          <div class="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">设计模板</div>
          <div class="text-sm font-bold text-slate-700 mt-1 truncate" :title="result.template_name">{{ result.template_name }}</div>
        </div>
        <div class="bg-slate-50 rounded-2xl p-4 border border-slate-100">
          <div class="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">生成耗时</div>
          <div class="text-sm font-bold text-slate-700 mt-1">预计 15.2s</div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex flex-col sm:flex-row gap-4 pt-6">
        <button v-if="result.mode === 'batch'" class="flex-1 bg-slate-800 hover:bg-slate-900 text-white font-black py-4 rounded-2xl shadow-xl transition-all flex items-center justify-center gap-2" @click="checkBatchStatus">
          <span>🔄</span> 查看进度
        </button>
        <button class="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-black py-4 rounded-2xl shadow-xl shadow-blue-600/20 transition-all flex items-center justify-center gap-2 border-b-4 border-blue-800 active:border-b-0 active:translate-y-1" @click="$emit('reset')">
          <span>🎨</span> 继续创作
        </button>
      </div>
    </div>

    <!-- 错误态 -->
    <div v-else class="p-12 flex flex-col items-center text-center space-y-6">
      <div class="w-20 h-20 bg-red-50 rounded-full flex items-center justify-center text-4xl shadow-lg shadow-red-500/10">
        🥀
      </div>
      <div class="space-y-2">
        <h3 class="text-xl font-black text-red-600 italic tracking-tighter">创意在时空裂缝中迷失了...</h3>
        <p class="text-slate-500 text-sm font-medium px-8">{{ result.error || '可能是网络或服务器波动，请稍后再试' }}</p>
      </div>
      <button class="px-10 py-4 bg-slate-100 hover:bg-slate-200 text-slate-600 font-black rounded-2xl transition-all" @click="$emit('reset')">
        尝试修复并重试
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: {
    type: Object,
    default: null
  }
})

defineEmits(['reset'])

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

function checkBatchStatus() {
  if (props.result && props.result.task_id) {
    alert(`暂未开发轮询弹窗功能。\n当前任务 ID: ${props.result.task_id}\n请等待后续后端接口测试完成！`);
  }
}

function getImageUrl(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return `${API_BASE}${url}`
}

const badgeTailwindClass = computed(() => {
  if (!props.result) return ''
  return map[props.result.mode]?.tailwind || 'bg-slate-100 text-slate-600'
})

const map = {
  custom: { label: '自定义创意', tailwind: 'bg-blue-100 text-blue-700' },
  template: { label: '专业模板', tailwind: 'bg-emerald-100 text-emerald-700' },
  edit: { label: '智能改图', tailwind: 'bg-amber-100 text-amber-700' },
  inpaint: { label: '局部重绘', tailwind: 'bg-indigo-100 text-indigo-700' },
  erase: { label: '智能消除', tailwind: 'bg-rose-100 text-rose-700' },
  adapt: { label: '多端适配', tailwind: 'bg-cyan-100 text-cyan-700' },
  export_all: { label: '全端全家桶', tailwind: 'bg-purple-100 text-purple-700' },
  style_transfer: { label: '风格迁移', tailwind: 'bg-fuchsia-100 text-fuchsia-700' },
  batch: { label: '极速大批量', tailwind: 'bg-teal-100 text-teal-700' },
}
</script>


