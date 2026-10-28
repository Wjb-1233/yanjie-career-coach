<script setup lang="ts">
import { computed, shallowRef } from 'vue'

import type { Evaluation, Scores } from '@/lib/types'

const props = defineProps<{ evaluation: Evaluation }>()
const labels: Record<keyof Scores, string> = {
  logic: '逻辑性',
  appropriateness: '得体性',
  impact: '感染力',
  relevance: '针对性',
  concision: '简洁度',
}
const keys = Object.keys(labels) as Array<keyof Scores>
const selected = shallowRef<keyof Scores | null>(null)
const weakest = computed(() => keys.reduce((lowest, key) =>
  props.evaluation.scores[key] < props.evaluation.scores[lowest] ? key : lowest,
))
const active = computed(() => selected.value ?? weakest.value)
const evidence = computed(() => props.evaluation.evidence?.find((item) => item.dimension === active.value))
const answerParts = computed(() => {
  if (!evidence.value) return null
  const index = evidence.value.answer.indexOf(evidence.value.quote)
  if (index < 0) return null
  return {
    before: evidence.value.answer.slice(0, index),
    quote: evidence.value.quote,
    after: evidence.value.answer.slice(index + evidence.value.quote.length),
  }
})
</script>

<template>
  <section class="evidence-panel panel" aria-labelledby="evidence-heading">
    <div class="panel-heading">
      <div>
        <p class="eyebrow">评分依据</p>
        <h2 id="evidence-heading">分数依据，回到原话</h2>
        <p>每维分数综合整场表现；下方是可核对的代表性回答，不是单句定分。</p>
      </div>
      <RouterLink v-if="evaluation.planId" class="plan-link" :to="`/plans/${evaluation.planId}`">
        查看针对性训练计划 →
      </RouterLink>
    </div>

    <div class="dimension-tabs" role="tablist" aria-label="查看五维评分依据">
      <button
        v-for="key in keys"
        :key="key"
        type="button"
        role="tab"
        :aria-selected="active === key"
        :class="{ active: active === key }"
        @click="selected = key"
      >
        <span>{{ labels[key] }}</span>
        <strong>{{ evaluation.scores[key] }} / 5</strong>
        <small v-if="key === weakest">优先练习</small>
      </button>
    </div>

    <div v-if="evidence" class="evidence-detail" role="tabpanel">
      <p class="round-label">第 {{ evidence.roundNo }} 轮 · 原文已核对</p>
      <div v-if="evidence.resumeQuote" class="resume-reference">
        <span>简历中的相关片段</span>
        <p>“{{ evidence.resumeQuote }}”</p>
      </div>
      <div class="dialogue">
        <div><span>面试官提问</span><p>{{ evidence.question }}</p></div>
        <div><span>我的完整回答</span><p v-if="answerParts">{{ answerParts.before }}<mark>{{ answerParts.quote }}</mark>{{ answerParts.after }}</p></div>
      </div>
      <div class="reason-grid">
        <div><span>为什么是这个分数</span><p>{{ evidence.reason }}</p></div>
        <div><span>下一步怎么练</span><p>{{ evidence.nextAction }}</p></div>
      </div>
    </div>
    <div v-else class="empty-evidence" role="tabpanel">
      <strong>暂无可核验证据</strong>
      <p>这份报告在该维度没有通过“轮次与回答原句”的核对，因此不展示推测出的依据。分数和原有改写建议仍可参考。</p>
    </div>
  </section>
</template>

<style scoped>
.evidence-panel { margin-top: 22px; padding: clamp(22px, 4vw, 34px); }
.panel-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.panel-heading h2 { margin: 0; font: 700 clamp(25px, 3vw, 34px)/1.2 var(--font-ui); }
.panel-heading p:last-child { margin: 10px 0 0; color: var(--ink-soft); line-height: 1.6; }
.plan-link { flex: none; color: var(--signal); font-weight: 800; text-decoration: none; }
.dimension-tabs { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 9px; margin-top: 27px; }
.dimension-tabs button { min-height: 90px; padding: 13px; border: 1px solid var(--line); border-radius:var(--radius); background: var(--overlay-2); color: var(--ink); text-align: left; cursor: pointer; }
.dimension-tabs button.active { border-color: var(--mint); background: var(--sky); box-shadow: inset 0 0 0 1px var(--mint); }
.dimension-tabs span, .dimension-tabs strong, .dimension-tabs small { display: block; }
.dimension-tabs strong { margin-top: 7px; font-size: 20px; }
.dimension-tabs small { margin-top: 3px; color: var(--signal); }
.evidence-detail, .empty-evidence { margin-top: 22px; padding: 23px; border-radius:var(--radius); background: var(--bg-2); }
.round-label { margin: 0 0 17px; color: var(--signal); font-weight: 800; }
.resume-reference { margin-bottom: 17px; padding: 14px 18px; border-left: 3px solid var(--mint); background:var(--card); }
.resume-reference p { margin: 7px 0 0; line-height: 1.6; }
.dialogue { display: grid; gap: 12px; }
.dialogue > div { padding: 16px 18px; border-radius:var(--radius); background:var(--card); }
.dialogue span, .reason-grid span, .resume-reference span { color: var(--ink-soft); font-size: 12px; font-weight: 800; }
.dialogue p, .reason-grid p { margin: 8px 0 0; line-height: 1.8; white-space: pre-wrap; }
.dialogue mark { padding: 2px 3px; border-radius: 3px; background: #ffe0bd; color: var(--ink); }
.reason-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 14px; }
.reason-grid > div { padding: 17px 18px; border-radius:var(--radius); background:var(--card); }
.empty-evidence strong { display: block; color: var(--ink); }
.empty-evidence p { margin: 8px 0 0; color: var(--ink-soft); line-height: 1.7; }
@media (max-width: 720px) { .panel-heading { align-items: flex-start; flex-direction: column; } .dimension-tabs { grid-template-columns: repeat(2, 1fr); } .reason-grid { grid-template-columns: 1fr; } }
.dimension-tabs button { border-color:var(--border);background:var(--overlay-1);color:var(--text);transition:transform var(--ease),border-color var(--ease),box-shadow var(--ease); }
.dimension-tabs button:hover { transform:translateY(-2px);border-color:var(--border-bright); }
.dimension-tabs button.active { border-color:var(--accent);background:var(--bg-2);box-shadow:none; }
.dimension-tabs small,.round-label,.plan-link { color:var(--text-2); }
.evidence-detail,.empty-evidence { border:1px solid var(--border);background:var(--bg-2); }
.resume-reference,.dialogue > div,.reason-grid > div { border:1px solid var(--border);background:var(--card); }
.resume-reference { border-left:1px solid var(--accent); }
.dialogue mark { background:rgba(154,163,181,.16);color:var(--text); }
</style>
