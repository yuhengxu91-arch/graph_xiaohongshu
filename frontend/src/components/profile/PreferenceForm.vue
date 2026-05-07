<template>
  <div class="preference-card">
    <h3>偏好设置</h3>
    
    <div class="form-container">
      <div class="form-group row">
        <label>默认生成比例</label>
        <select v-model="form.default_aspect_ratio" class="select" @change="debouncedSave">
          <option value="3:4">小红书竖图 (3:4)</option>
          <option value="1:1">朋友圈头图 (1:1)</option>
          <option value="9:16">抖音/视频号 (9:16)</option>
          <option value="2.35:1">公众号封面 (2.35:1)</option>
          <option value="4:3">网页横图 (4:3)</option>
        </select>
      </div>

      <div class="form-group row">
        <label>默认生成模式</label>
        <select v-model="form.default_mode" class="select" @change="debouncedSave">
          <option value="custom">提示词自定义</option>
          <option value="template">模板生成</option>
        </select>
      </div>
      
      <div class="form-group row">
        <label>自动保存到库</label>
        <div class="toggle-wrapper">
          <input type="checkbox" id="auto_save" v-model="form.auto_save" class="hidden-cb" @change="debouncedSave" />
          <label for="auto_save" class="toggle"></label>
          <span class="hint">生成成功的图片自动存入作品库</span>
        </div>
      </div>
      
      <div class="divider"></div>

      <!-- 图片生成引擎选择 -->
      <div class="form-group">
        <label class="section-label">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/></svg>
          图片生成引擎
        </label>
        <div class="engine-options">
          <label 
            v-for="engine in engines" 
            :key="engine.value"
            class="engine-option"
            :class="{ active: form.image_provider === engine.value }"
          >
            <input 
              type="radio" 
              :value="engine.value" 
              v-model="form.image_provider" 
              class="hidden-radio"
              @change="debouncedSave"
            />
            <span class="engine-icon">{{ engine.icon }}</span>
            <span class="engine-info">
              <span class="engine-name">{{ engine.label }}</span>
              <span class="engine-desc">{{ engine.desc }}</span>
            </span>
            <span v-if="form.image_provider === engine.value" class="check-icon">✓</span>
          </label>
        </div>
      </div>

      <div class="divider"></div>
      
      <div class="form-group">
        <label>自定义 Gemini API Key</label>
        <input 
          type="password" 
          v-model="form.custom_api_key" 
          class="input" 
          placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx" 
          @change="debouncedSave"
        />
        <p class="hint">若留空，则使用系统的默认 API Key。保护好您的 Key！</p>
      </div>

      <p v-if="saveMsg" :class="['save-msg', saveMsgError ? 'error' : '']">{{ saveMsg }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  prefs: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update-prefs'])

const engines = [
  { value: null,         icon: '⚙️', label: '跟随系统默认',     desc: '使用 .env 全局配置的引擎' },
  { value: 'gemini',     icon: '💎', label: 'Gemini (xunruijie)', desc: 'gemini-3-pro-image-preview' },
  { value: 'gpt_image',  icon: '🖼️', label: 'GPT Image 2',        desc: 'OpenAI GPT Image 2 生图 (scdn)' },
  { value: 'doubao',     icon: '🎨', label: '豆包 Seedream',      desc: '火山方舟 doubao-seedream 生图' },
  { value: 'jimeng',     icon: '🔮', label: '即梦',               desc: '火山引擎即梦 AI 生图' },
]

const form = ref({
  default_aspect_ratio: '3:4',
  default_mode: 'custom',
  auto_save: true,
  image_provider: null,
  custom_api_key: ''
})

const saveMsg = ref('')
const saveMsgError = ref(false)
let timer = null

// Init form from props
watch(() => props.prefs, (newVal) => {
  if (newVal && Object.keys(newVal).length > 0) {
    form.value = { ...form.value, ...newVal }
  }
}, { immediate: true })

function debouncedSave() {
  saveMsg.value = '正在保存...'
  saveMsgError.value = false
  clearTimeout(timer)
  timer = setTimeout(() => {
    emit('update-prefs', { ...form.value }, (err) => {
      if (err) {
        saveMsg.value = '保存失败: ' + err
        saveMsgError.value = true
      } else {
        saveMsg.value = '✓ 已自动保存'
        saveMsgError.value = false
        setTimeout(() => saveMsg.value = '', 2000)
      }
    })
  }, 500)
}
</script>

<style scoped>
.preference-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
  height: 100%;
}

h3 {
  margin: 0 0 20px 0;
  font-size: 16px;
  color: #303133;
  border-left: 4px solid #409eff;
  padding-left: 10px;
}

.form-container {
  max-width: 480px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

label {
  font-size: 14px;
  color: #606266;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.section-label .icon {
  width: 16px;
  height: 16px;
  color: #409eff;
}

.select, .input {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 14px;
  color: #606266;
  width: 200px;
}

.input {
  width: 100%;
  margin-top: 8px;
}

.hint {
  font-size: 12px;
  color: #c0c4cc;
  margin: 6px 0 0 0;
}

.divider {
  height: 1px;
  background: #ebeef5;
  margin: 24px 0;
}

.save-msg {
  color: #67c23a;
  font-size: 12px;
  text-align: right;
  margin-top: -10px;
}

.save-msg.error {
  color: #f56c6c;
}

/* ===== 引擎选择卡片 ===== */
.engine-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hidden-radio {
  display: none;
}

.engine-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 2px solid #ebeef5;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fafafa;
}

.engine-option:hover {
  border-color: #c0d4f0;
  background: #f5f8ff;
}

.engine-option.active {
  border-color: #409eff;
  background: linear-gradient(135deg, #f0f6ff 0%, #e8f0fe 100%);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.engine-icon {
  font-size: 22px;
  flex-shrink: 0;
  width: 32px;
  text-align: center;
}

.engine-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.engine-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.engine-desc {
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.check-icon {
  color: #409eff;
  font-weight: 700;
  font-size: 16px;
  flex-shrink: 0;
}

/* Toggle Switch */
.hidden-cb {
  display: none;
}

.toggle-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toggle {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 20px;
  background-color: #dcdfe6;
  border-radius: 20px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.toggle::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  background-color: white;
  border-radius: 50%;
  transition: transform 0.3s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.hidden-cb:checked + .toggle {
  background-color: #409eff;
}

.hidden-cb:checked + .toggle::after {
  transform: translateX(20px);
}
</style>
