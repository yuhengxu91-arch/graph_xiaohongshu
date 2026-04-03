<template>
  <div class="min-h-full bg-slate-50/40 p-6 md:p-10">
    <!-- 页面头部 -->
    <div class="max-w-7xl mx-auto mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
      <div class="space-y-2">
        <h2 class="text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-3">
          <span class="p-2 bg-blue-600 rounded-2xl shadow-lg shadow-blue-200 text-white">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
          </span>
          模板中心 <span class="text-slate-400 font-light text-xl ml-1">Template Lab</span>
        </h2>
        <p class="text-slate-500 max-w-xl leading-relaxed">
          沉淀您的 AI 制图资产。通过预设 Prompt 规范，让每一次创意生成都具备极高的水准与一致性。
        </p>
      </div>
      
      <!-- 搜索与新建 (手机端隐藏搜索，保持简洁) -->
      <div class="flex items-center gap-4">
        <button 
          v-if="currentTab === 'mine'" 
          @click="openCreateModal"
          class="px-6 py-2.5 bg-slate-900 text-white font-bold rounded-xl shadow-lg shadow-slate-200 hover:bg-black transition-all active:scale-95 flex items-center gap-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14m-7-7v14"/></svg>
          新建模板
        </button>
      </div>
    </div>

    <!-- 导航 Tab 区 -->
    <div class="max-w-7xl mx-auto mb-8">
      <div class="inline-flex p-1.5 bg-white border border-slate-200 rounded-2xl shadow-sm">
        <button 
          v-for="tab in [{id: 'mine', label: '我的模板', icon: '👤'}, {id: 'system', label: '系统模板', icon: '🏢'}]" 
          :key="tab.id"
          @click="currentTab = tab.id"
          :class="[
            'flex items-center gap-2 px-6 py-2 rounded-xl text-sm font-bold transition-all duration-200',
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

    <!-- 列表展示区 -->
    <div class="max-w-7xl mx-auto">
      <!-- 加载中 -->
      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <div v-for="i in 4" :key="i" class="bg-white rounded-2xl p-4 space-y-4 animate-pulse border border-slate-100">
          <div class="aspect-video bg-slate-100 rounded-xl"></div>
          <div class="h-4 bg-slate-100 rounded-full w-2/3"></div>
          <div class="h-3 bg-slate-100 rounded-full w-1/2"></div>
        </div>
      </div>
      
      <!-- 数据列表 -->
      <div 
        v-else-if="filteredTemplates.length > 0" 
        class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
      >
        <TemplatePreview 
          v-for="tpl in filteredTemplates" 
          :key="tpl.id || tpl.name"
          :template="tpl"
          :is-system="currentTab === 'system'"
          @use="useTemplate(tpl)"
          @edit="openEditModal(tpl)"
          @delete="handleDelete(tpl)"
          @duplicate="handleDuplicate(tpl)"
        />
      </div>
      
      <!-- 空状态 -->
      <div v-else class="min-h-[400px] flex flex-col items-center justify-center text-center p-12 bg-white rounded-[2.5rem] border-2 border-dashed border-slate-100">
        <div class="w-24 h-24 bg-slate-50 rounded-[2rem] flex items-center justify-center text-5xl mb-6 grayscale opacity-40">
          <svg v-if="currentTab === 'mine'" xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M8 7h6"/><path d="M8 11h8"/></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/></svg>
        </div>
        <h3 class="text-xl font-bold text-slate-800 mb-2">
          {{ currentTab === 'mine' ? '您的创意工坊虚位以待' : '系统模板正在准备中' }}
        </h3>
        <p class="text-slate-400 max-w-md mx-auto mb-8 leading-relaxed">
          {{ currentTab === 'mine' 
            ? '通过定义特定的 Prompt 和参数槽位，您可以将成功的制图经验转化为可复用的生产力工具。' 
            : '我们将不断更新各行业的精品制图范式，敬请期待。' 
          }}
        </p>
        <button 
          v-if="currentTab === 'mine'" 
          @click="openCreateModal"
          class="px-8 py-3 bg-blue-600 text-white font-bold rounded-2xl shadow-xl shadow-blue-100 hover:bg-blue-700 active:scale-95 transition-all flex items-center gap-2"
        >
          立即创建首个模板
        </button>
      </div>
    </div>

    <!-- 模板编辑器弹窗 -->
    <TemplateEditor 
      v-if="showEditor"
      :initial-data="editingTemplate"
      @close="showEditor = false"
      @save="handleSaveTemplate"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import TemplatePreview from './components/template/TemplatePreview.vue'
import TemplateEditor from './components/template/TemplateEditor.vue'
import { getTemplatesList, deleteTemplate, saveTemplate, duplicateTemplate } from './api.js'

const router = useRouter()

const currentTab = ref('mine') // 'mine' or 'system'
const templates = ref([])
const loading = ref(false)

const showEditor = ref(false)
const editingTemplate = ref(null)

const filteredTemplates = computed(() => {
  return templates.value.filter(t => {
    if (currentTab.value === 'system') return t.is_system === true
    return !t.is_system
  })
})

onMounted(() => {
  loadTemplates()
})

async function loadTemplates() {
  loading.value = true
  try {
    const res = await getTemplatesList({ scope: 'all' })
    templates.value = res || []
  } catch (e) {
    console.error('获取模板失败', e)
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  editingTemplate.value = null
  showEditor.value = true
}

function openEditModal(tpl) {
  editingTemplate.value = JSON.parse(JSON.stringify(tpl))
  showEditor.value = true
}

async function handleSaveTemplate(data) {
  try {
    const isEdit = !!data.id
    const saved = await saveTemplate(data)
    
    if (isEdit) {
      const idx = templates.value.findIndex(t => t.id === saved.id)
      if (idx !== -1) templates.value[idx] = saved
    } else {
      templates.value.unshift(saved)
    }
    showEditor.value = false
  } catch (e) {
    alert(`保存失败: ${e.message}`)
  }
}

async function handleDelete(tpl) {
  if (!confirm(`确定要删除模板《${tpl.name}》吗？`)) return
  try {
    await deleteTemplate(tpl.id)
    templates.value = templates.value.filter(t => t.id !== tpl.id)
  } catch (e) {
    alert(`删除失败: ${e.message}`)
  }
}

async function handleDuplicate(tpl) {
  try {
    const duplicated = await duplicateTemplate(tpl.id || tpl.name)
    templates.value.unshift(duplicated)
    currentTab.value = 'mine' // 切换到我的模板
  } catch (e) {
    alert(`复制失败: ${e.message}`)
  }
}

function useTemplate(tpl) {
  sessionStorage.setItem('use_template', JSON.stringify(tpl))
  router.push({ name: 'poster', query: { tab: 'template', tpl_id: tpl.id } })
}
</script>
