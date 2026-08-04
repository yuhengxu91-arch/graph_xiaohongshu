<template>
  <div class="poster-panel">
    <div class="card">
      <div class="card-header-row">
        <div class="card-title">上传图片以进行编辑</div>
        <ModelSwitcher
          v-model="selectedModelOverride"
          :currentImageModel="currentImageModel"
        />
      </div>

      <!-- 图片上传 -->
      <ImageUploader v-model="form.imageBase64" />

      <!-- 编辑指令输入 -->
      <div class="form-group" style="margin-top: 20px;">
        <label>编辑指令 <span class="label-hint">（必填）</span></label>
        <textarea
          v-model="form.editPrompt"
          class="textarea poster-textarea"
          placeholder="例如：把背景换成星空、消除照片里的人物、给主角戴上墨镜..."
          rows="3"
        ></textarea>
      </div>

      <!-- 尺寸选择 -->
      <div class="form-group">
        <label>输出尺寸</label>
        <RatioSelector v-model="form.aspectRatio" :ratios="aspectRatios" />
      </div>

      <!-- 生成按钮 -->
      <button
        class="btn btn-primary poster-generate-btn"
        :disabled="!isValid || generating"
        @click="handleGenerate"
      >
        {{ generating ? '🎨 生成中...' : '🚀 开始修改' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import ImageUploader from './ImageUploader.vue'
import RatioSelector from './RatioSelector.vue'
import ModelSwitcher from './ModelSwitcher.vue'

const props = defineProps({
  aspectRatios: { type: Array, default: () => [] },
  generating: { type: Boolean, default: false },
  currentImageModel: { type: Object, default: null },
})

const emit = defineEmits(['generate'])

const form = ref({
  imageBase64: '',
  editPrompt: '',
  aspectRatio: '3:4',
})

const selectedModelOverride = ref(null)

const isValid = computed(() => {
  return form.value.imageBase64 && form.value.editPrompt.trim()
})

function handleGenerate() {
  if (!isValid.value || props.generating) return
  emit('generate', {
    ...form.value,
    modelOverride: selectedModelOverride.value || undefined,
  })
}
</script>

<style scoped>
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}
</style>
