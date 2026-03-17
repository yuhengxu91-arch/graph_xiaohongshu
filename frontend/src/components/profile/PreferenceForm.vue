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

      <p v-if="saveMsg" class="save-msg">{{ saveMsg }}</p>
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

const form = ref({
  default_aspect_ratio: '3:4',
  default_mode: 'custom',
  auto_save: true,
  custom_api_key: ''
})

const saveMsg = ref('')
let timer = null

// Init form from props
watch(() => props.prefs, (newVal) => {
  if (newVal && Object.keys(newVal).length > 0) {
    form.value = { ...form.value, ...newVal }
  }
}, { immediate: true })

function debouncedSave() {
  saveMsg.value = '正在保存...'
  clearTimeout(timer)
  timer = setTimeout(() => {
    emit('update-prefs', { ...form.value }, (err) => {
      if (err) saveMsg.value = '保存失败: ' + err
      else {
        saveMsg.value = '已自动保存'
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
  max-width: 400px;
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
  text-align: right; margin-top: -10px;
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
