<script setup lang="ts">
import type { AbilityAttempt } from '@/lib/types'

defineProps<{ attempts: AbilityAttempt[] }>()
</script>

<template>
  <section v-if="attempts.length" class="attempts">
    <div class="section-heading"><p class="eyebrow">练习记录</p><h2>反馈与下一次改答</h2><p>以下分数只评价这道薄弱项练习，不等同于整场五维报告。</p></div>
    <article v-for="(attempt, index) in attempts" :key="attempt.id" class="panel attempt">
      <div class="attempt-top"><span>{{ index === 0 ? '最近一次改答' : '较早的改答' }}</span><strong>本题 {{ attempt.score }} / 5</strong></div>
      <p class="answer">{{ attempt.answer }}</p>
      <div class="feedback-grid">
        <div><span>引用的回答原句</span><p>“{{ attempt.answerQuote }}”</p></div>
        <div><span>已经做对</span><p>{{ attempt.strength }}</p></div>
        <div><span>仍需改进</span><p>{{ attempt.gap }}</p></div>
      </div>
      <p class="next-action"><strong>下一次重点：</strong>{{ attempt.nextAction }}</p>
    </article>
  </section>
</template>

<style scoped>
.attempts{margin-top:28px}.section-heading h2{margin:5px 0;font:700 30px/1.2 var(--font-ui)}.section-heading p:not(.eyebrow){color:var(--ink-soft);font-size:13px}.attempt{padding:24px;margin-top:14px}.attempt-top{display:flex;justify-content:space-between;align-items:center;gap:12px;color:var(--mint-dark);font-weight:800}.attempt-top strong{padding:7px 12px;border-radius:99px;background:var(--sky)}.answer{white-space:pre-wrap;line-height:1.7}.feedback-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.feedback-grid div{padding:14px;border:1px solid var(--line);border-radius:var(--radius)}.feedback-grid span{color:var(--mint-dark);font-size:12px;font-weight:800}.feedback-grid p{margin:8px 0 0;line-height:1.65;font-size:13px}.next-action{margin:16px 0 0;padding:12px 15px;background:#edf8f4;line-height:1.6}@media(max-width:700px){.feedback-grid{grid-template-columns:1fr}}
.attempt-top { color:var(--text-2); }
.attempt-top strong { border:1px solid var(--border);background:var(--bg-2); }
.feedback-grid div { border-color:var(--border);background:var(--bg-2); }
.feedback-grid span { color:var(--text-2); }
.next-action { border-left:2px solid var(--accent);background:var(--bg-2); }
</style>
