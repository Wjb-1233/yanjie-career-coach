<script setup lang="ts">
import type { AdminUserRecord } from '@/lib/types'

const props = defineProps<{ users: AdminUserRecord[]; busyId: string; requests?: Array<{ id: string; name: string; email: string; createdAt: string | null }> }>()
const emit = defineEmits<{
  update: [user: AdminUserRecord, patch: { active?: boolean }]
  reset: [user: AdminUserRecord]
  resolveRequest: [item: { id: string; name: string }]
  dismissRequest: [item: { id: string }]
}>()

const students = () => props.users.filter((user) => user.role !== 'ADMIN')
</script>

<template>
  <section class="panel table-panel">
    <header>
      <div>
        <p class="eyebrow">学员账号</p>
        <h2>学员名单</h2>
        <p class="panel-hint">学员自行注册后自动出现在这里；管理员账号唯一，不在此管理。</p>
      </div>
      <span>{{ students().length }} 位学员</span>
    </header>
    <div v-if="props.requests && props.requests.length" class="requests-block">
      <p class="requests-title">待处理的密码重置申请（{{ props.requests.length }}）</p>
      <div v-for="item in props.requests" :key="item.id" class="request-row">
        <span class="request-name">{{ item.name }}</span>
        <span class="request-email">{{ item.email }}</span>
        <button class="button compact" type="button" :disabled="busyId === item.id" @click="emit('resolveRequest', item)">重置并生成临时密码</button>
        <button class="text-btn" type="button" :disabled="busyId === item.id" @click="emit('dismissRequest', item)">忽略</button>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>学员</th><th>邮箱</th><th>加入时间</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="user in students()" :key="user.id">
            <td>{{ user.displayName }}</td>
            <td>{{ user.email }}</td>
            <td>{{ new Date(user.createdAt).toLocaleDateString('zh-CN') }}</td>
            <td><span class="tag" :class="{ inactive: !user.active }">{{ user.active ? '启用' : '已停用' }}</span></td>
            <td class="actions">
              <button class="button secondary compact" :disabled="busyId === user.id" @click="emit('update', user, { active: !user.active })">
                {{ user.active ? '停用账号' : '恢复账号' }}
              </button>
              <button class="text-btn" type="button" :disabled="busyId === user.id" @click="emit('reset', user)">重置密码</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!students().length" class="empty">还没有学员注册。</p>
    </div>
  </section>
</template>

<style scoped>
.table-panel { overflow: hidden; }
header { padding: 24px 24px 18px; display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
h2 { margin:0; font:600 22px var(--font-ui); }
.panel-hint { margin: 8px 0 0; color: var(--text-3); font-size: 12px; }
header > span { color:var(--text-3); font-size:12px; white-space: nowrap; padding-top: 6px; }
.table-wrap { overflow:auto; }
table { width:100%; border-collapse:collapse; }
th,td { padding:12px 18px; border-top:1px solid var(--divider); text-align:left; font-size:12px; white-space:nowrap; }
th { color:var(--text-3); background:var(--bg-2); }
tbody tr:hover { background: var(--overlay-1); }
.actions { display: flex; align-items: center; gap: 12px; }
.text-btn { padding: 0; border: 0; background: none; color: var(--text-3); font-size: 12px; cursor: pointer; }
.text-btn:hover { color: var(--text); }
.compact { min-height:32px; padding:5px 9px; font-size:12px; }
.empty { padding: 26px; color: var(--text-3); }
.tag { padding: 2px 8px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-2); font-size: 11px; }
.inactive { color:#cf9a92; border-color: rgba(248,113,113,.3); background:rgba(248,113,113,.1); }
.requests-block { margin: 0 24px 16px; padding: 14px 16px; border: 1px solid rgba(201,138,86,.35); border-radius: 12px; background: rgba(201,138,86,.08); display: grid; gap: 10px; }
.requests-title { margin: 0; color: var(--accent-strong); font-size: 12px; letter-spacing: .06em; }
.request-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.request-name { color: var(--text); font-size: 13px; }
.request-email { color: var(--text-3); font-size: 12px; }
</style>
