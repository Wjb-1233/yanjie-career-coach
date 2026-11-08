<script setup lang="ts">
import { Star } from 'lucide-vue-next'

import type { Scene } from '@/lib/types'
import { difficultyTone } from '@/lib/sceneTaxonomy'

defineProps<{ scene: Scene }>()
const emit = defineEmits<{ start: [scene: Scene, mode: 'text' | 'voice' | 'video' | 'drill']; favorite: [scene: Scene] }>()
</script>

<template>
  <article class="scene-card">
    <div class="top">
      <span class="cat">{{ scene.category }}</span>
      <button class="favorite" type="button" :aria-label="scene.favorite ? '取消收藏' : '收藏场景'" @click="emit('favorite', scene)">
        <Star :size="16" :fill="scene.favorite ? 'currentColor' : 'none'" :stroke-width="1.7" aria-hidden="true" />
      </button>
    </div>

    <h3>{{ scene.title }}</h3>
    <p class="meta">{{ scene.industry }} · {{ scene.position }}</p>
    <p class="role">AI 面试官 · {{ scene.roleName }}</p>
    <p class="bg">{{ scene.background }}</p>

    <div class="bottom">
      <span class="diff" :class="difficultyTone(scene.difficulty)">{{ scene.difficulty }}</span>
      <div class="actions">
        <button type="button" @click="emit('start', scene, 'text')">文字</button>
        <button type="button" @click="emit('start', scene, 'voice')">语音</button>
        <button type="button" @click="emit('start', scene, 'video')">视频</button>
        <button v-if="scene.difficulty === '进阶'" type="button" @click="emit('start', scene, 'drill')">深挖</button>
      </div>
    </div>
  </article>
</template>

<style scoped>
.scene-card { display: flex; flex-direction: column; gap: 8px; padding: 20px; border: 1px solid var(--border); border-radius: 14px; background: var(--card); transition: border-color .16s var(--ease); }
.scene-card:hover { border-color: var(--border-bright); }
.top { display: flex; align-items: center; justify-content: space-between; }
.cat { color: var(--text-3); font-size: 12.5px; }
.favorite { border: 0; background: transparent; color: var(--text-3); padding: 2px; cursor: pointer; }
.favorite:hover { color: var(--accent-strong); }
h3 { margin: 4px 0 0; font-size: 18px; font-weight: 600; line-height: 1.45; color: var(--text); }
.meta { margin: 0; color: var(--text-2); font-size: 13px; }
.role { margin: 0; color: var(--text-3); font-size: 12.5px; }
.bg { margin: 6px 0 0; color: var(--text-3); font-size: 13.5px; line-height: 1.75; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.bottom { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--divider); }
.diff { font-size: 12.5px; color: var(--text-3); }
.diff.easy { color: var(--success); }
.diff.hard { color: var(--danger); }
.actions { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.actions button { border: 1px solid var(--border); background: transparent; color: var(--text-2); border-radius: 999px; padding: 5px 12px; font-size: 12.5px; cursor: pointer; transition: color .14s var(--ease), border-color .14s var(--ease), background .14s var(--ease); }
.actions button:hover { color: var(--text); border-color: var(--border-bright); background: var(--bg-2); }
</style>
