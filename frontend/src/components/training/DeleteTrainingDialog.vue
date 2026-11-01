<script setup lang="ts">
import { onMounted, useTemplateRef } from 'vue'

const props = defineProps<{
  sceneTitle: string
  currentRound: number
  maxRounds: number
  busy: boolean
  error: string
}>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
const dialog = useTemplateRef<HTMLDialogElement>('dialog')

onMounted(() => dialog.value?.showModal())

function cancel(): void {
  if (!props.busy) emit('cancel')
}

function backdropClick(event: MouseEvent): void {
  if (event.target === event.currentTarget) cancel()
}
</script>

<template>
  <dialog ref="dialog" class="delete-dialog" aria-labelledby="delete-title" aria-describedby="delete-description" @cancel.prevent="cancel" @click="backdropClick">
    <p class="eyebrow">删除确认</p>
    <h2 id="delete-title">彻底删除这条训练记录？</h2>
    <p id="delete-description" class="description">
      「{{ sceneTitle }}」已完成 {{ currentRound }} / {{ maxRounds }} 轮。删除后，对话、评分报告和由这次评分生成的训练计划会一并移除；其他计划若引用了这次训练，相关进度会重置。此操作无法恢复。
    </p>
    <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
    <div class="actions">
      <button class="button secondary" type="button" :disabled="busy" @click="cancel">保留记录</button>
      <button class="button danger" type="button" :disabled="busy" @click="emit('confirm')">{{ busy ? '正在删除…' : '确认彻底删除' }}</button>
    </div>
  </dialog>
</template>

<style scoped>
.delete-dialog { width: min(440px, calc(100vw - 32px)); padding: 28px; border: 1px solid var(--border); border-radius:var(--radius); background:var(--card); color: var(--ink); box-shadow: 0 24px 70px rgba(16, 37, 43, .25); }
.delete-dialog::backdrop { background: rgba(9, 28, 32, .6); }
.delete-dialog h2 { margin: 8px 0 12px; font: 700 25px/1.25 var(--font-ui); }
.description { margin: 0; color: var(--ink-soft); font-size: 14px; line-height: 1.8; }
.dialog-error { margin: 16px 0 0; color: #a63828; font-size: 13px; }
.actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; margin-top: 26px; }
.danger { background: var(--danger); color: white; }
.danger:hover { background: var(--danger); }
.delete-dialog { border-color:var(--border);background:var(--card);color:var(--text);box-shadow:var(--shadow);backdrop-filter:none;animation:dialog-in .2s ease both; }
.delete-dialog::backdrop { background:rgba(3,7,18,.76);backdrop-filter:none; }
.dialog-error { color:#cf9a92; }
.danger { background:var(--danger); }
.danger:hover { background:var(--accent-strong); }
@keyframes dialog-in { from { opacity:0;transform:scale(.94) translateY(12px); } to { opacity:1;transform:scale(1) translateY(0); } }
@media (prefers-reduced-motion:reduce) { .delete-dialog { animation:none; } }
</style>
