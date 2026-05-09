<template>
  <div class="h-full flex flex-col bg-slate-50/50">
    <!-- 头部区域 -->
    <div class="px-8 pt-8 pb-4 flex items-center justify-between shrink-0">
      <div>
        <h1 class="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <span>📚 提示词库</span>
        </h1>
        <p class="text-sm text-slate-500 mt-1">收藏您的高效提示词，让每次创作都有迹可循</p>
      </div>
      
      <button 
        @click="openEditor()"
        class="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-xl font-medium transition-colors shadow-sm shadow-blue-600/20 flex items-center gap-2"
      >
        <span>➕</span> 新建 Prompt
      </button>
    </div>

    <!-- 过滤器栏 -->
    <div class="px-8 py-3 flex items-center justify-between border-b border-slate-100 shrink-0 bg-white sticky top-0 z-10">
      <div class="flex items-center gap-6">
        <!-- 分类切换 -->
        <div class="flex items-center gap-2 p-1 bg-slate-100/80 rounded-xl">
          <button 
            v-for="cat in categories" :key="cat.value"
            @click="activeCategory = cat.value"
            class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
            :class="activeCategory === cat.value ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-600 hover:text-slate-800'"
          >
            {{ cat.label }}
          </button>
        </div>

        <div class="h-4 w-px bg-slate-200"></div>

        <!-- 作用域切换 -->
        <div class="flex items-center gap-4">
          <button 
            v-for="scope in scopes" :key="scope.value"
            @click="activeScope = scope.value"
            class="text-sm font-medium transition-colors border-b-2 py-1"
            :class="activeScope === scope.value ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'"
          >
            {{ scope.label }}
          </button>
        </div>
      </div>

      <!-- 搜索框 -->
      <div class="relative w-64">
        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <span class="text-slate-400 text-sm">🔍</span>
        </div>
        <input 
          v-model="searchKeyword"
          @keyup.enter="fetchPrompts"
          type="text" 
          placeholder="搜索提示词或内容..." 
          class="w-full pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
        />
        <button 
          v-if="searchKeyword" 
          @click="searchKeyword = ''; fetchPrompts()"
          class="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- 列表区域 -->
    <div class="flex-1 overflow-y-auto p-8 custom-scrollbar relative">
      <!-- 加载中 -->
      <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-slate-50/50 z-10 backdrop-blur-sm">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="prompts.length === 0" class="h-full flex flex-col items-center justify-center text-center">
        <div class="w-24 h-24 bg-slate-100 rounded-full flex items-center justify-center text-4xl mb-4">
          📭
        </div>
        <h3 class="text-lg font-medium text-slate-800 mb-1">暂无提示词</h3>
        <p class="text-slate-500 mb-6 text-sm max-w-md">
          {{ searchKeyword ? '没有找到匹配的内容，换个关键词试试' : '您还没有收藏任何提示词，快去创作中收藏或新建一个吧' }}
        </p>
        <button v-if="!searchKeyword" @click="openEditor()" class="px-6 py-2 bg-white border border-slate-200 rounded-xl hover:border-blue-300 hover:text-blue-600 transition-colors text-sm font-medium">
          新建 Prompt
        </button>
      </div>

      <!-- 网格列表 -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 content-start">
        <PromptCard 
          v-for="prompt in prompts" 
          :key="prompt.id" 
          :prompt="prompt"
          @edit="openEditor(prompt)"
          @delete="handleDelete"
          @publish="handlePublish"
        />
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <PromptEditor 
      v-if="showEditor"
      :prompt="editingPrompt"
      @close="closeEditor"
      @saved="handleSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getPromptList, deletePrompt, publishPrompt } from './api'
import PromptCard from './components/prompt/PromptCard.vue'
import PromptEditor from './components/prompt/PromptEditor.vue'

// 状态
const loading = ref(false)
const prompts = ref([])
const activeCategory = ref('all')
const activeScope = ref('mine')
const searchKeyword = ref('')

const showEditor = ref(false)
const editingPrompt = ref(null)

// 常量
const categories = [
  { label: '全部', value: 'all' },
  { label: '🎨 海报生成', value: 'poster' },
  { label: '⚡ 内容工作流', value: 'workflow' },
  { label: '🔧 其他', value: 'other' }
]

const scopes = [
  { label: '我的收藏', value: 'mine' },
  { label: '公共广场', value: 'public' }
]

// 数据获取
const fetchPrompts = async () => {
  loading.value = true
  try {
    const res = await getPromptList({
      category: activeCategory.value,
      scope: activeScope.value,
      keyword: searchKeyword.value
    })
    prompts.value = res.items || []
  } catch (error) {
    console.error('获取提示词失败:', error)
  } finally {
    loading.value = false
  }
}

// 监听过滤器变化
watch([activeCategory, activeScope], () => {
  fetchPrompts()
})

onMounted(() => {
  fetchPrompts()
})

// 操作处理器
const openEditor = (prompt = null) => {
  editingPrompt.value = prompt ? JSON.parse(JSON.stringify(prompt)) : null
  showEditor.value = true
}

const closeEditor = () => {
  showEditor.value = false
  editingPrompt.value = null
}

const handleSaved = () => {
  closeEditor()
  fetchPrompts()
}

const handleDelete = async (id) => {
  if (confirm('确定要删除这条提示词吗？')) {
    try {
      await deletePrompt(id)
      fetchPrompts()
    } catch (e) {
      alert('删除失败')
    }
  }
}

const handlePublish = async (id) => {
  if (confirm('确定要发布到公共广场吗？其他人将可以看到并使用这条提示词。')) {
    try {
      await publishPrompt(id)
      fetchPrompts()
    } catch (e) {
      alert('发布失败')
    }
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 20px;
}
</style>
