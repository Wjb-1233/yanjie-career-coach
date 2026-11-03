<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    title: string
    description?: string
    compact?: boolean
    eyebrow?: string
    steps?: Array<{ title: string; detail?: string }>
    actionLabel?: string
    actionTo?: string | Record<string, string>
  }>(),
  { description: '', compact: false, eyebrow: '', steps: () => [], actionLabel: '', actionTo: '' },
)
</script>

<template>
  <section class="empty-state" :class="{ compact, guided: steps.length > 0 }">
    <div class="empty-main">
      <svg v-if="!steps.length" viewBox="0 0 120 96" aria-hidden="true" class="empty-art">
        <rect x="18" y="20" width="84" height="58" rx="8" fill="none" stroke="currentColor" stroke-width="1.2" opacity=".45" />
        <path d="M30 34h44M30 46h60M30 58h36" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity=".3" />
        <circle cx="92" cy="28" r="13" fill="none" stroke="currentColor" stroke-width="1.2" opacity=".55" />
        <path d="M92 22v7l4 3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity=".55" />
        <path d="M14 84h92" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity=".2" />
      </svg>

      <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
      <p class="empty-title" :class="{ display: steps.length > 0 }">{{ title }}</p>
      <p v-if="description" class="empty-desc">{{ description }}</p>
      <RouterLink v-if="actionLabel && actionTo" class="button" :to="actionTo">
        {{ actionLabel }}
        <ArrowRight :size="14" :stroke-width="1.8" aria-hidden="true" />
      </RouterLink>
      <slot />
    </div>

    <ol v-if="steps.length" class="empty-steps">
      <li v-for="(step, index) in steps" :key="step.title">
        <span class="step-no num">{{ String(index + 1).padStart(2, '0') }}</span>
        <div>
          <strong>{{ step.title }}</strong>
          <p v-if="step.detail">{{ step.detail }}</p>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.empty-state {
  display: grid;
  justify-items: center;
  gap: 6px;
  padding: 44px 24px;
  border: 1px dashed var(--border-bright);
  border-radius: var(--radius);
  color: var(--text-3);
  text-align: center;
}
.empty-state.compact { padding: 26px 18px; }
.empty-main { display: grid; justify-items: center; gap: 8px; }
.empty-art { width: 120px; height: 96px; margin-bottom: 6px; color: var(--text-3); }
.empty-title { margin: 0; color: var(--text-2); font-size: 13.5px; }
.empty-desc { margin: 0; max-width: 52ch; color: var(--text-3); font-size: 12.5px; line-height: 1.9; }

/* 引导态：两栏，左文案右步骤 */
.empty-state.guided {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
  justify-items: start;
  gap: 34px;
  padding: 30px 32px;
  border: 1px solid var(--border);
  border-style: solid;
  background: var(--card);
  text-align: left;
}
.empty-state.guided .empty-main { justify-items: start; align-content: start; }
.empty-state.guided .empty-title.display {
  font-family: var(--font-display);
  font-size: clamp(20px, 2vw, 24px);
  font-weight: 600;
  line-height: 1.45;
  color: var(--text);
}
.empty-state.guided .empty-desc { max-width: 400px; }
.empty-state.guided .button { margin-top: 6px; }
.empty-steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; align-content: start; width: 100%; }
.empty-steps li { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 12px; align-items: start; }
.step-no { padding-top: 2px; color: var(--accent); font-size: 12px; font-variant-numeric: tabular-nums; }
.empty-steps strong { display: block; color: var(--text); font-size: 13px; font-weight: 600; }
.empty-steps p { margin: 3px 0 0; color: var(--text-3); font-size: 12.5px; line-height: 1.75; }

@media (max-width: 860px) {
  .empty-state.guided { grid-template-columns: 1fr; gap: 24px; padding: 24px; }
}
</style>
