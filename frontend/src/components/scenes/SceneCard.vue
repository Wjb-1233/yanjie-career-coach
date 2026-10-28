<script setup lang="ts">
import type { Scene } from '@/lib/types'
import { difficultyCue, difficultyTone } from '@/lib/sceneTaxonomy'

defineProps<{ scene: Scene }>()
const emit = defineEmits<{ start: [scene: Scene, mode: 'text' | 'voice']; favorite: [scene: Scene] }>()
</script>

<template>
  <article class="scene-card">
    <div class="scene-topline">
      <span class="category">{{ scene.category }}</span>
      <button class="favorite" type="button" :aria-label="scene.favorite ? '取消收藏' : '收藏场景'" @click="emit('favorite', scene)">
        {{ scene.favorite ? '◆' : '◇' }}
      </button>
    </div>
    <div class="scene-main">
      <h3>{{ scene.title }}</h3>
      <p class="meta"><span>{{ scene.industry }}</span><span>{{ scene.position }}</span></p>
      <p class="role"><span class="role-dot" /> {{ scene.category === '基础能力提升' ? 'AI 练习对象' : 'AI 面试官' }} · {{ scene.roleName }}</p>
      <p class="background">{{ scene.background }}</p>
    </div>
    <div class="tags">
      <span class="tag difficulty" :class="difficultyTone(scene.difficulty)">{{ scene.difficulty }} · {{ difficultyCue(scene.difficulty) }}</span>
      <span v-for="tag in scene.tags.slice(0, 2)" :key="tag" class="tag">{{ tag }}</span>
    </div>
    <div class="card-actions">
      <RouterLink class="script" :to="{ name: 'scripts', query: { sceneId: scene.id } }">到话术优化中练习 →</RouterLink>
      <div class="start-actions">
        <button class="start text" type="button" @click="emit('start', scene, 'text')">文字对练 <span>→</span></button>
        <button class="start voice" type="button" @click="emit('start', scene, 'voice')">语音对练 <span>↗</span></button>
      </div>
    </div>
  </article>
</template>

<style scoped>
.scene-card { min-height: 332px; padding: 25px; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); box-shadow: 0 7px 22px rgba(16,37,43,.035); transition: transform .2s, box-shadow .2s, border-color .2s; }
.scene-card:hover { transform: translateY(-3px); border-color: #a8cdc5; box-shadow: 0 19px 42px rgba(16,37,43,.1); }
.scene-topline { display: flex; align-items: center; justify-content: space-between; }
.category { padding: 7px 10px; border-radius: 6px; background: var(--sky); color: var(--mint-dark); font-size: 12px; font-weight: 800; }
.favorite { width: 34px; height: 34px; border: 1px solid var(--line); border-radius: 50%; background:var(--card); color: var(--signal); cursor: pointer; }
.scene-main { flex: 1; }
h3 { margin: 21px 0 9px; font-family: var(--font-ui); font-size: 25px; line-height: 1.3; }
.meta { margin: 0 0 17px; display: flex; flex-wrap: wrap; gap: 8px; color: var(--ink-soft); font-size: 12px; }
.meta span + span::before { content: '/'; margin-right: 8px; color: #a8bab5; }
.role { margin: 0 0 11px; display: flex; align-items: center; gap: 7px; color: var(--mint-dark); font-size: 12px; font-weight: 800; }
.role-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--mint); box-shadow: 0 0 0 4px var(--sky); }
.background { margin: 0; color: var(--ink-soft); font-size: 13px; line-height: 1.8; }
.tags { display: flex; flex-wrap: wrap; gap: 7px; margin: 18px 0; }
.difficulty { background: rgba(193,112,62,.12); color: var(--accent-strong); }
.card-actions { display: grid; gap: 10px; padding-top: 17px; border-top: 1px solid var(--line); }
.start-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.script, .start { min-height: 43px; border: 0; border-radius:var(--radius); background: transparent; color: var(--ink); cursor: pointer; font-weight: 800; font-size: 12px; }
.script { min-height: 35px; width: fit-content; padding: 0 5px; color: var(--mint-dark); }
.script:hover { border-color: var(--mint-dark); color: var(--mint-dark); }
.start { display: flex; align-items: center; justify-content: center; gap: 8px; background: var(--ink); color: white; }
.start.voice { background: var(--mint-dark); }
.start span { color: var(--signal); font-size: 18px; transition: transform .18s; }
.start:hover span { transform: translateX(4px); }
.scene-card { border-color: var(--border); border-radius: var(--radius); background: var(--card); box-shadow: var(--shadow); animation: rise-in .28s ease both; transition: border-color var(--ease),box-shadow var(--ease); }
.scene-card:hover { transform: none; border-color: var(--border-bright); box-shadow: var(--shadow); }
.category { border:1px solid var(--border); background:var(--overlay-2); color:var(--text-2); }
.favorite { border-color:var(--border); background:var(--bg-2); color:var(--text-2); }
.favorite:hover { border-color:var(--border-bright); box-shadow:none; }
.role { color:var(--text-2); }
.role-dot { background:var(--muted-progress); box-shadow:none; }
.difficulty { border-color:var(--border); background:var(--overlay-2); color:var(--text-2); }
.difficulty.easy { border-color:var(--border);background:rgba(79,116,82,.12);color:var(--success); }
.difficulty.medium { border-color:var(--border);background:var(--overlay-2);color:var(--text-2); }
.difficulty.hard { border-color:var(--border);background:rgba(156,74,63,.12);color:var(--danger); }
.card-actions { border-color:var(--border); }
.script { color:var(--text-2); }
.start { border:1px solid var(--border); background:var(--bg-2); color:var(--text); transition:background var(--ease),border-color var(--ease); }
.start.voice { border-color:var(--accent); background:var(--accent); color:#fff; box-shadow:none; }
.start span { color:var(--text-2); }
.start.voice span { color:#fff; }
.start:hover { transform:none; border-color:var(--border-bright); background:var(--overlay-2); box-shadow:none; }
.start.voice:hover { border-color:var(--accent-strong); background:var(--accent-strong); box-shadow:none; }
</style>

