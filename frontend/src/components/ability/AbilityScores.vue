<script setup lang="ts">
import type { ScoreDimension, Scores } from '@/lib/types'

defineProps<{ scores: Scores; focus: ScoreDimension }>()

const dimensions: Array<{ key: ScoreDimension; label: string; cue: string }> = [
  { key: 'logic', label: '逻辑性', cue: '结论、依据与结果' },
  { key: 'appropriateness', label: '得体性', cue: '尊重与表达边界' },
  { key: 'impact', label: '感染力', cue: '真实细节与说服力' },
  { key: 'relevance', label: '针对性', cue: '回应当前问题' },
  { key: 'concision', label: '简洁度', cue: '重点与信息密度' },
]
</script>

<template>
  <section class="score-grid" aria-label="最近一次五维评分">
    <article v-for="item in dimensions" :key="item.key" class="score-card" :class="{ weakest: focus === item.key }">
      <span>{{ item.label }}</span>
      <div class="score-ring" :style="{ '--angle': `${scores[item.key] * 72}deg` }" role="progressbar" :aria-label="`${item.label} ${scores[item.key]} / 5`" :aria-valuenow="scores[item.key]" aria-valuemin="0" aria-valuemax="5"><strong>{{ scores[item.key] }}<small> / 5</small></strong></div>
      <p>{{ item.cue }}</p>
      <em v-if="focus === item.key">本次练习重点</em>
    </article>
  </section>
</template>

<style scoped>
.score-grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:16px; margin:26px 0 36px; }
.score-card { min-height:172px; padding:19px 16px; border:1px solid var(--border); border-radius:var(--radius); background:var(--card); text-align:center; transition:border-color var(--ease),box-shadow var(--ease); }
.score-card:hover { border-color:var(--border-bright); }
.score-card.weakest { border-color:var(--accent); }
.score-card > span { color:var(--text-2); font-size:13px; font-weight:600; }
.score-card.weakest > span { color:var(--accent-strong); }
.score-ring { position:relative; display:grid; width:78px; height:78px; place-items:center; margin:15px auto 13px; border-radius:50%; background:conic-gradient(var(--muted-progress) var(--angle),var(--track) var(--angle)); }
.score-ring::before { content:''; position:absolute; inset:7px; border-radius:50%; background:var(--card); }
.score-card.weakest .score-ring { background:conic-gradient(var(--accent) var(--angle),var(--track) var(--angle)); }
.score-ring strong { position:relative; z-index:1; display:block; margin:0; color:var(--text); font-size:25px; font-weight:500; font-variant-numeric:tabular-nums; }
.score-ring small { color:var(--text-3); font-size:11px; font-weight:400; }
.score-card p { margin:0; color:var(--text-3); font-size:11px; line-height:1.5; }
.score-card em { display:block; margin-top:8px; color:var(--accent-strong); font-size:11px; font-style:normal; font-weight:600; }
@media(max-width:950px){.score-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:600px){.score-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.score-card{min-height:165px;padding:16px 10px}}
</style>
