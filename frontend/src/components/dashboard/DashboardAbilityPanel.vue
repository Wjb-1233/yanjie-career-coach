<script setup lang="ts">
import { computed } from 'vue'

import ScoreRadar from '@/components/report/ScoreRadar.vue'
import type { Scores } from '@/lib/types'

const props = defineProps<{
  scores: Scores
  focus: string
  trainingCount: number
  weaknesses: Array<{ dimension: string; averageScore: number; sampleCount: number }>
}>()

const dimensions: Array<{ key: keyof Scores; label: string }> = [
  { key: 'logic', label: '逻辑性' },
  { key: 'appropriateness', label: '得体性' },
  { key: 'impact', label: '感染力' },
  { key: 'relevance', label: '针对性' },
  { key: 'concision', label: '简洁度' },
]

const rows = computed(() => dimensions.map(({ key, label }) => {
  const score = Number(props.scores[key]) || 0
  return { key, label, value: score.toFixed(1), width: `${Math.max(0, Math.min(100, score * 20))}%` }
}))

const weakest = computed(() => props.weaknesses[0] ?? null)
</script>

<template>
  <section class="ability" aria-labelledby="ability-title">
    <header class="section-head">
      <h2 id="ability-title" class="label">五维能力</h2>
      <span class="note">最近一次 · 每项 5 分</span>
    </header>

    <div v-if="trainingCount" class="split">
      <div class="radar-wrap">
        <ScoreRadar :scores="scores" quiet />
      </div>

      <div class="detail">
        <ul class="dims" aria-label="五维评分明细">
          <li v-for="item in rows" :key="item.key" :class="{ focus: item.label === focus }">
            <span class="name">{{ item.label }}</span>
            <span class="bar"><b :style="{ width: item.width }" /></span>
            <span class="val num">{{ item.value }}</span>
          </li>
        </ul>
        <p v-if="weakest" class="weakest">
          近期最弱 · {{ weakest.dimension }}（近 {{ weakest.sampleCount }} 次均值 {{ weakest.averageScore }}）
        </p>
      </div>
    </div>

    <p v-else class="empty-note">完成一次场景训练后，这里会显示五维评分与能力轮廓。</p>
  </section>
</template>

<style scoped>
.ability { margin-top: 46px; }
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--divider);
}
.section-head h2 { margin: 0; color: var(--text-3); font-size: 11px; font-weight: 400; letter-spacing: .2em; }
.section-head .note { color: var(--text-3); font-size: 11px; letter-spacing: .06em; }

.split {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 56px;
  align-items: center;
  padding: 26px 0 2px;
}
.radar-wrap { display: flex; justify-content: center; }

.detail { min-width: 0; }
.dims { display: flex; flex-direction: column; margin: 0; padding: 0; list-style: none; }
.dims li {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr) 40px;
  align-items: center;
  gap: 18px;
  padding: 11px 0;
  border-bottom: 1px solid var(--divider);
}
.dims li:last-child { border-bottom: 0; }
.dims .name { color: var(--text-3); font-size: 12px; letter-spacing: .08em; transition: color var(--ease); }
.dims .bar { position: relative; height: 2px; background: var(--track); }
.dims .bar b { position: absolute; inset: 0 auto 0 0; background: var(--fill); transition: width .5s var(--ease); }
.dims .val { color: var(--text); font-family: var(--font-num); font-size: 15px; font-weight: 400; letter-spacing: -.01em; text-align: right; }
.dims li.focus .name { color: var(--text); }
.dims li.focus .bar b { background: var(--accent); }

.weakest { margin: 18px 0 0; color: var(--text-3); font-size: 11px; letter-spacing: .06em; line-height: 1.7; }
.empty-note { margin: 0; padding: 64px 0 70px; color: var(--text-3); font-size: 13px; }

@media (max-width: 900px) {
  .split { grid-template-columns: 1fr; gap: 20px; padding-top: 18px; }
  .radar-wrap { max-width: 300px; margin: 0 auto; }
  .weakest { text-align: center; }
}
</style>
