<template>
  <div 
    class="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8 transition-all duration-300"
    :class="{ 'opacity-100 backdrop-blur-xl': true }"
  >
    <!-- 背景遮罩 -->
    <div class="absolute inset-0 bg-slate-900/60 transition-opacity" @click="$emit('close')"></div>
    
    <!-- 模态框主体 -->
    <div class="relative bg-white w-full max-w-6xl h-full max-h-[850px] rounded-[32px] shadow-2xl overflow-hidden flex flex-col md:flex-row animate-in fade-in zoom-in duration-300">
      <!-- 关闭按钮 -->
      <button 
        class="absolute top-6 right-6 z-20 w-10 h-10 flex items-center justify-center bg-white/20 hover:bg-white/40 backdrop-blur-md text-white rounded-full transition-all active:scale-90 text-2xl"
        @click="$emit('close')"
      >
        ×
      </button>

      <!-- 左侧：高清预览 -->
      <div class="flex-[1.5] bg-slate-950 flex shadow-inner relative group overflow-hidden">
        <img 
          :src="item.image_url" 
          :alt="item.title" 
          class="w-full h-full object-contain p-8 drop-shadow-2xl"
        />
        <!-- 装饰性渐变 -->
        <div class="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent pointer-events-none"></div>
      </div>

      <!-- 右侧：详情面板 -->
      <div class="flex-1 flex flex-col bg-white border-l border-slate-100 min-w-[380px]">
        <!-- 面板头部 -->
        <div class="p-8 border-b border-slate-50 space-y-4">
          <div class="flex flex-wrap gap-2">
            <span class="px-2.5 py-1 bg-blue-50 text-blue-600 rounded-lg text-xs font-bold uppercase tracking-wider">{{ formatMode(item.mode) }}</span>
            <span class="px-2.5 py-1 bg-slate-100 text-slate-500 rounded-lg text-xs font-bold">{{ item.aspect_ratio }}</span>
          </div>
          <h2 class="text-2xl font-black text-slate-800 leading-tight">
            {{ item.title || '未命名作品' }}
          </h2>
          <div class="flex items-center gap-2 text-slate-400 text-sm">
            <span>📅 创建于 {{ formatDate(item.created_at) }}</span>
          </div>
        </div>

        <!-- 面板主滚动区 -->
        <div class="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
          <!-- 提示词展示 -->
          <div class="space-y-3" v-if="item.prompt">
            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <span class="w-1 h-3 bg-blue-500 rounded-full"></span> 核心提示词
            </h3>
            <div class="p-4 bg-slate-50 rounded-2xl border border-slate-100 text-sm text-slate-700 leading-relaxed font-medium">
              {{ item.prompt }}
            </div>
          </div>

          <!-- AI 优化后的词 -->
          <div class="space-y-3" v-if="item.ai_prompt_used">
            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center justify-between">
              <span class="flex items-center gap-2"><span class="w-1 h-3 bg-indigo-500 rounded-full"></span> AI 执行词</span>
              <button 
                @click="copyText(item.ai_prompt_used)"
                class="text-blue-600 hover:text-blue-700 active:scale-95 transition-all flex items-center gap-1"
              >
                <span>📋</span> 复制
              </button>
            </h3>
            <div class="p-4 bg-slate-900 rounded-2xl border border-slate-800 text-[13px] text-slate-300 leading-relaxed font-mono break-all">
              {{ item.ai_prompt_used }}
            </div>
          </div>

          <!-- 风格标签 -->
          <div class="space-y-3" v-if="item.style_tags && item.style_tags.length">
            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <span class="w-1 h-3 bg-emerald-500 rounded-full"></span> 风格标签
            </h3>
            <div class="flex flex-wrap gap-2">
              <span 
                v-for="tag in item.style_tags" 
                :key="tag" 
                class="px-3 py-1.5 bg-slate-50 text-slate-600 rounded-xl text-xs font-bold border border-slate-100"
              >
                {{ tag }}
              </span>
            </div>
          </div>

          <!-- 参数详情 (JSON) -->
          <div class="space-y-3" v-if="item.params && Object.keys(item.params).length">
            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <span class="w-1 h-3 bg-orange-500 rounded-full"></span> 引擎详细参数
            </h3>
            <pre class="p-4 bg-slate-50 rounded-2xl text-[12px] text-slate-500 font-mono overflow-x-auto border border-slate-100">{{ JSON.stringify(item.params, null, 2) }}</pre>
          </div>
        </div>

        <!-- 面板底部操作区 -->
        <div class="p-8 border-t border-slate-50 bg-slate-50/30 grid grid-cols-2 gap-3">
          <button 
            class="col-span-2 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl font-bold shadow-lg shadow-blue-600/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
            @click="$emit('remix', item)"
          >
            🚀 基于此作品进行二次创作
          </button>
          <button 
            class="py-3 bg-white border border-slate-200 text-slate-700 rounded-2xl font-bold hover:bg-slate-50 transition-all flex items-center justify-center gap-2"
            @click="$emit('toggle-favorite', item.id)"
          >
            {{ item.is_favorite ? '⭐ 已收藏' : '☆ 加入收藏' }}
          </button>
          <button 
            class="py-3 bg-white border border-red-100 text-red-500 rounded-2xl font-bold hover:bg-red-50 transition-all flex items-center justify-center gap-2"
            @click="handleDelete"
          >
            🗑️ 彻底删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  item: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['close', 'toggle-favorite', 'delete', 'remix'])

function formatMode(mode) {
  const map = {
    custom: '自定义生成',
    template: '模板生成',
    edit: '以图改图',
    style_transfer: '风格迁移',
    inpaint: '局部重绘',
    erase: '智能擦除',
    adapt: '尺寸适配',
    export_all: '全平台导出',
    batch: '批量生成'
  }
  return map[mode] || mode
}

function formatDate(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleString()
}

function copyText(text) {
  navigator.clipboard.writeText(text)
    .then(() => alert('✅ 已成功复制到剪贴板'))
    .catch(() => alert('❌ 复制失败'))
}

function handleDelete() {
  if (confirm('确定要永久删除这份作品记录吗？图片文件也会被一并清理。')) {
    emit('delete', props.item.id)
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  display: none;
}
.custom-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
