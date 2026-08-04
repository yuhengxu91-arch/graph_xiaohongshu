<template>
  <div v-if="canManage" class="channel-panel">
    <div class="panel-header">
      <div class="header-left">
        <span class="header-icon">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
          </svg>
        </span>
        <div>
          <h3>模型通道状态</h3>
          <p class="header-desc">检测所有图片生成模型 API 的连通性与响应速度</p>
        </div>
      </div>
      <button
        class="test-all-btn"
        :disabled="testingAll"
        @click="testAllChannels"
      >
        <svg v-if="testingAll" class="spin-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        {{ testingAll ? `正在测试 (${testProgress}/${channels.length})` : '全部测试' }}
      </button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <span>正在加载模型通道列表...</span>
    </div>

    <!-- 通道卡片网格 -->
    <div v-else-if="channels.length" class="channel-grid">
      <div
        v-for="channel in channels"
        :key="channel.id"
        class="channel-card"
        :class="statusClass(channel)"
      >
        <div class="card-top">
          <div class="status-dot" :class="statusClass(channel)">
            <svg v-if="channelStatus[channel.id]?.testing" class="spin-icon-sm" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
          </div>
          <span class="source-badge" :class="channel.source">
            {{ channel.source === 'builtin' ? '内置' : '公共' }}
          </span>
        </div>

        <div class="card-body">
          <div class="channel-name">{{ channel.name }}</div>
          <div class="channel-meta">
            <span v-if="channel.provider_type" class="type-tag">{{ providerLabel(channel.provider_type) }}</span>
            <span v-else-if="channel.provider" class="type-tag">{{ providerTagLabel(channel.provider) }}</span>
          </div>
          <div v-if="channel.model_name" class="channel-model">{{ channel.model_name }}</div>
        </div>

        <div class="card-footer">
          <div class="status-info">
            <template v-if="channelStatus[channel.id]?.testing">
              <span class="status-text testing">测试中...</span>
            </template>
            <template v-else-if="channelStatus[channel.id]?.tested">
              <span v-if="channelStatus[channel.id].success" class="status-text success">
                ✓ 正常
                <span class="latency">{{ channelStatus[channel.id].latency_ms }}ms</span>
              </span>
              <span v-else class="status-text error" :title="channelStatus[channel.id].error">
                ✗ 异常
                <span class="latency">{{ channelStatus[channel.id].latency_ms }}ms</span>
              </span>
            </template>
            <template v-else>
              <span class="status-text idle">未测试</span>
            </template>
          </div>

          <button
            class="test-btn"
            :disabled="channelStatus[channel.id]?.testing || testingAll"
            @click="testSingleChannel(channel)"
          >
            {{ channelStatus[channel.id]?.testing ? '...' : '测试' }}
          </button>
        </div>

        <!-- 错误信息展开 -->
        <div
          v-if="channelStatus[channel.id]?.tested && !channelStatus[channel.id]?.success"
          class="error-detail"
        >
          <div class="error-content">{{ channelStatus[channel.id]?.error || '未知错误' }}</div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <p>暂无可用的模型通道</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getModelChannels, testModelChannel } from '../../api'

defineProps({
  canManage: {
    type: Boolean,
    default: false,
  },
})

const loading = ref(true)
const channels = ref([])
const channelStatus = reactive({})
const testingAll = ref(false)
const testProgress = ref(0)

onMounted(async () => {
  await loadChannels()
})

async function loadChannels() {
  loading.value = true
  try {
    const data = await getModelChannels()
    channels.value = data.channels || []
    // 初始化状态
    for (const ch of channels.value) {
      channelStatus[ch.id] = { tested: false, testing: false, success: false, latency_ms: 0, error: null }
    }
  } catch {
    channels.value = []
  } finally {
    loading.value = false
  }
}

async function testSingleChannel(channel) {
  channelStatus[channel.id] = { tested: false, testing: true, success: false, latency_ms: 0, error: null }
  try {
    const result = await testModelChannel(channel.id)
    channelStatus[channel.id] = {
      tested: true,
      testing: false,
      success: result.success,
      latency_ms: result.latency_ms,
      error: result.error,
    }
  } catch (err) {
    channelStatus[channel.id] = {
      tested: true,
      testing: false,
      success: false,
      latency_ms: 0,
      error: err.response?.data?.detail || err.message || '请求失败',
    }
  }
}

async function testAllChannels() {
  testingAll.value = true
  testProgress.value = 0
  for (const channel of channels.value) {
    await testSingleChannel(channel)
    testProgress.value++
  }
  testingAll.value = false
}

