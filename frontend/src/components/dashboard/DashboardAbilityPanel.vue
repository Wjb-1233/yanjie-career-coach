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
  { key: 'logic', label: '内容与逻辑' },
  { key: 'correctness', label: '信息完整' },
  { key: 'concision', label: '表达干净' },
  { key: 'relevance', label: '贴合问题' },
]

const rows = computed(() => dimensions.map(({ key, label }) => {
  const score = Number(props.scores[key]) || 0
  return { key, label, value: score.toFixed(1), width: `${Math.max(0, Math.min(100, score * 20))}%` }
}))

const weakest = computed(() => props.weaknesses[0] ?? null)
</script>

<template>
  <section class="ability panel" aria-labelledby="ability-title">
    <header class="section-head">
      <h2 id="ability-title" class="label">四维能力</h2>
      <span class="note">最近一次 · 每项 5 分</span>
    </header>

    <div v-if="trainingCount" class="split">
      <div class="radar-wrap">
        <ScoreRadar :scores="scores" quiet />
      </div>

      <div class="detail">
        <dl class="dims" aria-label="四维评分明细">
          <div v-for="item in rows" :key="item.key" :class="{ focus: item.label === focus }">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
        <p v-if="weakest" class="weakest">
          近期最弱：{{ weakest.dimension }}（近 {{ weakest.sampleCount }} 次均值 {{ weakest.averageScore }}）
        </p>
      </div>
    </div>

    <p v-else class="empty-note">完成一次场景训练后，这里会显示四维评分与能力轮廓。</p>
  </section>
</template>

<style scoped>
.ability { margin-top: 40px; padding: 22px 24px 24px; }
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--divider);
}
.section-head h2 { margin: 0; color: var(--text-3); font-size: 12.5px; font-weight: 500; }
.section-head .note { color: var(--text-3); font-size: 12px; }

.split {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 48px;
  align-items: center;
  padding: 24px 0 4px;
}
.radar-wrap { display: flex; justify-content: center; }

.detail { min-width: 0; }
.dims { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 24px; margin: 0; padding: 0; }
.dims div { display: grid; gap: 4px; padding: 10px 0; }
.dims dt { color: var(--text-3); font-size: 12.5px; }
.dims dd { margin: 0; color: var(--text); font-family: var(--font-num); font-size: 26px; font-weight: 500; letter-spacing: -.02em; }
.dims div.focus dt { color: var(--accent-strong); }
.dims div.focus dd { color: var(--accent-strong); }

.weakest { margin: 16px 0 0; color: var(--text-2); font-size: 13px; line-height: 1.7; }
.empty-note { margin: 0; padding: 64px 0 70px; color: var(--text-3); font-size: 13px; }

@media (max-width: 900px) {
  .split { grid-template-columns: 1fr; gap: 20px; padding-top: 18px; }
  .radar-wrap { max-width: 300px; margin: 0 auto; }
  .weakest { text-align: center; }
}

/* 进度条：入场时从 0 长到目标值 */
.bar b {
  width: 0;
  animation: bar-grow .62s cubic-bezier(.22, .8, .28, 1) both;
}
@keyframes bar-grow {
  from { width: 0; }
  to { width: var(--w); }
}
@media (prefers-reduced-motion: reduce) {
  .bar b { animation: none; width: var(--w); }
}
</style>
