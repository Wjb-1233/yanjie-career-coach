<script setup lang="ts">
import { computed } from 'vue'

import type { AbilityPractice, Scores } from '@/lib/types'

const props = defineProps<{ practice: AbilityPractice; scores: Scores | null }>()
const scoreValues = computed(() => props.scores ? Object.values(props.scores) : [])
const strongestScore = computed(() => scoreValues.value.length ? Math.max(...scoreValues.value) : null)
const scoreGap = computed(() => strongestScore.value === null ? null : strongestScore.value - props.practice.baselineScore)
</script>

<template>
  <section class="panel review" aria-label="最近一次训练的整场复盘">
    <div class="review-heading">
      <div><p class="eyebrow">整场复盘</p><h2>先看整场，再练最弱的一项</h2><p class="context">{{ practice.sceneTitle }} · {{ practice.roundCount }} 轮对话</p></div>
      <RouterLink class="report-link" :to="{ name: 'report', params: { id: practice.sessionId } }">查看完整评分报告 →</RouterLink>
    </div>
    <div class="overview">
      <div><span>综合分</span><strong>{{ practice.overallScore }}</strong><small>/ 100</small></div>
      <div class="focus"><span>本次最低项</span><strong>{{ practice.dimensionLabel }}</strong><small>{{ practice.baselineScore }} / 5</small></div>
      <div><span>与最高项差距</span><strong>{{ scoreGap === null ? '—' : `${scoreGap} 分` }}</strong><small>五维评分对照</small></div>
    </div>
    <div class="diagnosis">
      <div><span class="label">报告对整场表达的判断</span><p>{{ practice.reportSummary }}</p></div>
      <div class="evidence" v-if="practice.evidenceQuote"><span class="label">定位到的代表性证据</span><blockquote>“{{ practice.evidenceQuote }}”</blockquote><p>{{ practice.evidenceReason }}</p></div>
      <p v-if="practice.reportDegraded" class="degraded">这份报告由备用评分规则生成。下面的分析只整理已保存的对话与证据，不将规则判断当作模型结论。</p>
    </div>
    <div class="review-section">
      <div class="section-head"><h3>逐轮回看自己的表达</h3><span>共 {{ practice.reviewTurns.length }} 条回答</span></div>
      <p class="section-intro">以下是原对话，不是对每句话单独打分。标出的轮次是本维评分引用的代表性证据。</p>
      <div class="turn-list">
        <details v-for="turn in practice.reviewTurns" :key="turn.roundNo" class="turn" :class="{ highlighted: turn.isFocusEvidence }" :open="turn.isFocusEvidence">
          <summary><span>第 {{ turn.roundNo }} 轮</span><strong>{{ turn.question || '回看这轮回答' }}</strong><em v-if="turn.isFocusEvidence">评分引用</em></summary>
          <div class="turn-body"><p><b>对方提问</b>{{ turn.question || '场景开场' }}</p><p><b>我的回答</b>{{ turn.answer }}</p><span v-if="turn.flags.length" class="risk">表达提醒：{{ turn.flags.join('、') }}</span></div>
        </details>
      </div>
    </div>
    <div v-if="practice.reportSuggestions.length" class="review-section">
      <div class="section-head"><h3>报告给出的改进方向</h3><span>{{ practice.reportSuggestions.length }} 条</span></div>
      <div class="suggestion-list"><article v-for="(suggestion, index) in practice.reportSuggestions" :key="`${suggestion.roundNo}-${index}`"><span>第 {{ suggestion.roundNo }} 轮 · {{ suggestion.problem }}</span><p>{{ suggestion.rewrite }}</p></article></div>
    </div>
    <div class="next-steps">
      <div><span class="label">接下来怎么练</span><p>先用下方题目检查自己能否改进 {{ practice.dimensionLabel }}，再进入专项场景练多轮表达，最后回到原场景复测。</p></div>
      <div class="step-links"><RouterLink class="button secondary" :to="{ name: 'scenes', query: { sceneId: `scene-foundation-${practice.dimension}` } }">练 {{ practice.dimensionLabel }} 场景 →</RouterLink><RouterLink class="button secondary" :to="{ name: 'scenes', query: { sceneId: practice.sceneId } }">回原场景复测 →</RouterLink></div>
    </div>
  </section>
