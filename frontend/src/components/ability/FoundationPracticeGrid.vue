<script setup lang="ts">
import { computed } from 'vue'
import type { Scene } from '@/lib/types'

const props = defineProps<{ scenes: Scene[] }>()

const dimensionOrder = ['logic', 'appropriateness', 'impact', 'relevance', 'concision']
const sortedScenes = computed(() => [...props.scenes].sort((a, b) =>
  dimensionOrder.indexOf(a.id.replace('scene-foundation-', '')) - dimensionOrder.indexOf(b.id.replace('scene-foundation-', ''))))

const dimensionNames: Record<string, string> = {
  logic: '逻辑性', appropriateness: '得体性', impact: '感染力',
  relevance: '针对性', concision: '简洁度',
}

function dimension(scene: Scene): string {
  return dimensionNames[scene.id.replace('scene-foundation-', '')] ?? '表达能力'
}
</script>

<template>
  <section class="foundation-section" aria-labelledby="foundation-heading">
    <div class="section-heading">
      <div><p class="eyebrow">通用练习</p><h2 id="foundation-heading">选择一个维度，开始对练</h2></div>
      <span>无需先完成面试</span>
    </div>
    <div class="foundation-grid">
      <article v-for="(scene, index) in sortedScenes" :key="scene.id" class="foundation-card">
        <div class="card-top"><span class="dimension">{{ dimension(scene) }}</span><span class="index">{{ String(index + 1).padStart(2, '0') }}</span></div>
        <h3>{{ scene.title }}</h3>
        <p>{{ scene.goal }}</p>
        <RouterLink class="practice-link" :to="{ name: 'scenes', query: { sceneId: scene.id } }">进入对练 <span aria-hidden="true">→</span></RouterLink>
      </article>
    </div>
  </section>
</template>

<style scoped>
.foundation-section { margin: 32px 0 42px; }
.section-heading { display:flex; justify-content:space-between; align-items:end; gap:16px; margin-bottom:16px; }
.section-heading h2 { margin:0; font-size:24px; line-height:1.3; }
.section-heading > span { color:var(--text-2); font-size:12px; }
.foundation-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }
.foundation-card { min-height:230px; padding:24px; display:flex; flex-direction:column; border:1px solid var(--border); border-radius:var(--radius); background:var(--card); box-shadow:var(--shadow); transition:border-color var(--ease); }
.foundation-card:hover { border-color:var(--border-bright); }
.card-top { display:flex; justify-content:space-between; align-items:center; }
.dimension { padding:5px 10px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--overlay-2); color:var(--text-2); font-size:12px; font-weight:600; }
.index { color:var(--text-3); font-size:28px; font-weight:500; }
h3 { margin:14px 0 9px; font-size:20px; line-height:1.35; }
p:not(.eyebrow) { margin:0 0 18px; color:var(--text-2); font-size:13px; line-height:1.7; }
.practice-link { margin-top:auto; color:var(--text); font-size:13px; font-weight:650; text-decoration:none; }
.practice-link span { display:inline-block; transition:transform var(--ease); }
.practice-link:hover span { transform:translateX(4px); }
@media(max-width:850px){.foundation-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:580px){.foundation-grid{grid-template-columns:1fr}.section-heading{align-items:start;flex-direction:column}.foundation-card{min-height:190px}}
</style>
