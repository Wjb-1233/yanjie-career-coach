<script setup lang="ts">
withDefaults(defineProps<{ title: string; description?: string; compact?: boolean }>(), { description: '', compact: false })
</script>

<template>
  <div class="empty-state" :class="{ compact }">
    <svg viewBox="0 0 120 96" aria-hidden="true" class="empty-art">
      <rect x="18" y="20" width="84" height="58" rx="8" fill="none" stroke="currentColor" stroke-width="1.2" opacity=".45" />
      <path d="M30 34h44M30 46h60M30 58h36" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity=".3" />
      <circle cx="92" cy="28" r="13" fill="none" stroke="currentColor" stroke-width="1.2" opacity=".55" />
      <path d="M92 22v7l4 3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity=".55" />
      <path d="M14 84h92" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity=".2" />
    </svg>
    <p class="empty-title">{{ title }}</p>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty-state { display: grid; justify-items: center; gap: 6px; padding: 44px 24px; border: 1px dashed var(--border-bright); border-radius: var(--radius); color: var(--text-3); text-align: center; }
.empty-state.compact { padding: 26px 18px; }
.empty-art { width: 120px; height: 96px; margin-bottom: 6px; color: var(--text-3); }
.empty-title { margin: 0; color: var(--text-2); font-size: 13.5px; }
.empty-desc { margin: 0; max-width: 52ch; color: var(--text-3); font-size: 12.5px; line-height: 1.9; }
</style>
