<script setup lang="ts">
import { onUnmounted, shallowRef, watch } from 'vue'

import type { AbilityPractice } from '@/lib/types'

const props = defineProps<{ practice: AbilityPractice; sending: boolean }>()
const emit = defineEmits<{ submit: [answer: string] }>()
const answer = shallowRef('')
const waitingSeconds = shallowRef(0)
let waitingTimer: ReturnType<typeof setInterval> | null = null

watch(() => props.sending, (sending) => {
  if (waitingTimer) clearInterval(waitingTimer)
  waitingTimer = null
  waitingSeconds.value = 0
  if (sending) waitingTimer = setInterval(() => { waitingSeconds.value += 1 }, 1000)
}, { immediate: true })
onUnmounted(() => { if (waitingTimer) clearInterval(waitingTimer) })

watch(() => props.practice.attempts[0]?.id, (current, previous) => {
  if (current && current !== previous) answer.value = ''
})

function submit(): void {
  const value = answer.value.trim()
  if (value.length >= 12 && !props.sending) emit('submit', value)
}
</script>

<template>
  <section class="panel drill">
    <div class="drill-header">
      <div>
        <p class="eyebrow">薄弱项训练</p>
        <h2>巩固练习：再答一道代表题</h2>
        <p>看完整场复盘后，选评分引用的一轮练习改答，重点落实 <strong>{{ practice.dimensionLabel }}</strong> 的具体动作。</p>
      </div>
      <span class="focus-tag">{{ practice.dimensionLabel }} · 报告 {{ practice.baselineScore }} / 5</span>
    </div>
    <p v-if="practice.reportDegraded" class="notice">最近一次报告使用了备用评分，薄弱项仅供参考；本题反馈仍需大模型正常运行。</p>
    <div class="source-grid">
      <div class="source-card">
        <span class="source-label">当时的问题</span>
        <p>{{ practice.question }}</p>
      </div>
      <div class="source-card original">
        <span class="source-label">你当时的回答</span>
        <p>{{ practice.originalAnswer }}</p>
        <blockquote v-if="practice.evidenceQuote">报告引用：“{{ practice.evidenceQuote }}”</blockquote>
      </div>
    </div>
    <div class="task-box">
      <span class="source-label">本题训练目标</span>
      <p>{{ practice.targetAction }}</p>
      <small v-if="practice.evidenceReason">来自评分依据：{{ practice.evidenceReason }}</small>
    </div>
    <form class="answer-form" @submit.prevent="submit">
      <label for="ability-answer">现在请重新回答这个问题</label>
      <textarea id="ability-answer" v-model="answer" maxlength="3000" rows="6" :disabled="sending" placeholder="先直接回答问题，再按本题目标补充关键事实。请使用自己的真实经历，不必照抄范例。" />
      <div v-if="sending" class="analysis-status" role="status"><span class="analysis-pulse" aria-hidden="true" /><span>正在等待 AI 核对回答与引用原句 · 已等待 {{ waitingSeconds }} 秒。请保持页面开启；若生成失败，本次不会计入练习记录。</span></div>
      <div class="form-footer">
        <small>{{ answer.trim().length }} / 3000 字 · 至少 12 字</small>
        <button type="submit" class="button signal" :disabled="sending || answer.trim().length < 12">{{ sending ? '正在分析回答…' : practice.attempts.length ? '提交新一次改答' : '提交改答并获取反馈' }}</button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.drill{padding:32px}.drill-header{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}.drill-header h2{margin:12px 0;font-size:clamp(26px,3vw,36px);line-height:1.25}.drill-header p:not(.eyebrow){color:var(--text-2);line-height:1.7;margin:0}.focus-tag{flex:none;padding:9px 14px;border-radius:var(--radius-sm);background:var(--primary-soft);color:var(--primary-hover);font-size:13px;font-weight:750}.notice{padding:12px 16px;background:rgba(194,168,119,.12);color:var(--warning);border-radius:var(--radius-sm)}.source-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:24px}.source-card{padding:20px;border:1px solid var(--border);border-radius:var(--radius);background:var(--card)}.source-card.original{background:var(--bg-2)}.source-label{color:var(--primary);font-size:12px;font-weight:800;letter-spacing:.04em}.source-card p{margin:10px 0 0;line-height:1.75;white-space:pre-wrap}.source-card blockquote{margin:14px 0 0;padding-left:12px;border-left:3px solid var(--primary);color:var(--text-2);line-height:1.6}.task-box{margin:16px 0 26px;padding:17px 20px;border-left:4px solid var(--primary);border-radius:0 8px 8px 0;background:var(--primary-soft)}.task-box p{margin:7px 0;line-height:1.65;font-weight:700}.task-box small{color:var(--text-2);line-height:1.6}.answer-form label{display:block;margin-bottom:10px;font-weight:750}.answer-form textarea{width:100%;min-height:165px;resize:vertical;padding:16px;border:1px solid var(--border);border-radius:var(--radius);background:var(--card);color:var(--text);font:inherit;line-height:1.7;box-sizing:border-box}.answer-form textarea:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 4px rgba(37,99,235,.12)}.analysis-status{display:flex;gap:10px;align-items:flex-start;margin-top:12px;padding:12px 14px;border-radius:var(--radius-sm);background:var(--primary-soft);color:var(--primary-hover);font-size:13px;line-height:1.6}.analysis-pulse{flex:none;width:8px;height:8px;margin-top:6px;border-radius:50%;background:var(--primary);box-shadow:0 0 0 4px var(--border);animation:pulse 1.2s ease-in-out infinite}@keyframes pulse{50%{opacity:.35}}.form-footer{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:12px}.form-footer small{color:var(--text-2)}.form-footer button:disabled{opacity:.55;cursor:not-allowed}@media(max-width:700px){.drill{padding:22px}.drill-header{flex-direction:column}.source-grid{grid-template-columns:1fr}.form-footer{align-items:stretch;flex-direction:column}.form-footer button{width:100%}}
.drill { border-color:var(--border);background:var(--card); }
.focus-tag { border:1px solid var(--accent);background:var(--primary-soft);color:var(--accent-strong); }
.notice { border:1px solid var(--border);background:var(--bg-2);color:var(--text-2); }
.source-card { border-color:var(--border);background:var(--bg-2); }
.source-card.original { background:var(--bg-2); }
.source-label { color:var(--text-2); }
.source-card blockquote { border-color:var(--border-bright); }
.task-box { border-color:var(--accent);background:var(--bg-2); }
.answer-form textarea { border-color:var(--border);background:var(--bg-2);color:var(--text); }
.answer-form textarea:focus { border-color:var(--accent);box-shadow:0 0 0 3px rgba(91,141,239,.12); }
.analysis-status { background:var(--bg-2);color:var(--text-2); }
.analysis-pulse { background:var(--muted-progress);box-shadow:none; }
</style>
