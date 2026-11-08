<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

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

// ③ 表达指标时间轴：停顿点落在录音的哪一秒，点击可跳转
const speechDuration = computed(() => {
  const raw = session.value?.delivery
  return Math.max(1, Math.round(session.value?.durationSeconds ?? raw?.durationSeconds ?? 0))
})

const pauseMarks = computed(() => {
  const pauses = (session.value?.delivery as unknown as { pauses?: Array<{ start: number; end: number; seconds: number }> } | undefined)?.pauses ?? []
  return pauses
    .filter((item) => item.seconds >= 0.6)
    .slice(0, 12)
    .map((item) => ({ ...item, percent: Math.min(100, (item.start / speechDuration.value) * 100) }))
})

// 同题横向对比：这道题以前怎么答的
interface SameQuestionAttempt { sessionId: string; startedAt: string; isCurrent: boolean; question: string; answer: string; overallScore: number | null; channel: string }
const attempts = shallowRef<Record<number, SameQuestionAttempt[]>>({})
const attemptsLoading = shallowRef<number | null>(null)

async function loadAttempts(roundNo: number): Promise<void> {
  if (attemptsLoading.value !== null) return
  attemptsLoading.value = roundNo
  try {
    const response = await api.get<ApiEnvelope<{ attempts: SameQuestionAttempt[] }>>(
      `/training-sessions/${route.params.id}/same-question/${roundNo}`,
    )
    attempts.value = { ...attempts.value, [roundNo]: response.data.data.attempts }
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    attemptsLoading.value = null
  }
}

// ① 行动计划：把报告里散落的建议压成三件事
interface PlannedAction { title: string; detail: string; label: string; to: RouteLocationRaw }
const weeklyActions = computed<PlannedAction[]>(() => {
  const current = evaluation.value
  if (!current) return []
  const actions: PlannedAction[] = []
  const weakest = [...DIMS].sort((a, b) => (current.scores[a] ?? 0) - (current.scores[b] ?? 0))[0]
  const evidence = current.evidence.find((item) => item.dimension === weakest)
  if (evidence) {
    actions.push({
      title: `先把「${labels[weakest]}」这一维拉起来`,
      detail: evidence.nextAction || evidence.reason || '按证据里的问题重写这一轮回答。',
      label: '去改这句',
      to: {
        name: 'scripts',
        query: {
          sceneId: session.value?.sceneId ?? '',
          original: evidence.quote,
          dimension: labels[weakest],
          objective: evidence.reason ?? '',
        },
      },
    })
  }
  const filler = current.speechStats?.topFillers?.[0]
  if (filler) {
    actions.push({
      title: `这次只砍一个口头禅：「${filler.word}」`,
      detail: `本场出现 ${filler.count} 次。下一场刻意停顿 0.5 秒代替「${filler.word}」，比硬背稿有效。`,
      label: '再练一场',
      to: { name: 'scenes', query: { sceneId: session.value?.sceneId ?? '' } },
    })
  }
  const upgrade = current.upgrades?.[0]
  if (upgrade) {
    actions.push({
      title: '把一句空话换成一个具体结果',
      detail: `${upgrade.problem.replace(/。$/, '')}：${upgrade.original} → ${upgrade.improved}`,
      label: '看全部改写',
      to: { name: 'scripts', query: { sceneId: session.value?.sceneId ?? '', original: upgrade.original } },
    })
  }
  return actions.slice(0, 3)
})

// ② 逐题考察点：这一轮问的是什么维度、得分多少、证据里缺什么
function roundRubric(roundNo: number): { dimension: string; score: number; note: string } | null {
  const current = evaluation.value
  if (!current) return null
  const planned = session.value?.questionPlan?.[roundNo - 1]
  const evidence = current.evidence.find((item) => item.roundNo === roundNo)
  if (!planned && !evidence) return null
  const key = (evidence?.dimension ?? planned?.dimension ?? '') as keyof Scores
  const dimension = labels[key] ?? evidence?.dimension ?? planned?.dimension ?? '综合表达'
  return {
    dimension,
    score: key in labels ? current.scores[key] : 0,
    note: evidence?.reason ?? '',
  }
}

