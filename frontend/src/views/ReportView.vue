<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { useRoute } from 'vue-router'

import AnimatedNumber from '@/components/report/AnimatedNumber.vue'
import ScoreEvidencePanel from '@/components/report/ScoreEvidencePanel.vue'
import ScoreRadar from '@/components/report/ScoreRadar.vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Evaluation, Scores, TrainingMessage, TrainingSession } from '@/lib/types'

const route = useRoute()
const evaluation = shallowRef<Evaluation | null>(null)
const messages = shallowRef<TrainingMessage[]>([])
const session = shallowRef<TrainingSession | null>(null)

interface Round { roundNo: number; question: string; answer: string; flags: readonly string[]; annotated: boolean }
const rounds = computed<Round[]>(() => {
  const result: Round[] = []
  let question = ''
  for (const message of messages.value) {
    if (message.speaker === 'AI') { question = message.content; continue }
    if (message.speaker !== 'USER') continue
    result.push({
      roundNo: message.roundNo,
      question,
      answer: message.content,
      flags: message.flags,
      annotated: Boolean(evaluation.value?.suggestions.some((item) => item.roundNo === message.roundNo)),
    })
  }
  return result
})
const error = shallowRef('')
const deliveryAdvice = computed(() => {
  const raw = deliveryStats.value
  if (!raw) return [] as string[]
  const tips: string[] = []
  if (raw.speechRate > 260) tips.push('语速偏快（每分钟 ' + raw.speechRate + ' 字），关键信息容易被带过')
  else if (raw.speechRate < 120) tips.push('语速偏慢（每分钟 ' + raw.speechRate + ' 字），可以更紧凑一些')
  if (raw.longestPause >= 3) tips.push('最长停顿 ' + raw.longestPause + ' 秒，卡顿时可以用过渡句衔接')
  else if (raw.pauseCount >= 6) tips.push('停顿 ' + raw.pauseCount + ' 次偏多，先想清结论再开口')
  if (raw.fillerTotal >= 5) tips.push('填充词 ' + raw.fillerTotal + ' 次，换成短停顿会更稳')
  return tips
})

const visionStats = computed(() => {
  const raw = (session.value?.delivery as { vision?: Record<string, unknown> } | undefined)?.vision
  if (!raw || raw.available === false) return null
  return raw as {
    faceRatio: number
    eyeContactRatio: number
    headStability: number
    brightness: number
    centerOffset: number
    tips?: string[]
  }
})

const replayMarks = computed<Array<{ text: string; start: number }>>(() => {
  const marks = (session.value?.delivery as { marks?: Array<{ text: string; start: number }> } | undefined)?.marks
  return Array.isArray(marks) ? marks : []
})

const comparison = computed(() => {
  const current = evaluation.value
  if (!current?.previousScores || current.previousOverall === null) return null
  const rows = (['logic', 'relevance', 'correctness', 'concision'] as Array<keyof Scores>).map((key) => ({
    key,
    label: labels[key],
    before: current.previousScores![key],
    after: current.scores[key],
    delta: current.scores[key] - current.previousScores![key],
  }))
  return {
    before: current.previousScores,
    after: current.scores,
    beforeOverall: current.previousOverall,
    afterOverall: current.overallScore,
    rows,
  }
})

function replaySeek(seconds: number): void {
  const media = document.querySelector<HTMLVideoElement>('.replay-media')
  if (!media) return
  media.currentTime = seconds
  void media.play().catch(() => undefined)
}

function exportPdf(): void {
  window.print()
}

const upgradeStats = computed(() => {
  const rows = evaluation.value?.upgrades ?? []
  const counts = new Map<string, number>()
  for (const row of rows) counts.set(row.type, (counts.get(row.type) ?? 0) + 1)
  return {
    total: rows.length,
    types: [...counts.entries()].map(([type, count]) => `${type} ×${count}`),
  }
})

const deliveryStats = computed(() => {
  const raw = session.value?.delivery
  if (!raw || !raw.speechRate) return null
  return raw
})

const labels: Record<keyof Scores, string> = { logic: '内容与逻辑', relevance: '贴合问题', correctness: '信息完整', concision: '表达干净' }

