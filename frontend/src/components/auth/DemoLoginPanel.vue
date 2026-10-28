<script setup lang="ts">
interface Props {
  loading: boolean
}

interface Emits {
  select: [role: 'STUDENT' | 'ADMIN']
}

defineProps<Props>()
const emit = defineEmits<Emits>()
</script>

<template>
  <div class="demo-login" aria-label="演示账号快速登录">
    <div class="divider"><span>本机演示快捷入口</span></div>
    <div class="demo-actions">
      <button type="button" class="demo-button student" :disabled="loading" @click="emit('select', 'STUDENT')">
        <span class="role-icon" aria-hidden="true">学</span>
        <span>一键登录用户<small>体验训练与报告</small></span>
      </button>
      <button type="button" class="demo-button admin" :disabled="loading" @click="emit('select', 'ADMIN')">
        <span class="role-icon" aria-hidden="true">管</span>
        <span>一键登录管理员<small>查看管理后台</small></span>
      </button>
    </div>
    <p class="demo-note">仅本机开发演示可用，正式部署时不会开放此入口。</p>
  </div>
</template>

<style scoped>
.demo-login { width: 100%; margin-top: 24px; }
.divider { display: flex; align-items: center; gap: 12px; color: var(--ink-soft); font-size: 12px; white-space: nowrap; }
.divider::before, .divider::after { content: ''; height: 1px; flex: 1; background: var(--line); }
.demo-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
.demo-button { display: flex; align-items: center; gap: 9px; min-height: 67px; padding: 10px; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); color: var(--ink); text-align: left; font-size: 12px; font-weight: 800; cursor: pointer; transition: border-color .18s, transform .18s, box-shadow .18s; }
.demo-button:hover:not(:disabled) { transform: translateY(-2px); border-color: var(--mint); box-shadow: 0 8px 20px rgba(16, 37, 43, .07); }
.demo-button:focus-visible { outline: 3px solid var(--mint); outline-offset: 2px; }
.demo-button:disabled { opacity: .55; cursor: wait; }
.role-icon { flex: none; display: grid; width: 34px; height: 34px; place-items: center; border-radius:var(--radius-sm); background: var(--primary-soft); color: var(--primary); font-size: 14px; }
.admin .role-icon { background: #eef2ff; color: #4f46e5; }
.demo-button small { display: block; margin-top: 3px; color: var(--ink-soft); font-size: 10px; font-weight: 500; }
.demo-note { margin: 11px 0 0; color: var(--ink-soft); font-size: 10px; line-height: 1.6; text-align: center; }
.demo-button { border-color:var(--border);background:var(--glass);color:var(--text);transition:transform var(--ease),border-color var(--ease),box-shadow var(--ease); }
.demo-button:hover:not(:disabled) { border-color:var(--text-3);box-shadow:none; }
.role-icon { background:var(--bg-2);color:var(--text-2); }
.admin .role-icon { background:var(--bg-2);color:var(--text-2); }
@media (max-width: 420px) { .demo-actions { grid-template-columns: 1fr; } }
</style>