const labels: Record<keyof Scores, string> = { logic: '内容与逻辑', relevance: '贴合问题', correctness: '信息完整', concision: '表达干净' }

const DIMS: Array<keyof Scores> = ['logic', 'relevance', 'correctness', 'concision']

const rescoring = shallowRef(false)

async function rescore(): Promise<void> {
  if (rescoring.value) return
  rescoring.value = true
  try {
    await api.post(`/evaluations/${route.params.id}?force=true`)
    await loadReport()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    rescoring.value = false
  }
}

// T-04：逐题 STAR 完整度（启发式，只做提示，不参与评分）
const STAR_PATTERNS: Array<[keyof StarCoverage, RegExp]> = [
  ['situation', /(当时|背景|项目|公司|团队|客户|业务|系统|平台|产品|部门|实习|学校|课程|比赛)/],
  ['task', /(负责|目标|需要|任务|要求|挑战|要解决|被安排|承担)/],
  ['action', /(我(先|做|通过|主导|设计|搭建|负责|改成|调整)|首先|然后|接着|于是|具体|办法|方案|优化|协调|排查|推进)/],
  ['result', /(结果|提升|降低|下降|完成|达成|最终|上线|节省|效率|从.{0,12}(到|降|升)|\d+\s*(%|倍|万|千|ms|秒|天|人))/],
]

interface StarCoverage { situation: boolean; task: boolean; action: boolean; result: boolean }

function starOf(answer: string): StarCoverage {
  return {
    situation: STAR_PATTERNS[0][1].test(answer),
    task: STAR_PATTERNS[1][1].test(answer),
    action: STAR_PATTERNS[2][1].test(answer),
    result: STAR_PATTERNS[3][1].test(answer),
  }
}

function starScore(coverage: StarCoverage): number {
  return Object.values(coverage).filter(Boolean).length
}

function starHint(answer: string): string {
  const coverage = starOf(answer)
  const missing = [
    coverage.situation ? '' : '情境',
    coverage.task ? '' : '任务',
    coverage.action ? '' : '行动',
    coverage.result ? '' : '结果',
  ].filter(Boolean)
  return missing.length ? `缺${missing.join('、')}` : '四要素齐全'
}

// 教练查看链接（只读 + 时间点批注）
const shareLink = shallowRef('')
const shareBusy = shallowRef(false)

async function createShareLink(): Promise<void> {
  if (!session.value || shareBusy.value) return
  shareBusy.value = true
  try {
    const response = await api.post<ApiEnvelope<{ url: string; expiresAt: number }>>(`/share/training-sessions/${session.value.id}`)
    shareLink.value = `${location.origin}${response.data.data.url}`
    await navigator.clipboard?.writeText(shareLink.value).catch(() => undefined)
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    shareBusy.value = false
  }
}

// V-04：同场景两次录像并排对比
const compareSession = shallowRef<TrainingSession | null>(null)
const compareScore = shallowRef<number | null>(null)

async function loadCompare(): Promise<void> {
  const current = session.value
  if (!current?.recordingUrl) return
  try {
    const response = await api.get<ApiEnvelope<{ items?: TrainingSession[] } | TrainingSession[]>>('/training-sessions', { params: { size: 40 } })
    const payload = response.data.data
    const list = Array.isArray(payload) ? payload : (payload.items ?? [])
    const previous = list.find((item) => item.id !== current.id
      && item.sceneId === current.sceneId
      && item.channel === current.channel
      && Boolean(item.recordingUrl))
    if (!previous) return
    compareSession.value = previous
    const score = await api.get<ApiEnvelope<Evaluation>>(`/evaluations/${previous.id}`).catch(() => null)
    compareScore.value = score ? score.data.data.overallScore : null
  } catch {
    // 对比是增强信息，取不到不影响报告
  }
}

