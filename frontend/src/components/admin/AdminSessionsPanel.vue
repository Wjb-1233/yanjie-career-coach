<script setup lang="ts">
import type { AdminSessionRecord } from '@/lib/types'

defineProps<{ sessions: AdminSessionRecord[]; loading: boolean }>()
const emit = defineEmits<{ export: []; report: [userId: string] }>()
</script>

<template>
  <section class="panel table-panel"><header><div><p class="eyebrow">训练与报告</p><h2>训练记录与学员报告</h2></div><button class="button" @click="emit('export')">导出全部训练报告</button></header>
    <div v-if="loading" class="loading">正在读取训练记录…</div>
    <div v-else class="table-wrap"><table><thead><tr><th>学员</th><th>邮箱</th><th>面试场景</th><th>状态</th><th>轮次</th><th>评分</th><th>时间</th><th>报告</th></tr></thead><tbody>
      <tr v-for="item in sessions" :key="item.id"><td>{{ item.userName }}</td><td>{{ item.email }}</td><td>{{ item.sceneTitle }}</td><td>{{ item.status === 'FINISHED' ? '已完成' : '进行中' }}</td><td>{{ item.rounds }}</td><td>{{ item.overallScore ?? '—' }}</td><td>{{ new Date(item.startedAt).toLocaleString('zh-CN') }}</td><td><button class="text-button" @click="emit('report', item.userId)">查看学员报告</button></td></tr>
    </tbody></table><p v-if="!sessions.length" class="empty">目前没有训练记录。</p></div>
  </section>
</template>

<style scoped>
.table-panel{overflow:hidden}header{padding:22px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px}h2{margin:0;font:700 22px var(--font-ui)}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:12px 14px;border-top:1px solid var(--line);text-align:left;font-size:12px;white-space:nowrap}th{color:var(--ink-soft);background:var(--bg-2)}.text-button{border:0;background:none;color:var(--mint-dark);cursor:pointer;font-weight:700}.loading,.empty{padding:26px;color:var(--ink-soft)}
th { background:var(--overlay-1); }
.text-button { color:var(--text-2); }
</style>