const orderedScores = computed(() => evaluation.value
  ? (Object.entries(evaluation.value.scores) as Array<[keyof Scores, number]>).sort((a, b) => b[1] - a[1])
  : [])
const weakestScore = computed(() => evaluation.value ? Math.min(...Object.values(evaluation.value.scores)) : 0)

const overallDelta = computed(() => {
  const current = evaluation.value
  if (!current || current.previousOverall === null || current.previousOverall === undefined) return null
  return Math.round((current.overallScore - current.previousOverall) * 10) / 10
})

function deltaOf(key: keyof Scores): number | null {
  const current = evaluation.value
  if (!current?.previousScores) return null
  const diff = current.scores[key] - current.previousScores[key]
  return diff === 0 ? 0 : diff
}

function deltaLabel(diff: number | null): string {
  if (diff === null) return ''
  if (diff === 0) return '持平'
  return diff > 0 ? `↑ ${Math.abs(diff)}` : `↓ ${Math.abs(diff)}`
}
const styleLine = computed(() => evaluation.value?.styleTags?.join(' · ') ?? '')

onMounted(async () => {
  try {
    const response = await api.get<ApiEnvelope<Evaluation>>(`/evaluations/${route.params.id}`)
    const sessionResponse = await api.get<ApiEnvelope<TrainingSession>>(`/training-sessions/${String(route.params.id)}`).catch(() => null)
    if (sessionResponse) {
      session.value = sessionResponse.data.data
      messages.value = sessionResponse.data.data.messages
    }
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
      <div class="report-actions">
        <button type="button" class="button secondary" @click="exportPdf">打印 / 导出 PDF</button>
        <RouterLink class="button secondary" :to="{ name: 'stories', query: { sessionId: route.params.id } }">沉淀为故事</RouterLink>
        <RouterLink class="button secondary" to="/scenes">再练一个场景</RouterLink>
      </div>
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
          <p v-if="overallDelta !== null" class="overall-delta" :class="{ up: overallDelta > 0, down: overallDelta < 0 }">
            {{ overallDelta === 0 ? '与上次持平' : overallDelta > 0 ? `比上次高 ${overallDelta} 分` : `比上次低 ${Math.abs(overallDelta)} 分` }}
          </p>
          <p v-if="styleLine" class="style-line">{{ styleLine }}</p>
          <p v-if="evaluation.degraded" class="degraded">本报告由本地评分规则生成，未使用大模型语义评分。</p>
        </div>

        <div class="radar"><ScoreRadar :scores="evaluation.scores" /></div>

        <ul class="dims">
          <li v-for="([key, value], index) in orderedScores" :key="key" :class="{ weakest: value === weakestScore }">
            <span class="name">{{ labels[key] }}</span>
            <span class="bar"><b :style="{ '--w': `${value * 20}%`, animationDelay: `${index * 85}ms` }" /></span>
            <span class="val num">
              {{ value.toFixed(1) }}
              <i v-if="deltaOf(key) !== null" class="delta num" :class="{ up: (deltaOf(key) ?? 0) > 0, down: (deltaOf(key) ?? 0) < 0 }">{{ deltaLabel(deltaOf(key)) }}</i>
            </span>
          </li>
        </ul>
      </section>

      <section class="summary">
        <p class="label">教练总评</p>
        <p class="summary-text">{{ evaluation.summary }}</p>
      </section>

      <ScoreEvidencePanel :evaluation="evaluation" />

      <section v-if="rounds.length" class="replay">
        <header class="replay-head">
          <h2>对话回放</h2>
          <span>{{ rounds.length }} 轮 · 有批注的轮次已标记</span>
        </header>
        <ol class="replay-list">
          <li v-for="round in rounds" :key="round.roundNo" class="replay-item" :class="{ flagged: round.annotated || round.flags.length }">
            <span class="replay-no num">第 {{ round.roundNo }} 轮</span>
            <div class="replay-body">
              <p class="replay-q">{{ round.question }}</p>
              <p class="replay-a">{{ round.answer }}</p>
              <p v-if="round.flags.length" class="replay-flags">表达提醒：{{ round.flags.join('、') }}</p>
            </div>
          </li>
        </ol>
      </section>

      <section v-if="evaluation.speechStats" class="speech panel">
        <header class="speech-head"><h2>表达习惯</h2><span>基于本场全部回答的文本统计</span></header>
        <dl class="speech-grid">
          <div><dt>口头禅</dt><dd class="num">{{ evaluation.speechStats.fillerTotal }}<small>次</small></dd></div>
          <div><dt>占比</dt><dd class="num">{{ Math.round(evaluation.speechStats.fillerRate * 100) }}<small>%</small></dd></div>
          <div><dt>平均句长</dt><dd class="num">{{ evaluation.speechStats.avgSentenceLength }}<small>字</small></dd></div>
          <div><dt>每轮平均</dt><dd class="num">{{ evaluation.speechStats.avgRoundLength }}<small>字</small></dd></div>
        </dl>
        <p v-if="evaluation.speechStats.topFillers.length" class="speech-tags">
          <span v-for="item in evaluation.speechStats.topFillers" :key="item.word">{{ item.word }} ×{{ item.count }}</span>
        </p>
      </section>

      <section v-if="deliveryStats" class="speech panel">
        <header class="speech-head"><h2>表达节奏</h2><span>基于本场语音的停顿与语速分析</span></header>
        <dl class="speech-grid">
          <div><dt>语速</dt><dd class="num">{{ deliveryStats.speechRate }}<small>字/分</small></dd></div>
          <div><dt>净语速</dt><dd class="num">{{ deliveryStats.articulationRate }}<small>字/分</small></dd></div>
          <div><dt>停顿</dt><dd class="num">{{ deliveryStats.pauseCount }}<small>次</small></dd></div>
          <div><dt>最长停顿</dt><dd class="num">{{ deliveryStats.longestPause }}<small>秒</small></dd></div>
        </dl>
        <p v-if="deliveryAdvice.length" class="delivery-advice">
          <span v-for="tip in deliveryAdvice" :key="tip">{{ tip }}</span>
        </p>
        <p class="speech-tags">
          <span class="tag">开口 {{ deliveryStats.durationSeconds }} 秒</span>
          <span class="tag">说话 {{ deliveryStats.charCount }} 字</span>
          <span v-if="deliveryStats.fillerTotal" class="tag">填充词 {{ deliveryStats.fillerTotal }} 次</span>
        </p>
      </section>

      <section v-if="session?.jobMatch" class="speech panel">
        <header class="speech-head">
          <h2>岗位匹配</h2>
          <span>{{ session.jobMatch.score }} / 100 · {{ session.jobMatch.degraded ? '规则估算' : '按 JD 与简历对比' }}</span>
        </header>
        <ul v-if="session.jobMatch.strengths.length" class="match-list">
          <li v-for="item in session.jobMatch.strengths" :key="item"><b>优势</b>{{ item }}</li>
        </ul>
        <ul v-if="session.jobMatch.gaps.length" class="match-list">
          <li v-for="gap in session.jobMatch.gaps" :key="gap.requirement">
            <b>缺口</b>{{ gap.requirement }} — {{ gap.why }}
            <em>{{ gap.drill }}</em>
          </li>
        </ul>
      </section>

      <section v-if="comparison" class="compare panel">
        <header class="speech-head"><h2>与上次对比</h2><span>同一场景的历史最好成绩</span></header>
        <div class="compare-body">
          <div class="compare-radars">
            <div class="compare-radar">
              <p class="compare-label">上次 {{ comparison.beforeOverall }} 分</p>
              <ScoreRadar :scores="comparison.before" />
            </div>
            <div class="compare-radar">
              <p class="compare-label now">本次 {{ comparison.afterOverall }} 分</p>
              <ScoreRadar :scores="comparison.after" />
            </div>
          </div>
          <ul class="compare-rows">
            <li v-for="row in comparison.rows" :key="row.key">
              <span class="label">{{ row.label }}</span>
              <span class="num">{{ row.before }} → {{ row.after }}</span>
              <span class="delta" :class="{ up: row.delta > 0, down: row.delta < 0 }">{{ row.delta > 0 ? '+' + row.delta : row.delta }}</span>
            </li>
          </ul>
        </div>
      </section>

      <section v-if="session?.recordingUrl" class="speech panel">
        <header class="speech-head">
          <h2>现场回放</h2>
          <span>{{ session.channel === 'VIDEO' ? '视频面试录像' : '语音对练录音' }}</span>
        </header>
        <video v-if="session.channel === 'VIDEO'" :src="session.recordingUrl" controls playsinline class="replay-media" />
        <audio v-else :src="session.recordingUrl" controls class="replay-media" />
        <div v-if="replayMarks.length" class="mark-row">
          <button v-for="(mark, index) in replayMarks" :key="index" type="button" @click="replaySeek(mark.start)">
            {{ String(index + 1).padStart(2, '0') }} {{ mark.text }}
          </button>
        </div>
      </section>

      <section v-if="visionStats" class="speech panel">
        <header class="speech-head"><h2>镜头表现</h2><span>画面里的客观指标，不评价长相</span></header>
        <dl class="speech-grid">
          <div><dt>出镜率</dt><dd class="num">{{ Math.round(visionStats.faceRatio * 100) }}<small>%</small></dd></div>
          <div><dt>看镜头</dt><dd class="num">{{ Math.round(visionStats.eyeContactRatio * 100) }}<small>%</small></dd></div>
          <div><dt>头部稳定</dt><dd class="num">{{ Math.round(visionStats.headStability * 100) }}<small>%</small></dd></div>
          <div><dt>画面亮度</dt><dd class="num">{{ Math.round(visionStats.brightness) }}<small>/255</small></dd></div>
        </dl>
        <p v-if="visionStats.tips?.length" class="delivery-advice">
          <span v-for="tip in visionStats.tips" :key="tip">{{ tip }}</span>
        </p>
      </section>

      <section v-if="upgradeStats.total" class="speech panel">
        <header class="speech-head">
          <h2>措辞升级</h2>
          <span>{{ upgradeStats.total }} 处 · {{ upgradeStats.types.join(' / ') }}</span>
        </header>
        <ul class="upgrade-list">
          <li v-for="(item, index) in evaluation.upgrades" :key="index">
            <span class="type">{{ item.type }}</span>
            <p class="origin">原句：{{ item.original }}</p>
            <p class="problem">{{ item.problem }}</p>
            <p class="improved">改后：{{ item.improved }}</p>
          </li>
        </ul>
      </section>

      <section v-if="evaluation.reference && !evaluation.reference.startsWith('（规则兜底')" class="speech panel">
        <header class="speech-head"><h2>满分回答参考</h2><span>保留你的真实事实，不编造经历</span></header>
        <p class="reference-text">{{ evaluation.reference }}</p>
      </section>

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
              <div v-if="suggestion.reference" class="quote reference">
                <span>满分回答</span>
                <p>{{ suggestion.reference }}</p>
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
  background: var(--panel-bg);
}
.score { display: flex; flex-direction: column; }
.overall-delta { margin: 8px 0 0; color: var(--text-3); font-size: 12px; }
.overall-delta.up { color: var(--success); }
.overall-delta.down { color: var(--danger); }
.delta { color: var(--text-3); font-size: 10px; font-style: normal; margin-left: 4px; }
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
  grid-template-columns: 64px minmax(0, 1fr) 58px;
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

.speech { margin-top: 42px; padding: 22px 24px; }
.speech-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.speech-head h2 { margin: 0; font-size: 13px; font-weight: 500; color: var(--text-2); letter-spacing: .04em; }
.speech-head span { color: var(--text-3); font-size: 11px; }
.speech-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 20px; margin: 18px 0 0; }
.speech-grid dt { color: var(--text-3); font-size: 11px; letter-spacing: .12em; }
.speech-grid dd { margin: 8px 0 0; color: var(--text); font-size: 22px; font-weight: 300; font-family: var(--font-num); }
.speech-grid small { margin-left: 4px; color: var(--text-3); font-size: 11px; }
.delivery-advice { margin: 6px 0 0; display: grid; gap: 6px; color: var(--text-2); font-size: 12.5px; line-height: 1.7; }
.speech-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 0; }
.speech-tags span { padding: 3px 8px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-2); font-size: 11.5px; }
.replay { margin-top: 42px; }
.replay-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--divider); }
.replay-head h2 { margin: 0; color: var(--text); font-size: 14px; font-weight: 500; }
.replay-head span { color: var(--text-3); font-size: 11px; }
.replay-list { margin: 0; padding: 0; list-style: none; }
.replay-item { display: grid; grid-template-columns: 62px minmax(0,1fr); gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--divider); }
.replay-no { color: var(--text-3); font-size: 11px; padding-top: 2px; }
.replay-item.flagged .replay-no { color: var(--accent-strong); }
.replay-q { margin: 0; color: var(--text-2); font-size: 12.5px; line-height: 1.8; }
.replay-a { margin: 6px 0 0; color: var(--text); font-size: 13px; line-height: 1.9; white-space: pre-wrap; }
.replay-item.flagged .replay-a { border-left: 2px solid var(--accent); padding-left: 10px; margin-left: -12px; }
.replay-flags { margin: 6px 0 0; color: var(--warning); font-size: 11px; }
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
.quote.reference { grid-column: 1 / -1; border-left: 2px solid var(--accent); }
.quote.reference span { color: var(--accent-strong); }
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
.dims .delta.up { color: var(--success); }
.dims .delta.down { color: var(--danger); }
.delta.num { font-size: 11px; }

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
.stability-note { margin: 8px 0 0; color: var(--text-3); font-size: 12px; }
.reference-text { margin: 8px 0 0; color: var(--text-2); line-height: 1.9; font-size: 13.5px; }
.replay-media { width: 100%; margin-top: 6px; border-radius: 10px; }
.mark-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.mark-row button { padding: 5px 11px; border: 1px solid var(--border); border-radius: 999px; background: var(--bg-2); color: var(--text-2); font-size: 12px; cursor: pointer; }
.mark-row button:hover { border-color: var(--accent); color: var(--accent-strong); }

