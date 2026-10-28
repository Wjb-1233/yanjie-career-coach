<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { useRoute } from 'vue-router'

import AnimatedNumber from '@/components/report/AnimatedNumber.vue'
import ScoreEvidencePanel from '@/components/report/ScoreEvidencePanel.vue'
import ScoreRadar from '@/components/report/ScoreRadar.vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Evaluation, Scores } from '@/lib/types'

const route = useRoute()
const evaluation = shallowRef<Evaluation | null>(null)
const error = shallowRef('')
const labels: Record<keyof Scores, string> = { logic: '逻辑性', appropriateness: '得体性', impact: '感染力', relevance: '针对性', concision: '简洁度' }

const orderedScores = computed(() => evaluation.value
  ? (Object.entries(evaluation.value.scores) as Array<[keyof Scores, number]>).sort((a, b) => b[1] - a[1])
  : [])
const weakestScore = computed(() => evaluation.value ? Math.min(...Object.values(evaluation.value.scores)) : 0)
const styleLine = computed(() => evaluation.value?.styleTags?.join(' · ') ?? '')

onMounted(async () => {
  try {
    const response = await api.get<ApiEnvelope<Evaluation>>(`/evaluations/${route.params.id}`)
    evaluation.value = response.data.data
  } catch (reason) { error.value = errorMessage(reason) }
})
</script>

<template>
  <div class="page report-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">训练报告</p>
        <h1 class="page-title">这次表达，<br />哪里已经做对了？</h1>
        <p class="page-lead">评分不是结论，而是下一次训练的起点。</p>
      </div>
      <RouterLink class="button secondary" to="/scenes">再练一个场景</RouterLink>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-else-if="!evaluation" class="skeleton report-loading" />

    <template v-else>
      <section class="hero">
        <div class="score">
          <p class="label">综合表现</p>
          <div class="figure">
            <span class="num"><AnimatedNumber :value="evaluation.overallScore" /></span>
            <span class="den">/ 100</span>
          </div>
          <p v-if="styleLine" class="style-line">{{ styleLine }}</p>
          <p v-if="evaluation.degraded" class="degraded">本报告由本地评分规则生成，未使用大模型语义评分。</p>
        </div>

        <div class="radar"><ScoreRadar :scores="evaluation.scores" /></div>

        <ul class="dims">
          <li v-for="[key, value] in orderedScores" :key="key" :class="{ weakest: value === weakestScore }">
            <span class="name">{{ labels[key] }}</span>
            <span class="bar"><b :style="{ width: `${value * 20}%` }" /></span>
            <span class="val num">{{ value.toFixed(1) }}</span>
          </li>
        </ul>
      </section>

      <section class="summary">
        <p class="label">教练总评</p>
        <p class="summary-text">{{ evaluation.summary }}</p>
      </section>

      <ScoreEvidencePanel :evaluation="evaluation" />

      <section v-if="evaluation.suggestions.length" class="suggestions">
        <header class="section-head">
          <h2 class="label">改写建议</h2>
          <span class="note">{{ evaluation.suggestions.length }} 处</span>
        </header>
        <article v-for="(suggestion, index) in evaluation.suggestions" :key="`${suggestion.roundNo}-${index}`" class="suggestion">
          <span class="idx num">{{ String(index + 1).padStart(2, '0') }}</span>
          <div class="suggestion-body">
            <h3>{{ suggestion.problem }}</h3>
            <div class="compare">
              <div class="quote">
                <span>原表达</span>
                <p>{{ suggestion.original || '未记录原文' }}</p>
              </div>
              <div class="quote rewrite">
                <span>建议改写</span>
                <p>{{ suggestion.rewrite }}</p>
              </div>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.report-page { max-width: 1080px; }
.report-loading { min-height: 520px; }

.hero {
  display: grid;
  grid-template-columns: minmax(0, .78fr) 260px minmax(0, 1fr);
  align-items: center;
  gap: 40px;
  padding: 34px 38px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: linear-gradient(180deg, var(--card), var(--bg-2));
}
.score { display: flex; flex-direction: column; }
.label { margin: 0; color: var(--text-3); font-size: 11px; letter-spacing: .2em; }
.figure { display: flex; align-items: flex-end; gap: 12px; margin-top: 18px; }
.figure .num {
  color: var(--text);
  font-family: var(--font-num);
  font-size: 92px;
  font-weight: 200;
  font-variant-numeric: tabular-nums;
  letter-spacing: -.05em;
  line-height: .8;
}
.figure .den { padding-bottom: 9px; color: var(--text-3); font-family: var(--font-num); font-size: 12px; letter-spacing: .06em; }
.style-line { margin: 20px 0 0; color: var(--text-2); font-size: 13px; letter-spacing: .04em; }
.degraded { margin: 12px 0 0; color: var(--warning); font-size: 11px; line-height: 1.7; }

.radar { display: flex; justify-content: center; }

.dims { display: flex; flex-direction: column; margin: 0; padding: 0; list-style: none; }
.dims li {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) 34px;
  align-items: center;
  gap: 16px;
  padding: 9px 0;
  border-bottom: 1px solid var(--divider);
}
.dims li:last-child { border-bottom: 0; }
.dims .name { color: var(--text-3); font-size: 12px; letter-spacing: .08em; }
.dims .bar { position: relative; height: 2px; background: var(--track); }
.dims .bar b { position: absolute; inset: 0 auto 0 0; background: var(--fill); }
.dims .val { color: var(--text); font-family: var(--font-num); font-size: 14px; text-align: right; }
.dims li.weakest .name { color: var(--text); }
.dims li.weakest .bar b { background: var(--accent); }

.summary { margin-top: 42px; padding-top: 18px; border-top: 1px solid var(--divider); }
.summary-text { max-width: 76ch; margin: 16px 0 0; color: var(--text-2); font-size: 15px; line-height: 2; letter-spacing: .01em; }

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

.suggestions { margin-top: 42px; }
.suggestion {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 18px;
  padding: 24px 0;
  border-bottom: 1px solid var(--divider);
}
.suggestion .idx { color: var(--text-3); font-family: var(--font-num); font-size: 11px; letter-spacing: .08em; }
.suggestion h3 { margin: 0 0 16px; color: var(--text); font-size: 15px; font-weight: 500; letter-spacing: .01em; line-height: 1.6; }

.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
.quote { padding-left: 16px; border-left: 1px solid var(--border-bright); }
.quote.rewrite { border-left: 1px solid var(--accent); }
.quote span { display: block; color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.quote p { margin: 9px 0 0; color: var(--text-2); font-size: 13px; line-height: 1.85; white-space: pre-wrap; }
.quote.rewrite p { color: var(--text); }

@media (max-width: 960px) {
  .hero { grid-template-columns: 1fr; gap: 26px; padding: 28px 24px; }
  .radar { max-width: 260px; margin: 0 auto; }
  .compare { grid-template-columns: 1fr; gap: 16px; }
}
@media (max-width: 560px) {
  .suggestion { grid-template-columns: 1fr; gap: 10px; }
}
</style>
