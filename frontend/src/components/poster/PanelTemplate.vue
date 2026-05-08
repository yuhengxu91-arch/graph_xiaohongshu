<template>
  <div class="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
    <!-- 模板选择列表 -->
    <div v-if="!selectedTemplate" class="space-y-6">
      <div class="flex flex-col md:flex-row md:items-center justify-between px-4 gap-4">
        <div>
          <h2 class="text-xl font-bold text-slate-800 tracking-tight">精选设计模板</h2>
          <p class="text-xs text-slate-400 mt-1 uppercase tracking-widest font-semibold">Premium Design Templates</p>
        </div>
        
        <!-- Tab 切换 -->
        <div class="inline-flex p-1 bg-white border border-slate-200 rounded-2xl shadow-sm self-start">
          <button 
            v-for="tab in [{id: 'mine', label: '我的模板', icon: '👤'}, {id: 'system', label: '公共模板', icon: '🏛️'}]" 
            :key="tab.id"
            @click="currentTab = tab.id"
            :class="[
              'flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-xs font-bold transition-all duration-200',
              currentTab === tab.id 
                ? 'bg-blue-600 text-white shadow-md shadow-blue-100' 
                : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
            ]"
          >
            <span>{{ tab.icon }}</span>
            {{ tab.label }}
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" v-if="filteredTemplates.length > 0">
        <TemplatePreview
          v-for="tpl in filteredTemplates"
          :key="tpl.id"
          :template="tpl"
          :isSystem="currentTab === 'system'"
          :selectionMode="true"
          @click="selectTemplate(tpl)"
          @use="selectTemplate(tpl)"
          class="cursor-pointer"
        />
      </div>
      
      <!-- 空状态 -->
      <div v-else-if="templates.length > 0" class="py-20 flex flex-col items-center justify-center gap-4 border-2 border-dashed border-slate-100 rounded-3xl bg-slate-50/50">
        <span class="text-4xl grayscale opacity-40">{{ currentTab === 'mine' ? '📂' : '🏛️' }}</span>
        <p class="text-slate-500 font-medium">{{ currentTab === 'mine' ? '您还没有创建过个人模板' : '暂无公共模板' }}</p>
      </div>
      
      <!-- 加载中 -->
      <div v-else class="py-32 flex flex-col items-center justify-center gap-6">
        <div class="w-12 h-12 border-4 border-blue-50 border-t-blue-600 rounded-full animate-spin"></div>
        <div class="text-center">
          <p class="text-lg font-bold text-slate-700">正在同步云端模板库...</p>
          <p class="text-slate-400 text-xs mt-1">Fetching the latest creative inspirations</p>
        </div>
      </div>
    </div>

    <!-- 模板参数配置 -->
    <div v-if="selectedTemplate" class="bg-white rounded-[2.5rem] shadow-2xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
      <div class="p-8 border-b border-slate-50 bg-slate-50/30 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <button @click="selectedTemplate = null" class="w-10 h-10 rounded-2xl bg-white border border-slate-200 flex items-center justify-center text-slate-400 hover:text-blue-600 hover:border-blue-100 hover:bg-blue-50 transition-all">
            ←
          </button>
          <div>
            <h2 class="text-xl font-bold text-slate-800">{{ selectedTemplate.name }}</h2>
            <p class="text-xs text-slate-400 font-medium">定制您的专属内容</p>
          </div>
        </div>
        <div class="px-4 py-1.5 bg-blue-50 text-blue-600 text-[10px] font-black rounded-full uppercase tracking-widest border border-blue-100">
          Template Config
        </div>
      </div>

      <div class="p-8 space-y-10">
        <!-- 动态参数列表 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div
            v-for="slot in selectedTemplate.text_slots"
            :key="slot.name"
            class="space-y-4"
            :class="slot.multiline ? 'md:col-span-2' : ''"
          >
            <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
              <span class="text-blue-500">✏️</span> {{ slot.label }}
              <span v-if="slot.required" class="text-red-400 text-xs font-normal">(必填)</span>
            </label>
            <textarea
              v-if="slot.multiline"
              v-model="form.params[slot.name]"
              class="w-full bg-slate-50 border border-slate-200 rounded-[1.5rem] px-6 py-5 text-sm focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-600 outline-none transition-all placeholder:text-slate-400 resize-none"
              :placeholder="`请输入${slot.label}...`"
              rows="4"
            ></textarea>
            <input
              v-else
              v-model="form.params[slot.name]"
              class="w-full bg-slate-50 border border-slate-200 rounded-2xl px-6 py-4 text-sm focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-600 outline-none transition-all placeholder:text-slate-400"
              :placeholder="`请输入${slot.label}`"
              :maxlength="slot.max_length || 100"
            />
          </div>
        </div>

        <!-- 颜色方案与尺寸并排 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-10 border-t border-slate-50 pt-10">
          <div class="space-y-4" v-if="selectedTemplate.color_options?.length > 0">
            <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
              <span class="text-blue-500">🎨</span> 色调选项
            </label>
            <div class="flex flex-wrap gap-2.5">
              <button
                v-for="color in selectedTemplate.color_options"
                :key="color"
                class="px-5 py-2.5 rounded-xl border-2 font-bold text-sm transition-all"
                :class="form.colorOption === color 
                  ? 'border-blue-600 bg-blue-50 text-blue-700 shadow-md shadow-blue-600/10' 
                  : 'border-slate-100 bg-white hover:border-blue-200 text-slate-600'"
                @click="form.colorOption = color"
              >
                {{ color }}
              </button>
            </div>
          </div>

          <div class="space-y-4">
            <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
              <span class="text-blue-500">📏</span> 输出尺寸
              <span class="text-xs text-slate-400 font-normal">(默认: {{ selectedTemplate.default_aspect_ratio }})</span>
            </label>
            <RatioSelector 
              :modelValue="form.aspectRatio || selectedTemplate.default_aspect_ratio"
              @update:modelValue="val => form.aspectRatio = val"
              :ratios="aspectRatios" 
            />
          </div>
        </div>

        <!-- 生成按钮 -->
        <div class="pt-6">
          <button
            class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed text-white font-black py-5 rounded-[2rem] shadow-2xl shadow-blue-600/30 transition-all flex items-center justify-center gap-3 group relative overflow-hidden"
            :disabled="!isValid || generating"
            @click="handleGenerate"
          >
            <span v-if="generating" class="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            <span v-else class="text-xl transition-transform group-hover:scale-125 group-hover:rotate-12 duration-300">🪄</span>
            <span class="text-lg tracking-wide">{{ generating ? '正在施展魔法...' : '生成渲染海报' }}</span>
            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-shimmer" v-if="!generating"></div>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import RatioSelector from './RatioSelector.vue'