</template>

<style scoped>
.review { padding: 30px; margin-bottom: 24px; }
.review-heading,.section-head,.next-steps { display:flex;justify-content:space-between;align-items:start;gap:20px; }
.review-heading h2 { margin:6px 0;font-size:clamp(25px,3vw,34px); }
.context,.section-intro,.section-head span { color:var(--text-2);font-size:12px; }
.report-link { flex:none;margin-top:8px;color:var(--text-2);font-size:13px;font-weight:650; }
.overview { display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:24px 0; }
.overview > div { padding:17px;border:1px solid var(--border);border-radius:var(--radius);background:var(--bg-2); }
.overview span,.overview small { display:block;color:var(--text-2);font-size:11px; }
.overview strong { display:block;margin:7px 0;font-size:25px; }
.overview .focus { border-color:var(--accent);background:var(--card); }
.overview .focus strong { color:var(--accent-strong); }
.label { color:var(--text-2);font-size:12px;font-weight:650;letter-spacing:.02em; }
.diagnosis { display:grid;gap:14px;line-height:1.75; }
.diagnosis > div { padding:18px;border-left:2px solid var(--border-bright);border-radius:0 10px 10px 0;background:var(--bg-2); }
.diagnosis p { margin:8px 0 0;white-space:pre-wrap; }
.diagnosis blockquote { margin:12px 0 0;color:var(--text); }
.degraded { margin:0;padding:12px 15px;border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-2);font-size:12px; }
.review-section { margin-top:28px;padding-top:25px;border-top:1px solid var(--border); }
.section-head h3 { margin:0;font-size:21px; }
.section-intro { margin:10px 0 15px;line-height:1.6; }
.turn-list,.suggestion-list { display:grid;grid-template-columns:minmax(0,1fr);gap:9px;min-width:0; }
.turn { min-width:0;border:1px solid var(--border);border-radius:var(--radius);background:var(--bg-2); }
.turn.highlighted { border-color:var(--accent); }
.turn summary { display:flex;align-items:center;gap:12px;padding:13px 15px;cursor:pointer;list-style:none; }
.turn summary::-webkit-details-marker { display:none; }
.turn summary span { flex:none;color:var(--text-2);font-size:12px;font-weight:650; }
.turn summary strong { min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;font-weight:600; }
.turn summary em { flex:none;margin-left:auto;color:var(--accent-strong);font-size:11px;font-style:normal; }
.turn-body { padding:0 15px 15px;border-top:1px solid var(--border); }
.turn-body p { margin:13px 0;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere; }
.turn-body b { display:block;margin-bottom:4px;color:var(--text-2);font-size:11px; }
.risk { color:rgba(192,127,117,.5);font-size:11px; }
.suggestion-list { grid-template-columns:repeat(2,minmax(0,1fr));margin-top:16px; }
.suggestion-list article { padding:16px;border:1px solid var(--border);border-radius:var(--radius);background:var(--bg-2); }
.suggestion-list span { color:var(--text-2);font-size:12px;font-weight:650; }
.suggestion-list p { margin:9px 0 0;line-height:1.7;white-space:pre-wrap; }
.next-steps { margin-top:28px;padding:20px;border:1px solid var(--border);border-radius:var(--radius);background:var(--bg-2); }
.next-steps p { max-width:580px;margin:8px 0 0;color:var(--text-2);font-size:13px;line-height:1.7; }
.step-links { display:flex;flex-wrap:wrap;gap:9px;justify-content:flex-end; }
@media (max-width:760px) { .review { padding:20px; }.review-heading,.next-steps { flex-direction:column; }.overview { grid-template-columns:1fr 1fr; }.suggestion-list { grid-template-columns:1fr; }.step-links { justify-content:flex-start; }.turn summary strong { min-width:0; } }
</style>
