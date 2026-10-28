<script setup lang="ts">
import type { AdminUserRecord } from '@/lib/types'

defineProps<{ users: AdminUserRecord[]; busyId: string }>()
const emit = defineEmits<{ update: [user: AdminUserRecord, patch: { role?: 'STUDENT' | 'ADMIN'; active?: boolean }] }>()
</script>

<template>
  <section class="panel table-panel">
    <header><div><p class="eyebrow">用户目录</p><h2>账号与角色</h2></div><span>{{ users.length }} 位学员/管理员</span></header>
    <div class="table-wrap"><table><thead><tr><th>用户</th><th>邮箱</th><th>角色</th><th>状态</th><th>加入时间</th><th>操作</th></tr></thead>
      <tbody><tr v-for="user in users" :key="user.id"><td>{{ user.displayName }}</td><td>{{ user.email }}</td>
        <td><select class="field compact" :value="user.role" :disabled="busyId === user.id" @change="emit('update', user, { role: ($event.target as HTMLSelectElement).value as 'STUDENT' | 'ADMIN' })"><option value="STUDENT">学员</option><option value="ADMIN">管理员</option></select></td>
        <td><span class="tag" :class="{ inactive: !user.active }">{{ user.active ? '启用' : '已停用' }}</span></td>
        <td>{{ new Date(user.createdAt).toLocaleDateString('zh-CN') }}</td>
        <td><button class="button secondary compact" :disabled="busyId === user.id" @click="emit('update', user, { active: !user.active })">{{ user.active ? '停用账号' : '恢复账号' }}</button></td>
      </tr></tbody>
    </table></div>
  </section>
</template>

<style scoped>
.table-panel { overflow: hidden; } header { padding: 22px 24px 14px; display:flex; justify-content:space-between; align-items:center; gap:12px; } h2 { margin:0; font:700 22px var(--font-ui); } header > span { color:var(--ink-soft); font-size:12px; } .table-wrap { overflow:auto; } table { width:100%; border-collapse:collapse; } th,td { padding:12px 18px; border-top:1px solid var(--line); text-align:left; font-size:12px; white-space:nowrap; } th { color:var(--ink-soft); background:var(--bg-2); } .compact { min-height:34px; padding:5px 9px; font-size:12px; } .inactive { color:var(--danger); background:rgba(192,127,117,.12); }
th { background:var(--overlay-1); }
.inactive { color:#cf9a92;background:rgba(248,113,113,.1); }
</style>
