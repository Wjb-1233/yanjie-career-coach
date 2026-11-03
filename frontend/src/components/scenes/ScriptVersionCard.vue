<script setup lang="ts">
import { computed } from 'vue'

import { diffChars, diffStats } from '@/lib/diff'
import { scriptPresentation } from '@/lib/scriptPresentation'
import type { ScriptVersion } from '@/lib/types'

const props = defineProps<{ version: ScriptVersion; sceneTitle?: string; showActions?: boolean; allowDelete?: boolean }>()
const emit = defineEmits<{ favorite: [version: ScriptVersion]; remove: [version: ScriptVersion]; preview: [version: ScriptVersion] }>()
const presentation = computed(() => scriptPresentation(props.version.style))
const segments = computed(() =>
  props.version.original?.trim() ? diffChars(props.version.original, props.version.content) : null)
const stats = computed(() => (segments.value ? diffStats(segments.value) : null))
const hasDiff = computed(() => segments.value?.some((segment) => segment.type !== 'same') ?? false)
</script>

<template>
  <article class="version-card" :class="presentation.tone">
    <div class="version-meta">
      <span class="style-badge">{{ presentation.label }}</span>
      <span v-if="sceneTitle" class="scene-title">{{ sceneTitle }}</span>
      <time v-if="version.createdAt">{{ new Date(version.createdAt).toLocaleString('zh-CN') }}</time>
    </div>
    <p class="purpose">{{ presentation.purpose }}</p>
    <p class="content">{{ version.content }}</p>
    <details v-if="hasDiff" class="diff-detail">
      <summary>与你的原话逐字对比 · 新增 {{ stats?.added ?? 0 }} 字 / 删去 {{ stats?.removed ?? 0 }} 字</summary>
      <p class="diff-text">
        <template v-for="(segment, index) in segments" :key="index">
          <span v-if="segment.type === 'add'" class="diff-add">{{ segment.text }}</span>
          <del v-else-if="segment.type === 'del'" class="diff-del">{{ segment.text }}</del>
          <template v-else>{{ segment.text }}</template>
        </template>
      </p>
      <p class="diff-legend"><span class="diff-add">新增或改写</span><del class="diff-del">原话删去</del></p>
    </details>
    <div v-if="version.highlights.length" class="highlights" aria-label="版本特点">
      <span v-for="point in version.highlights" :key="point">{{ point }}</span>
    </div>
    <div v-if="showActions" class="actions">
      <button type="button" @click="emit('preview', version)">▶ 试听</button>
      <button type="button" @click="emit('favorite', version)">{{ version.favorite ? '★ 已收藏' : '☆ 收藏' }}</button>
      <button v-if="allowDelete" type="button" class="danger" @click="emit('remove', version)">删除</button>
    </div>
  </article>
</template>

<style scoped>
.version-card { --tone-ink:var(--text-2); --tone-bg:var(--overlay-2); padding:20px; border:1px solid var(--border); border-radius:var(--radius); background:var(--card); transition:border-color var(--ease); }
.version-card:hover { border-color:var(--border-bright); }
.version-card.concise { --tone-ink:var(--text-2); --tone-bg:var(--overlay-1); }
.version-card.warm { --tone-ink:var(--text); --tone-bg:var(--overlay-3); }
.version-card.review { --tone-ink:var(--text-3); --tone-bg:var(--overlay-1); }
.version-meta { display:flex;align-items:center;flex-wrap:wrap;gap:9px;color:var(--text-2);font-size:12px; }
.style-badge { padding:5px 10px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--tone-bg); color:var(--tone-ink); font-weight:650; }
.version-meta time { margin-left:auto; }
.purpose { margin:14px 0 0; color:var(--text-3); font-size:12px; line-height:1.55; }
.content { margin: 15px 0; color: var(--text); line-height: 1.75; white-space: pre-wrap; overflow-wrap: anywhere; }
.highlights { display:flex;flex-wrap:wrap;gap:7px; }
.highlights span { padding:4px 8px; border-radius:6px; background:var(--tone-bg); color:var(--tone-ink); font-size:11px; }
.actions { display:flex;gap:16px;margin-top:18px; }
.actions button { padding:0;border:0;background:transparent;color:var(--text-2);font-weight:650;cursor:pointer; }
.actions .danger { color:#cf9a92; }

.diff-detail { margin-top: 12px; }
.diff-detail summary { color: var(--text-3); font-size: 11px; letter-spacing: .06em; cursor: pointer; }
.diff-detail summary:hover { color: var(--text-2); }
.diff-text { margin: 10px 0 0; padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-2); color: var(--text); font-size: 13px; line-height: 2; }
.diff-add { padding: 1px 2px; border-radius: 2px; background: var(--accent-soft); color: var(--accent-strong); }
.diff-del { padding: 1px 2px; color: var(--danger); text-decoration: line-through; text-decoration-thickness: 1px; }
.diff-legend { display: flex; gap: 16px; margin: 8px 0 0; color: var(--text-3); font-size: 11px; }
.diff-legend .diff-add, .diff-legend .diff-del { font-size: 11px; }
</style>