.report-actions { display: flex; gap: 10px; }
.upgrade-list { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 12px; }
.upgrade-list li { padding: 12px 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--bg-2); display: grid; gap: 4px; }
.upgrade-list .type { width: fit-content; padding: 2px 9px; border: 1px solid var(--accent); border-radius: 999px; color: var(--accent-strong); font-size: 11px; }
.upgrade-list p { margin: 0; font-size: 12.5px; line-height: 1.75; }
.upgrade-list .origin { color: var(--text-3); }
.upgrade-list .problem { color: #a4342a; }
.upgrade-list .improved { color: var(--text); }
.match-list { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 8px; }
.match-list li { color: var(--text-2); font-size: 12.5px; line-height: 1.8; }
.match-list b { margin-right: 8px; color: var(--text-3); font-weight: 500; font-size: 11.5px; }
.match-list em { display: block; color: var(--accent-strong); font-style: normal; font-size: 12px; }
.compare.panel { display: grid; grid-template-columns: 1fr; padding: 22px; }
.compare-body { display: grid; gap: 20px; width: 100%; }
.compare-radars { display: flex; justify-content: center; gap: 120px; flex-wrap: wrap; }
.compare-radar { width: 240px; text-align: center; }
.compare-label { margin: 0 0 4px; color: var(--text-3); font-size: 12px; }
.compare-label.now { color: var(--accent-strong); font-weight: 600; }
.compare-rows { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; width: fit-content; margin-inline: auto; }
.compare-rows li { display: grid; grid-template-columns: 84px 92px 40px; align-items: center; gap: 14px; font-size: 12.5px; }
.compare-rows .label { color: var(--text-3); }
.compare-rows .delta { text-align: right; color: var(--text-3); }
.compare-rows .delta.up { color: var(--success); }
.compare-rows .delta.down { color: var(--danger); }
@media (max-width: 900px) { .compare-radars { gap: 12px; } .compare-radar { width: 45%; } }
@media print {
  .app-shell aside, .app-shell header, .report-actions, .mark-row, .replay-media,
  .speech.panel:has(.mark-row), button { display: none !important; }
  .page, .report { padding: 0 !important; max-width: none !important; }
  .panel { break-inside: avoid; box-shadow: none !important; border-color: #ccc !important; }
}
</style>