// V-03：按题分段的录像片段
const segments = computed(() => session.value?.delivery?.segments ?? [])
const activeSegment = shallowRef(0)

function playSegment(index: number): void {
  activeSegment.value = index
  const player = document.querySelector<HTMLVideoElement>('.segment-player video')
  if (player) {
    player.load()
    void player.play().catch(() => undefined)
  }
}

// A-02：人工修正转写（视频/语音场次）
const editingRound = shallowRef<number | null>(null)
const editingText = shallowRef('')
const transcriptSaving = shallowRef(false)
const transcript = computed(() => session.value?.delivery?.transcript ?? [])
const needsRescore = computed(() => Boolean(session.value?.delivery?.rescoreRequired))

function startEdit(roundNo: number, text: string): void {
  editingRound.value = roundNo
  editingText.value = text
}

async function saveTranscript(roundNo: number): Promise<void> {
  if (!session.value || transcriptSaving.value) return
  transcriptSaving.value = true
  try {
    await api.patch(`/training-sessions/${session.value.id}/transcript/${roundNo}`, { text: editingText.value.trim() })
    editingRound.value = null
    await loadReport()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    transcriptSaving.value = false
  }
}

function confidenceLabel(value: number | null): string {
  if (value === null || value === undefined) return '未提供置信度'
  if (value < 0.7) return `置信度 ${Math.round(value * 100)}% · 建议核对`
  return `置信度 ${Math.round(value * 100)}%`
}

// V-06：视频逐题自评（镜头位置 / 信息组织 / 开场收尾）
interface SelfReviewEntry { roundNo: number; camera: boolean; structure: boolean; opening: boolean; note: string }
const selfReview = shallowRef<SelfReviewEntry[]>([])
const reviewSaved = shallowRef(false)
const reviewSaving = shallowRef(false)

function initSelfReview(): void {
  const marks = session.value?.delivery?.marks ?? []
  const saved = new Map((session.value?.delivery?.selfReview ?? []).map((item) => [item.roundNo, item]))
  const source = marks.length ? marks.map((mark, index) => ({ roundNo: index + 1, text: mark.text })) : rounds.value.map((round) => ({ roundNo: round.roundNo, text: round.question }))
  selfReview.value = source.map((item) => {
    const existing = saved.get(item.roundNo)
    return {
      roundNo: item.roundNo,
      camera: existing?.camera ?? false,
      structure: existing?.structure ?? false,
      opening: existing?.opening ?? false,
      note: existing?.note ?? '',
    }
  })
}

async function saveSelfReview(): Promise<void> {
  if (!session.value || reviewSaving.value) return
  reviewSaving.value = true
  try {
    await api.put(`/training-sessions/${session.value.id}/self-review`, { items: selfReview.value })
    reviewSaved.value = true
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    reviewSaving.value = false
  }
}

watch(session, () => initSelfReview())

const orderedScores = computed(() => evaluation.value
  ? DIMS.map((key) => [key, Number(evaluation.value!.scores[key]) || 0] as [keyof Scores, number])
    .sort((a, b) => b[1] - a[1])
  : [])
const weakestScore = computed(() => (orderedScores.value.length ? orderedScores.value[orderedScores.value.length - 1][1] : 0))

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

async function loadReport(): Promise<void> {
  const response = await api.get<ApiEnvelope<Evaluation>>(`/evaluations/${route.params.id}`)
  const sessionResponse = await api.get<ApiEnvelope<TrainingSession>>(`/training-sessions/${String(route.params.id)}`).catch(() => null)
  if (sessionResponse) {
    session.value = sessionResponse.data.data
    messages.value = sessionResponse.data.data.messages
  }
  evaluation.value = response.data.data
}

