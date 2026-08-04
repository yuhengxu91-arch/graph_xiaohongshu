<template>
  <div class="model-switcher" ref="switcherRef">
    <button
      class="switcher-trigger"
      :class="{ open: showDropdown }"
      @click="toggleDropdown"
      :title="currentDisplay.label + ' · ' + currentDisplay.provider"
    >
      <span class="trigger-icon">{{ currentDisplay.icon }}</span>
      <div class="trigger-text">
        <div class="trigger-label">当前模型 <span class="trigger-hint">· 点击切换</span></div>
        <div class="trigger-value">
          {{ currentDisplay.label }}
          <span class="trigger-provider">/ {{ currentDisplay.provider }}</span>
        </div>
      </div>
      <svg class="chevron" :class="{ rotated: showDropdown }" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <Transition name="dropdown">
      <div v-if="showDropdown" class="dropdown-panel">
        <div class="dropdown-header">选择生图模型</div>
        <div class="dropdown-list">
          <!-- 跟随偏好 -->
          <button
            class="dropdown-item"
            :class="{ active: !modelValue }"
            @click="selectModel(null)"
          >
            <span class="item-icon">⚙️</span>
            <div class="item-info">
              <div class="item-name">跟随个人偏好</div>
              <div class="item-desc">使用偏好设置中的模型</div>
            </div>
            <span v-if="!modelValue" class="item-check">✓</span>
          </button>

          <!-- 内置模型 -->
          <div class="dropdown-group">内置模型</div>
          <button
            v-for="engine in builtinOptions"
            :key="engine.value"
            class="dropdown-item"
            :class="{ active: modelValue === engine.value }"
            @click="selectModel(engine.value)"
          >
            <span class="item-icon">{{ engine.icon }}</span>
            <div class="item-info">
              <div class="item-name">{{ engine.label }}</div>
              <div class="item-desc">{{ engine.desc }}</div>
            </div>
            <span v-if="modelValue === engine.value" class="item-check">✓</span>
          </button>

          <!-- 公共模型 -->
          <template v-if="configOptions.length">
            <div class="dropdown-group">公共配置模型</div>
            <button
              v-for="model in configOptions"
              :key="model.value"
              class="dropdown-item"
              :class="{ active: modelValue === model.value }"
              @click="selectModel(model.value)"
            >
              <span class="item-icon">{{ model.icon }}</span>
              <div class="item-info">
                <div class="item-name">{{ model.label }}</div>
                <div class="item-desc">{{ model.desc }}</div>
              </div>
              <span v-if="modelValue === model.value" class="item-check">✓</span>
            </button>
          </template>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getImageModels } from '../../api'

const props = defineProps({
  modelValue: { type: String, default: null },
  currentImageModel: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const showDropdown = ref(false)
const switcherRef = ref(null)
const imageModels = ref([])

const builtinOptions = [
  { value: 'builtin:gemini', icon: '💎', label: 'Gemini', desc: 'gemini-3-pro · xunruijie' },
  { value: 'builtin:gpt_image', icon: '🖼️', label: 'GPT Image 2', desc: 'gpt-image-2 · scdn' },
  { value: 'builtin:doubao', icon: '🎨', label: '豆包 Seedream', desc: 'doubao-seedream · 火山方舟' },
]

const configOptions = computed(() => {
  return imageModels.value
    .filter(m => m.is_active)
    .map(m => ({
      value: `config:${m.id}`,
      icon: providerIcon(m.provider_type),
      label: m.name,
      desc: `${m.model_name} · ${providerLabel(m.provider_type)}`,
    }))
})

const currentDisplay = computed(() => {
  if (!props.modelValue) {
    // 跟随偏好 - 显示偏好中的模型
    if (props.currentImageModel) {
      return props.currentImageModel
    }
    return { icon: '⚙️', label: '跟随偏好', provider: '个人设置' }
  }
  // 查找选中的模型
  const builtin = builtinOptions.find(o => o.value === props.modelValue)
  if (builtin) {
    return { icon: builtin.icon, label: builtin.label, provider: builtin.desc }
  }
  const config = configOptions.value.find(o => o.value === props.modelValue)
  if (config) {
    return { icon: config.icon, label: config.label, provider: config.desc }
  }
  return { icon: '❓', label: '未知模型', provider: '' }
})

onMounted(async () => {
  try {
    const data = await getImageModels(false)
    imageModels.value = data.items || []
  } catch { /* ignore */ }
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
}

function selectModel(value) {
  emit('update:modelValue', value)
  showDropdown.value = false
}

function handleClickOutside(e) {
  if (switcherRef.value && !switcherRef.value.contains(e.target)) {
    showDropdown.value = false
  }
}

function providerIcon(type) {
  if (type === 'gemini') return '💎'
  if (type === 'doubao') return '🎨'
  return '🖼️'
}

function providerLabel(type) {
  if (type === 'openai_image') return 'OpenAI 兼容'
  if (type === 'gemini') return 'Gemini'
  if (type === 'doubao') return '豆包'
  return type || '未知'
}
</script>

<style scoped>
.model-switcher {
  position: relative;
}

.switcher-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: white;
  border: 1.5px solid #e2e8f0;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  max-width: 22rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.switcher-trigger:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.12);
}

.switcher-trigger.open {
  border-color: #3b82f6;
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.15);
}

.trigger-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.trigger-text {
  min-width: 0;
  text-align: left;
}

.trigger-label {
  font-size: 10px;
  font-weight: 800;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  line-height: 1;
}

.trigger-hint {
  font-weight: 600;
  color: #3b82f6;
  font-size: 9px;
}

.trigger-value {
  margin-top: 3px;
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trigger-provider {
  color: #94a3b8;
  font-weight: 600;
}

.chevron {
  width: 14px;
  height: 14px;
  color: #94a3b8;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.chevron.rotated {
  transform: rotate(180deg);
}

/* Dropdown */
.dropdown-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 320px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.06);
  z-index: 50;
  overflow: hidden;
}

.dropdown-header {
  padding: 14px 16px 10px;
  font-size: 11px;
  font-weight: 800;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 1px;
  border-bottom: 1px solid #f1f5f9;
}

.dropdown-list {
  max-height: 380px;
  overflow-y: auto;
  padding: 6px;
}

.dropdown-group {
  padding: 10px 12px 4px;
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  background: transparent;
  border: 1.5px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.dropdown-item:hover {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.dropdown-item.active {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.item-icon {
  font-size: 20px;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  border-radius: 10px;
}

.dropdown-item.active .item-icon {
  background: #dbeafe;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.item-desc {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-check {
  font-size: 14px;
  color: #3b82f6;
  font-weight: 800;
  flex-shrink: 0;
}

/* Transition */
.dropdown-enter-active {
  transition: all 0.2s ease;
}
.dropdown-leave-active {
  transition: all 0.15s ease;
}
.dropdown-enter-from {
  opacity: 0;
  transform: translateY(-8px) scale(0.96);
}
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
</style>
