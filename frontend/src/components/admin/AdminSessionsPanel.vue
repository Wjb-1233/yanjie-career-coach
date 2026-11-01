<script setup lang="ts">
import type { AdminLearnerRow } from '@/lib/types'

defineProps<{ learners: AdminLearnerRow[]; loading: boolean }>()
const emit = defineEmits<{ export: []; report: [userId: string] }>()
</script>

<template>
  <section class="panel table-panel"><header><div><p class="eyebrow">训练与报告</p><h2>学员训练概览</h2><p class="panel-hint">一个学员一行；点任意一行打开他的五维评分、趋势与逐轮批注。</p></div><button class="button" @click="emit('export')">导出全部训练报告</button></header>
    <div v-if="loading" class="loading">正在读取学员数据…</div>
    <div v-else class="table-wrap"><table><thead><tr><th>学员</th><th>邮箱</th><th>训练场次</th><th>已完成</th><th>平均分</th><th>最近训练</th><th>状态</th><th>报告</th></tr></thead><tbody>
      <tr
        v-for="item in learners"
        :key="item.userId"
        class="row"
        role="button"
        tabindex="0"
        :aria-label="`查看 ${item.name} 的学员报告`"
        @click="emit('report', item.userId)"
        @keydown.enter.prevent="emit('report', item.userId)"
        @keydown.space.prevent="emit('report', item.userId)"
      >
        <td>{{ item.name }}</td>
        <td>{{ item.email }}</td>
        <td class="num">{{ item.sessions }}</td>
        <td class="num">{{ item.finished }}</td>
        <td class="num">{{ item.averageScore ?? '—' }}</td>
        <td>{{ item.lastTrainedAt ? new Date(item.lastTrainedAt).toLocaleString('zh-CN') : '还没训练' }}</td>
        <td><span class="state" :class="{ off: !item.active }">{{ item.active ? '启用' : '停用' }}</span></td>
        <td><button class="text-button" type="button" @click.stop="emit('report', item.userId)">查看报告</button></td>
      </tr>
    </tbody></table><p v-if="!learners.length" class="empty">目前还没有学员。</p></div>
  </section>
</template>

<style scoped>
.table-panel{overflow:hidden}header{padding:26px 24px 20px;display:flex;align-items:flex-start;justify-content:space-between;gap:16px}h2{margin:0;font:600 22px var(--font-ui);line-height:1.3}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:12px 14px;border-top:1px solid var(--line);text-align:left;font-size:12px;white-space:nowrap}th{color:var(--ink-soft);background:var(--bg-2)}.text-button{border:0;background:none;color:var(--mint-dark);cursor:pointer;font-weight:700}.loading,.empty{padding:26px;color:var(--ink-soft)}
.panel-hint{margin:8px 0 0;color:var(--text-3);font-size:12px}
.state{padding:2px 8px;border:1px solid var(--border);border-radius:4px;color:var(--text-2);font-size:11px}
.state.off{border-color:rgba(248,113,113,.3);color:#cf9a92}
tbody tr.row{cursor:pointer;transition:background .14s var(--ease)}
tbody tr.row:hover{background:var(--overlay-2)}
tbody tr.row:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
th { background:var(--overlay-1); }
.text-button { color:var(--text-2); }
</style>
