<template>
  <div class="min-h-full bg-slate-50/40 p-6 md:p-10">
    <div class="max-w-5xl mx-auto space-y-6">
      <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 class="text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-3">
            <span class="p-2 bg-blue-600 rounded-2xl shadow-lg shadow-blue-200 text-white">👥</span>
            人员管理 <span class="text-slate-400 font-light text-xl ml-1">Admin Users</span>
          </h2>
          <p class="text-slate-500 mt-2">管理员可以授予或取消其他用户的后台管理权限。</p>
        </div>
        <button
          class="px-4 py-2 rounded-xl bg-white border border-slate-200 text-sm font-bold text-slate-600 hover:bg-slate-50"
          @click="loadUsers"
        >
          刷新
        </button>
      </div>

      <div class="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
        <div class="grid grid-cols-[1fr_160px_180px] gap-4 px-6 py-4 bg-slate-50 text-xs font-bold text-slate-400 uppercase tracking-wider">
          <div>用户</div>
          <div>角色</div>
          <div class="text-right">操作</div>
        </div>

        <div v-if="loading" class="p-10 text-center text-slate-400 font-medium">正在加载用户...</div>
        <div v-else-if="users.length === 0" class="p-10 text-center text-slate-400 font-medium">暂无用户</div>

        <template v-else>
          <div
            v-for="user in users"
            :key="user.id"
            class="grid grid-cols-[1fr_160px_180px] gap-4 px-6 py-4 border-t border-slate-100 items-center"
          >
            <div class="min-w-0">
              <div class="font-bold text-slate-800 truncate">{{ user.username }}</div>
              <div class="text-xs text-slate-400 mt-1">{{ formatDate(user.created_at) }}</div>
            </div>

            <div>
              <span
                class="inline-flex px-2.5 py-1 rounded-lg text-xs font-bold"
                :class="user.is_admin ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'"
              >
                {{ user.is_admin ? '管理员' : '普通用户' }}
              </span>
            </div>

            <div class="text-right">
              <button
                class="px-4 py-2 rounded-xl text-xs font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                :class="user.is_admin ? 'bg-red-50 text-red-600 hover:bg-red-100' : 'bg-blue-600 text-white hover:bg-blue-700'"
                :disabled="updatingId === user.id"
                @click="toggleAdmin(user)"
              >
                {{ user.is_admin ? '取消管理员' : '设为管理员' }}
              </button>
            </div>
          </div>
        </template>
      </div>

      <p v-if="errorMessage" class="text-sm font-semibold text-red-500">{{ errorMessage }}</p>
      <p v-if="successMessage" class="text-sm font-semibold text-emerald-600">{{ successMessage }}</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getAdminUsers, setAdminUserRole } from './api.js'

const users = ref([])
const loading = ref(false)
const updatingId = ref('')
const errorMessage = ref('')
const successMessage = ref('')

onMounted(() => {
  loadUsers()
})

async function loadUsers() {
  loading.value = true
  errorMessage.value = ''
  try {
    users.value = await getAdminUsers()
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || error.message || '加载用户失败'
  } finally {
    loading.value = false
  }
}

async function toggleAdmin(user) {
  updatingId.value = user.id
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const updated = await setAdminUserRole(user.id, !user.is_admin)
    const index = users.value.findIndex(item => item.id === updated.id)
    if (index !== -1) users.value[index] = updated
    successMessage.value = updated.is_admin ? `已将 ${updated.username} 设为管理员` : `已取消 ${updated.username} 的管理员权限`
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || error.message || '更新权限失败'
  } finally {
    updatingId.value = ''
  }
}

function formatDate(value) {
  if (!value) return '创建时间未知'
  return new Date(value).toLocaleString()
}
</script>