function providerLabel(type) {
  const map = {
    openai_image: 'OpenAI 兼容',
    gemini: 'Gemini',
    doubao: '豆包',
  }
  return map[type] || type
}

function providerTagLabel(provider) {
  const map = {
    gemini: 'Gemini',
    gemini_ch: 'Gemini CH',
    gpt_image: 'GPT Image',
    doubao: '豆包',
  }
  return map[provider] || provider
}

function statusClass(channel) {
  const st = channelStatus[channel.id]
  if (!st) return 'idle'
  if (st.testing) return 'testing'
  if (st.tested && st.success) return 'success'
  if (st.tested && !st.success) return 'error'
  return 'idle'
}
</script>

<style scoped>
.channel-panel {
  background: white;
  border-radius: 20px;
  padding: 28px 32px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 16px rgba(0, 0, 0, 0.03);
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  background: linear-gradient(135deg, #10b981, #059669);
  border-radius: 14px;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);
}

.header-icon .icon {
  width: 22px;
  height: 22px;
  color: white;
}

.panel-header h3 {
  font-size: 17px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.header-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 2px 0 0;
}

.test-all-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.test-all-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.4);
}

.test-all-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

/* 加载态 */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 0;
  color: #94a3b8;
  font-size: 14px;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* 卡片网格 */
.channel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.channel-card {
  position: relative;
  background: #f8fafc;
  border: 1.5px solid #e2e8f0;
  border-radius: 16px;
  padding: 18px 20px;
  transition: all 0.3s ease;
  overflow: hidden;
}

.channel-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  border-radius: 16px 16px 0 0;
  transition: background 0.3s ease;
}

.channel-card.idle::before {
  background: #cbd5e1;
}
.channel-card.testing::before {
  background: linear-gradient(90deg, #3b82f6, #8b5cf6, #3b82f6);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}
.channel-card.success {
  border-color: #86efac;
  background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
}
.channel-card.success::before {
  background: linear-gradient(90deg, #22c55e, #10b981);
}
.channel-card.error {
  border-color: #fca5a5;
  background: linear-gradient(180deg, #fef2f2 0%, #ffffff 100%);
}
.channel-card.error::before {
  background: linear-gradient(90deg, #ef4444, #dc2626);
}

.channel-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-dot.idle {
  background: #cbd5e1;
  box-shadow: 0 0 0 3px rgba(203, 213, 225, 0.3);
}
.status-dot.testing {
  background: transparent;
  width: 18px;
  height: 18px;
}
.status-dot.success {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.2), 0 0 8px rgba(34, 197, 94, 0.3);
}
.status-dot.error {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2), 0 0 8px rgba(239, 68, 68, 0.3);
}

.source-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  letter-spacing: 0.5px;
}
.source-badge.builtin {
  background: linear-gradient(135deg, #ede9fe, #ddd6fe);
  color: #7c3aed;
}
.source-badge.config {
  background: linear-gradient(135deg, #e0f2fe, #bae6fd);
  color: #0284c7;
}

.card-body {
  margin-bottom: 14px;
}

.channel-name {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 6px;
  line-height: 1.3;
}

.channel-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.type-tag {
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 6px;
}

.channel-model {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.status-info {
  flex: 1;
}

.status-text {
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.status-text.idle { color: #94a3b8; }
.status-text.testing { color: #3b82f6; }
.status-text.success { color: #16a34a; }
.status-text.error { color: #dc2626; }

.latency {
  font-size: 12px;
  font-weight: 500;
  color: #94a3b8;
  background: #f8fafc;
  padding: 1px 6px;
  border-radius: 4px;
}

.test-btn {
  padding: 6px 16px;
  background: white;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s ease;
}
.test-btn:hover:not(:disabled) {
  border-color: #3b82f6;
  color: #3b82f6;
  background: #f0f7ff;
}
.test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-detail {
  margin-top: 10px;
  padding: 10px 12px;
  background: #fef2f2;
  border-radius: 10px;
  border: 1px solid #fecaca;
}

.error-content {
  font-size: 12px;
  color: #991b1b;
  line-height: 1.5;
  word-break: break-all;
}

.empty-state {
  text-align: center;
  padding: 48px 0;
  color: #94a3b8;
  font-size: 14px;
}

/* 动画 */
@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.spin-icon {
  width: 18px;
  height: 18px;
  animation: spin 1s linear infinite;
}

.spin-icon-sm {
  width: 14px;
  height: 14px;
  color: #3b82f6;
  animation: spin 1s linear infinite;
}
</style>