import TemplatePreview from '../template/TemplatePreview.vue'

const props = defineProps({
  templates: { type: Array, default: () => [] },
  aspectRatios: { type: Array, default: () => [] },
  generating: { type: Boolean, default: false }
})

const emit = defineEmits(['generate'])

const currentTab = ref('system')
const filteredTemplates = computed(() => {
  return props.templates.filter(t => {
    if (currentTab.value === 'system') return t.is_system === true
    return !t.is_system
  })
})

const selectedTemplate = ref(null)
const form = ref({
  params: {},
  colorOption: '',
  aspectRatio: null,
})

onMounted(() => {
  const saved = sessionStorage.getItem('use_template')
  if (saved) {
    sessionStorage.removeItem('use_template')
    try {
      const tpl = JSON.parse(saved)
      if (tpl && tpl.config) {
        selectTemplate({
          id: tpl.id || null,
          index: tpl.sort_order || 0,
          name: tpl.name,
          description: tpl.description,
          category: tpl.category,
          style_tag: tpl.style_tag,
          text_slots: tpl.config.text_slots || [],
          color_options: tpl.config.color_options || [],
          default_aspect_ratio: tpl.config.default_aspect_ratio || '3:4',
          ai_prompt_template: tpl.config.ai_prompt_template || '',
        })
      }
    } catch (e) {
      console.error('解析模板数据失败:', e)
    }
  }
})

const isValid = computed(() => {
  if (!selectedTemplate.value) return false
  const slots = selectedTemplate.value.text_slots || []
  for (const slot of slots) {
    if (slot.required && !form.value.params[slot.name]?.trim()) {
      return false
    }
  }
  return true
})

function selectTemplate(tpl) {
  // 兜底：确保从 config 中解构出关键字段（防止缓存/数据源未映射的情况）
  const resolved = {
    ...tpl,
    text_slots: tpl.text_slots || tpl.config?.text_slots || [],
    color_options: tpl.color_options || tpl.config?.color_options || [],
    default_aspect_ratio: tpl.default_aspect_ratio || tpl.config?.default_aspect_ratio || '3:4',
    ai_prompt_template: tpl.ai_prompt_template || tpl.config?.ai_prompt_template || '',
  }
  selectedTemplate.value = resolved
  const params = {}
  for (const slot of resolved.text_slots) {
    params[slot.name] = ''
  }
  form.value = {
    params,
    colorOption: resolved.color_options?.[0] || '',
    aspectRatio: null,
  }
}


function handleGenerate() {
  if (!selectedTemplate.value || !isValid.value || props.generating) return
  emit('generate', {
    template: selectedTemplate.value,
    ...form.value
  })
}
</script>