onMounted(async () => {
  try {
    await loadReport()
    await loadCompare()
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
        <button class="button secondary" type="button" :disabled="shareBusy" @click="createShareLink">
          {{ shareBusy ? '生成中…' : shareLink ? '链接已复制' : '生成教练链接' }}
        </button>
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
          <p v-if="evaluation.degraded" class="degraded">
            本报告由本地评分规则生成，未使用大模型语义评分。
            <button class="rescore" type="button" :disabled="rescoring" @click="rescore">
              {{ rescoring ? '重新评分中…' : '重新用大模型评分' }}
            </button>
          </p>
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

      <section v-if="weeklyActions.length" class="actions-card panel">
        <header><h2>接下来只做三件事</h2><span>按顺序做，别一次改所有问题</span></header>
        <ol>
          <li v-for="(action, index) in weeklyActions" :key="action.title">
            <span class="action-no num">0{{ index + 1 }}</span>
            <div>
              <strong>{{ action.title }}</strong>
              <p>{{ action.detail }}</p>
            </div>
            <RouterLink class="button secondary compact" :to="action.to">{{ action.label }}</RouterLink>
          </li>
        </ol>
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
              <p v-if="roundRubric(round.roundNo)" class="rubric-line">
                <span class="rubric-dim">考察 · {{ roundRubric(round.roundNo)?.dimension }}</span>
                <span v-if="roundRubric(round.roundNo)?.score" class="rubric-score">{{ roundRubric(round.roundNo)?.score }} / 5</span>
                <span v-if="roundRubric(round.roundNo)?.note" class="rubric-note">{{ roundRubric(round.roundNo)?.note }}</span>
              </p>
              <div class="star-row" :class="`star-${starScore(starOf(round.answer))}`">
                <span class="star-label">STAR {{ starScore(starOf(round.answer)) }}/4</span>
                <span v-for="key in (['situation','task','action','result'] as const)" :key="key" class="star-dot" :class="{ on: starOf(round.answer)[key] }">
                  {{ { situation: 'S', task: 'T', action: 'A', result: 'R' }[key] }}
                </span>
                <span class="star-hint">{{ starHint(round.answer) }}</span>
              </div>
              <p v-if="round.flags.length" class="replay-flags">表达提醒：{{ round.flags.join('、') }}</p>
              <div class="attempt-row">
                <button type="button" class="mini" :disabled="attemptsLoading === round.roundNo" @click="loadAttempts(round.roundNo)">
                  {{ attemptsLoading === round.roundNo ? '查找中…' : attempts[round.roundNo] ? '重新对比' : '同题对比' }}
                </button>
                <span v-if="attempts[round.roundNo]" class="attempt-hint">
                  {{ attempts[round.roundNo].length ? `共 ${attempts[round.roundNo].length} 次历史作答` : '还没有历史作答' }}
                </span>
              </div>
              <div v-if="attempts[round.roundNo]" class="attempt-list">
                <article v-for="attempt in attempts[round.roundNo]" :key="attempt.sessionId + attempt.startedAt" class="attempt-item" :class="{ current: attempt.isCurrent }">
                  <header>
                    <span>{{ new Date(attempt.startedAt).toLocaleDateString('zh-CN') }}</span>
                    <span v-if="attempt.isCurrent" class="tag">本次</span>
                    <strong v-if="attempt.overallScore !== null" class="num">{{ attempt.overallScore }} 分</strong>
                    <span class="star-label">STAR {{ starScore(starOf(attempt.answer)) }}/4</span>
                  </header>
                  <p>{{ attempt.answer }}</p>
                  <p class="attempt-missing">{{ starHint(attempt.answer) }} · {{ attempt.answer.length }} 字</p>
                </article>
              </div>
            </div>
          </li>
        </ol>
      </section>

      <section v-if="shareLink" class="share-note panel">
        <h2>教练查看链接</h2>
        <p>链接 7 天内有效，只能查看这份报告、录像与转写，并可添加时间点批注；不能修改评分。</p>
        <code>{{ shareLink }}</code>
      </section>

      <section v-if="session?.recordingUrl && compareSession?.recordingUrl" class="compare-video panel">
        <header>
          <h2>两次录像对比</h2>
          <span>同一场景 · 左为最近一次，右为上一次</span>
        </header>
        <div class="compare-grid">
          <figure>
            <video :src="session.recordingUrl ?? undefined" controls playsinline preload="metadata" />
            <figcaption>
              <b>本次 {{ evaluation?.overallScore ?? '—' }}</b>
              <span>{{ new Date(session.startedAt).toLocaleDateString('zh-CN') }}</span>
            </figcaption>
          </figure>
          <figure>
            <video :src="compareSession.recordingUrl ?? undefined" controls playsinline preload="metadata" />
            <figcaption>
              <b>上次 {{ compareScore ?? '—' }}</b>
              <span>{{ new Date(compareSession.startedAt).toLocaleDateString('zh-CN') }}</span>
            </figcaption>
          </figure>
        </div>
      </section>

      <section v-if="segments.length" class="segments panel">
        <header><h2>按题回看</h2><span>每段只包含该题的回答，可逐题复盘</span></header>
        <ol class="segment-tabs">
          <li v-for="(segment, index) in segments" :key="segment.roundNo">
            <button type="button" :class="{ active: index === activeSegment }" @click="playSegment(index)">
              第 {{ segment.roundNo }} 题
            </button>
          </li>
        </ol>
        <div class="segment-player">
          <video :src="segments[activeSegment]?.url ?? undefined" controls playsinline preload="metadata" />
          <p>{{ segments[activeSegment]?.question }}</p>
        </div>
      </section>

      <section v-if="transcript.length" class="transcript panel">
        <header>
          <h2>转写文本</h2>
          <span>识别有误可以手动改，改完需要重新评分</span>
        </header>
        <p v-if="needsRescore" class="rescore-tip">
          转写已修改，当前报告基于旧文本。
          <button type="button" class="rescore" :disabled="rescoring" @click="rescore">{{ rescoring ? '重新评分中…' : '用新文本重新评分' }}</button>
        </p>
        <ul>
          <li v-for="item in transcript" :key="item.roundNo">
            <div class="tr-head">
              <span class="num">第 {{ item.roundNo }} 轮</span>
              <span class="tr-conf" :class="{ low: item.confidence !== null && item.confidence < 0.7 }">{{ confidenceLabel(item.confidence) }}</span>
              <button v-if="editingRound !== item.roundNo" type="button" class="mini" @click="startEdit(item.roundNo, item.text)">修正</button>
            </div>
            <p class="tr-q">{{ item.question }}</p>
            <template v-if="editingRound === item.roundNo">
              <textarea v-model="editingText" class="field" rows="3" maxlength="2000" />
              <div class="tr-actions">
                <button class="button" type="button" :disabled="transcriptSaving" @click="saveTranscript(item.roundNo)">{{ transcriptSaving ? '保存中…' : '保存修正' }}</button>
                <button class="button secondary" type="button" @click="editingRound = null">取消</button>
              </div>
            </template>
            <p v-else class="tr-text">{{ item.text }}<span v-if="item.edited" class="tr-edited">已人工修正</span></p>
          </li>
        </ul>
      </section>

      <section v-if="session?.channel === 'VIDEO' && selfReview.length" class="self-review panel">
        <header><h2>逐题自评</h2><span>回看录像后勾选，指标会随报告保存</span></header>
        <ul>
          <li v-for="item in selfReview" :key="item.roundNo">
            <span class="num">第 {{ item.roundNo }} 题</span>
            <label><input v-model="item.camera" type="checkbox" /> 镜头位置合适</label>
            <label><input v-model="item.structure" type="checkbox" /> 信息有结构</label>
            <label><input v-model="item.opening" type="checkbox" /> 开场与收尾清楚</label>
            <input v-model="item.note" class="field note" maxlength="200" placeholder="补充一句（可选）" />
          </li>
        </ul>
        <button class="button secondary" type="button" :disabled="reviewSaving" @click="saveSelfReview">
          {{ reviewSaving ? '保存中…' : reviewSaved ? '已保存 ✓ 再保存一次' : '保存自评' }}
        </button>
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
        <div v-if="pauseMarks.length && session?.recordingUrl" class="pause-timeline">
          <div class="timeline-head">
            <span>停顿分布</span>
            <span>{{ pauseMarks.length }} 处 ≥ 0.6 秒 · 点击跳到录音位置</span>
          </div>
          <div class="timeline-track">
            <i
              v-for="(mark, index) in pauseMarks"
              :key="index"
              class="pause-mark"
              :style="{ left: `${mark.percent}%`, height: `${Math.min(22, 8 + mark.seconds * 4)}px` }"
              :title="`${mark.start.toFixed(1)}s 停顿 ${mark.seconds.toFixed(1)}s`"
              @click="replaySeek(mark.start)"
            />
          </div>
          <div class="timeline-scale"><span>0s</span><span>{{ speechDuration }}s</span></div>
        </div>
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
            <RouterLink class="deep-link" :to="{ name: 'scripts', query: { sceneId: session?.sceneId, original: item.original, dimension: item.type, objective: item.problem } }">在话术优化里深入改写 →</RouterLink>
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
.rescore { margin-left: 8px; padding: 2px 10px; border: 1px solid var(--border-bright); border-radius: 999px; background: transparent; color: var(--text-2); font-size: 11px; cursor: pointer; }
.rescore:hover:not(:disabled) { border-color: var(--accent); color: var(--accent-strong); }

.radar { display: flex; justify-content: center; }

.dims { display: flex; flex-direction: column; margin: 0; padding: 0; list-style: none; }
.dims .val { display: inline-flex; align-items: baseline; justify-content: flex-end; gap: 3px; white-space: nowrap; }
.dims li {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) 66px;
  align-items: center;
  gap: 16px;
  padding: 9px 0;
  border-bottom: 1px solid var(--divider);
}
.dims li:last-child { border-bottom: 0; }
.dims .name { color: var(--text-3); font-size: 12px; letter-spacing: .04em; white-space: nowrap; }
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
.upgrade-list .deep-link { margin-top: 4px; width: fit-content; color: var(--accent-strong); font-size: 12px; }
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

.star-row { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
.star-label { color: var(--text-3); font-size: 11px; letter-spacing: .04em; }
.star-dot { display: inline-grid; place-items: center; width: 18px; height: 18px; border: 1px solid var(--border); border-radius: 50%; color: var(--text-3); font-size: 10px; }
.star-dot.on { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.star-hint { color: var(--text-3); font-size: 11px; }

.self-review header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.self-review h2 { margin: 0; }
.self-review header span { color: var(--text-3); font-size: 11.5px; }
.self-review ul { list-style: none; margin: 14px 0; padding: 0; display: grid; gap: 10px; }
.self-review li { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; }
.self-review li .num { color: var(--text-3); font-size: 11.5px; }
.self-review label { display: inline-flex; align-items: center; gap: 5px; color: var(--text-2); font-size: 12px; }
.self-review .note { margin-left: auto; min-width: 180px; max-width: 260px; }

.transcript header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.transcript header span { color: var(--text-3); font-size: 11.5px; }
.transcript ul { list-style: none; margin: 12px 0 0; padding: 0; display: grid; gap: 12px; }
.transcript li { padding: 12px 14px; border: 1px solid var(--border); border-radius: 8px; }
.tr-head { display: flex; align-items: center; gap: 10px; }
.tr-head .num { color: var(--text-3); font-size: 11.5px; }
.tr-conf { margin-left: auto; color: var(--text-3); font-size: 11px; }
.tr-conf.low { color: var(--error, #b4553f); }
.tr-q { margin: 8px 0 4px; color: var(--text-3); font-size: 12px; }
.tr-text { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
.tr-edited { margin-left: 8px; color: var(--accent-strong); font-size: 11px; }
.tr-actions { display: flex; gap: 8px; margin-top: 8px; }
.mini { padding: 2px 8px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-2); font-size: 11px; cursor: pointer; }
.rescore-tip { margin: 10px 0 0; color: var(--warning); font-size: 12px; }

.segments header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.segments header span { color: var(--text-3); font-size: 11.5px; }
.segment-tabs { list-style: none; margin: 12px 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.segment-tabs button { padding: 5px 12px; border: 1px solid var(--border); border-radius: 999px; background: var(--card); color: var(--text-2); font-size: 12px; cursor: pointer; }
.segment-tabs button.active { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.segment-player video { width: 100%; max-height: 46vh; border-radius: 10px; background: #0b0b0e; }
.segment-player p { margin: 8px 0 0; color: var(--text-3); font-size: 12px; }

.compare-video header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.compare-video header span { color: var(--text-3); font-size: 11.5px; }
.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 12px; }
.compare-grid figure { margin: 0; display: grid; gap: 6px; }
.compare-grid video { width: 100%; max-height: 34vh; border-radius: 10px; background: #0b0b0e; }
.compare-grid figcaption { display: flex; align-items: baseline; justify-content: space-between; color: var(--text-3); font-size: 11.5px; }
.compare-grid figcaption b { color: var(--text); font-size: 13px; }
@media (max-width: 720px) { .compare-grid { grid-template-columns: 1fr; } }

.share-note h2 { margin: 0 0 6px; }
.share-note p { margin: 0 0 8px; color: var(--text-3); font-size: 12.5px; line-height: 1.7; }
.share-note code { padding: 6px 10px; border-radius: 6px; background: var(--bg-2); color: var(--text-2); font-size: 12px; word-break: break-all; }
.actions-card header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.actions-card header span { color: var(--text-3); font-size: 11.5px; }
.actions-card ol { list-style: none; margin: 12px 0 0; padding: 0; display: grid; gap: 12px; }
.actions-card li { display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; gap: 12px; align-items: start; padding-top: 12px; border-top: 1px solid var(--divider); }
.actions-card li:first-child { border-top: 0; padding-top: 0; }
.action-no { color: var(--accent-strong); font-size: 12px; padding-top: 2px; }
.actions-card strong { display: block; color: var(--text); font-size: 13.5px; font-weight: 600; }
.actions-card p { margin: 4px 0 0; color: var(--text-2); font-size: 12.5px; line-height: 1.75; }
.rubric-line { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin: 8px 0 0; font-size: 11.5px; }
.rubric-dim { padding: 2px 8px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-2); }
.rubric-score { color: var(--text); font-variant-numeric: tabular-nums; }
.rubric-note { color: var(--text-3); }
.pause-timeline { margin-top: 14px; }
.timeline-head { display: flex; justify-content: space-between; color: var(--text-3); font-size: 11.5px; }
.timeline-track { position: relative; height: 26px; margin: 6px 0 2px; border-radius: 4px; background: linear-gradient(90deg, var(--track), var(--track)); }
.pause-mark { position: absolute; bottom: 2px; width: 3px; border-radius: 2px; background: var(--accent); cursor: pointer; transition: opacity .14s var(--ease); }
.pause-mark:hover { opacity: .65; }
.timeline-scale { display: flex; justify-content: space-between; color: var(--text-3); font-size: 10.5px; }

.attempt-row { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.attempt-hint { color: var(--text-3); font-size: 11px; }
.attempt-list { display: grid; gap: 8px; margin-top: 10px; }
.attempt-item { padding: 10px 12px; border: 1px solid var(--border); border-left: 2px solid var(--border); border-radius: 0 8px 8px 0; background: var(--bg-2); }
.attempt-item.current { border-left-color: var(--accent); }
.attempt-item header { display: flex; align-items: baseline; gap: 10px; color: var(--text-3); font-size: 11px; }
.attempt-item header .tag { padding: 1px 6px; border: 1px solid var(--accent); border-radius: 999px; color: var(--accent-strong); font-size: 10px; }
.attempt-item header strong { margin-left: auto; color: var(--text); font-size: 12.5px; }
.attempt-item p { margin: 6px 0 0; color: var(--text-2); font-size: 12.5px; line-height: 1.75; }
.attempt-item .attempt-missing { color: var(--text-3); font-size: 11px; }
</style>
