<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

interface TaskRow {
  id: string
  kind: string
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'
  progress: number
  stage: string | null
  error: string | null
  email: string
  createdAt: string
  updatedAt: string
}

const props = defineProps<{ tasks: TaskRow[]; loading: boolean }>()
const emit = defineEmits<{ refresh: [] }>()
const error = shallowRef('')
const busy = ref('')

const KIND_LABEL: Record<string, string> = { VIDEO_INTERVIEW: '视频面试分析' }
const STATUS_LABEL: Record<TaskRow['status'], string> = {
  PENDING: '排队中',
  RUNNING: '进行中',
  DONE: '已完成',
  FAILED: '失败',
}

const rows = computed(() =>
  [...props.tasks].sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1)),
)

function timeOf(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

async function retry(task: TaskRow): Promise<void> {
  busy.value = task.id
  error.value = ''
  try {
    await api.post<ApiEnvelope<{ id: string }>>(`/admin/tasks/${task.id}/retry`)
    emit('refresh')
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <section class="panel tasks-panel">
    <header class="tasks-head">
      <div>
        <h2>后台任务</h2>
        <p>视频分析这类长任务在后台排队执行，失败可以重跑。</p>
      </div>
      <button type="button" class="button secondary" @click="emit('refresh')">刷新</button>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <div v-if="loading" class="skeleton loading-line" />
    <p v-else-if="!rows.length" class="empty">还没有任务记录</p>

    <table v-else class="tasks-table">
      <thead>
        <tr><th>类型</th><th>学员</th><th>状态</th><th>进度</th><th>更新时间</th><th /></tr>
      </thead>
      <tbody>
        <tr v-for="task in rows" :key="task.id">
          <td>{{ KIND_LABEL[task.kind] ?? task.kind }}</td>
          <td class="email">{{ task.email }}</td>
          <td>
            <span class="chip" :class="task.status.toLowerCase()">{{ STATUS_LABEL[task.status] }}</span>
            <span v-if="task.error" class="err" :title="task.error">{{ task.error.slice(0, 18) }}</span>
          </td>
          <td class="progress">
            <i><b :style="{ width: `${task.progress}%` }" /></i>
            <span class="num">{{ task.progress }}%</span>
            <small v-if="task.stage">{{ task.stage }}</small>
          </td>
          <td class="num time">{{ timeOf(task.updatedAt) }}</td>
          <td>
            <button
              v-if="task.status === 'FAILED' || task.status === 'DONE'"
              type="button"
              class="link"
              :disabled="busy === task.id"
              @click="retry(task)"
            >{{ task.status === 'FAILED' ? '重跑' : '再跑一次' }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.tasks-panel { padding: 22px; }
.tasks-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.tasks-head h2 { margin: 0 0 6px; font-family: var(--font-display); font-size: 20px; }
.tasks-head p { margin: 0; color: var(--text-2); font-size: 12.5px; }
.empty { margin: 0; padding: 24px 0; color: var(--text-3); font-size: 13px; text-align: center; }
.tasks-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tasks-table th { padding: 10px 12px; border-bottom: 1px solid var(--line); color: var(--text-3); font-weight: 500; text-align: left; }
.tasks-table td { padding: 12px; border-bottom: 1px solid var(--line); color: var(--text-2); vertical-align: middle; }
.tasks-table tr:last-child td { border-bottom: 0; }
.email { max-width: 190px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chip { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11px; border: 1px solid var(--line); }
.chip.pending { color: #8a6d3b; border-color: #d8c39a; }
.chip.running { color: var(--accent-strong); border-color: var(--accent); }
.chip.done { color: #2f6b4f; border-color: #a8cdb8; }
.chip.failed { color: #a4342a; border-color: #d9a7a1; }
.err { margin-left: 6px; color: #a4342a; font-size: 11px; }
.progress { display: grid; grid-template-columns: 70px auto; align-items: center; gap: 8px; }
.progress i { position: relative; display: block; height: 3px; background: var(--track); border-radius: 999px; overflow: hidden; }
.progress i b { position: absolute; inset: 0 auto 0 0; background: var(--accent); border-radius: 999px; }
.progress small { grid-column: 1 / -1; color: var(--text-3); font-size: 11px; }
.time { color: var(--text-3); white-space: nowrap; }
.link { padding: 0; border: 0; background: none; color: var(--primary-hover); font-size: 12px; cursor: pointer; }
.link:disabled { opacity: .6; cursor: default; }
</style>
