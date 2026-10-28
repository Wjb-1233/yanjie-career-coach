<script setup lang="ts">
import { computed } from 'vue'

import { scriptPresentation } from '@/lib/scriptPresentation'
import type { ScriptVersion } from '@/lib/types'

const props = defineProps<{ version: ScriptVersion; sceneTitle?: string; showActions?: boolean; allowDelete?: boolean }>()
const emit = defineEmits<{ favorite: [version: ScriptVersion]; remove: [version: ScriptVersion] }>()
const presentation = computed(() => scriptPresentation(props.version.style))
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
    <div v-if="version.highlights.length" class="highlights" aria-label="版本特点">
      <span v-for="point in version.highlights" :key="point">{{ point }}</span>
    </div>
    <div v-if="showActions" class="actions">
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
</style>
