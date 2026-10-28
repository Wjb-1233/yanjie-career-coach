<script setup lang="ts">
import { computed } from 'vue'

import type { ScoreComparison, Scores } from '@/lib/types'

const props = defineProps<{ comparison: ScoreComparison; focusDimension: string }>()
const labels: Record<keyof Scores, string> = {
  logic: '逻辑性', appropriateness: '得体性', impact: '感染力',
  relevance: '针对性', concision: '简洁度',
}
const rows = computed(() => (Object.keys(labels) as Array<keyof Scores>).map((key) => ({
  key,
  label: labels[key],
  before: props.comparison.baselineScores[key],
  after: props.comparison.retestScores[key],
  delta: props.comparison.scoreDeltas[key],
})))
const outcome = computed(() => ({
  IMPROVED: '本轮评分显示提升',
  NEEDS_PRACTICE: '本轮尚未达到提升标准',
  PROVISIONAL: '离线评分，结果待验证',
}[props.comparison.status]))
const signed = (value: number) => value > 0 ? `+${value}` : String(value)
</script>

<template>
  <section class="comparison panel" aria-label="训练前后评分对比">
    <div class="comparison-heading">
      <div>
        <p class="eyebrow">改进前后</p>
        <h2>复测结果与下一步</h2>
        <p>重点维度：{{ focusDimension }}。任务完成率与能力变化分别记录，不把进度当成提升。</p>
      </div>
      <span class="outcome" :class="comparison.status.toLowerCase()">{{ outcome }}</span>
    </div>
    <div class="overall">
      <span>综合分 {{ comparison.baselineOverall }} → {{ comparison.retestOverall }}</span>
      <strong :class="{ positive: comparison.overallDelta > 0, negative: comparison.overallDelta < 0 }">
        {{ signed(comparison.overallDelta) }}
      </strong>
    </div>
    <div class="score-table" role="table" aria-label="五维评分变化">
      <div class="score-row heading" role="row"><span>维度</span><span>初次</span><span>复测</span><span>变化</span></div>
      <div v-for="row in rows" :key="row.key" class="score-row" role="row">
        <span>{{ row.label }}</span><span>{{ row.before }}</span><span>{{ row.after }}</span>
        <strong :class="{ positive: row.delta > 0, negative: row.delta < 0 }">{{ signed(row.delta) }}</strong>
      </div>
    </div>
    <p class="recommendation">{{ comparison.recommendation }}</p>
    <div class="comparison-actions">
      <RouterLink :to="`/report/${comparison.baselineSessionId}`">查看初次报告</RouterLink>
      <RouterLink :to="`/report/${comparison.retestSessionId}`">查看复测报告</RouterLink>
      <RouterLink v-if="comparison.status !== 'IMPROVED'" class="button signal" :to="{ name: 'scenes', query: { sceneId: comparison.sceneId } }">再次训练并生成新计划 →</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.comparison { padding: 28px; margin-top: 20px; }
.comparison-heading { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; }
.comparison h2 { margin: 6px 0 8px; font: 700 26px/1.3 var(--font-ui); }
.comparison-heading p:last-child { margin: 0; color: var(--ink-soft); line-height: 1.7; }
.outcome { flex: none; padding: 8px 12px; border-radius: 99px; background: var(--overlay-2); color: var(--ink-soft); font-size: 12px; }
.outcome.improved { background: var(--sky); color: var(--mint-dark); }
.outcome.needs_practice, .outcome.provisional { background: rgba(194,168,119,.14); color: var(--warning); }
.overall { display: flex; align-items: center; gap: 12px; margin: 24px 0 12px; font-size: 18px; }
.overall strong { font-size: 23px; }
.score-row { display: grid; grid-template-columns: 1fr repeat(3, 80px); gap: 10px; padding: 11px 12px; border-bottom: 1px solid var(--line); }
.score-row.heading { background: var(--overlay-1); color: var(--ink-soft); font-size: 12px; }
.positive { color: var(--mint-dark); }
.negative { color: var(--warn); }
.recommendation { margin: 20px 0; padding: 14px 16px; border-left: 3px solid var(--mint); background: var(--sky); line-height: 1.7; }
.comparison-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; font-size: 13px; }
.comparison-actions > a:not(.button) { color: var(--mint-dark); font-weight: 700; }
@media (max-width: 600px) { .comparison-heading { flex-direction: column; } .score-row { grid-template-columns: 1fr repeat(3, 48px); } }
.outcome { background:var(--overlay-2); }
.outcome.improved { background:var(--bg-2);color:var(--text); }
.outcome.needs_practice,.outcome.provisional { background:var(--bg-2);color:var(--text-2); }
.score-row.heading { background:var(--overlay-1); }
.positive,.comparison-actions > a:not(.button) { color:var(--text); }
.negative { color:var(--text-2); }
.recommendation { border-color:var(--accent);background:var(--bg-2); }
</style>
