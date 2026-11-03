<script setup lang="ts">
import { Play, RefreshCw } from 'lucide-vue-next'
import { computed, onMounted, shallowRef } from 'vue'

import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'

import type { ApiEnvelope, LessonResponse, TrainingPlan, TrainingPlanTask } from '@/lib/types'

const props = defineProps<{
  plan: TrainingPlan
  task: TrainingPlanTask
  submitting: boolean
}>()
const emit = defineEmits<{
  completeStep: [index: number]
  submitPractice: [answer: string]
}>()

const answer = shallowRef(props.task.practiceAnswer ?? '')
const generated = shallowRef<LessonResponse | null>(null)
const lessonGenerating = shallowRef(true)
const videoUrl = shallowRef('')
const videoBuilding = shallowRef(false)
const videoError = shallowRef('')
const videoElapsed = shallowRef(0)
const chapters = shallowRef<Array<{ title: string; start: number; duration: number }>>([])
const videoEl = shallowRef<HTMLVideoElement | null>(null)
const activeChapter = shallowRef(0)
let videoTimer: ReturnType<typeof setInterval> | null = null
const lessonError = shallowRef('')
const lesson = computed(() => generated.value?.lesson ?? props.task.lesson)
const nextStep = computed(() => props.task.completedSteps.length)
const readyToPractice = computed(() => nextStep.value === lesson.value?.steps.length)
const sourcePoints = computed(() =>
  (generated.value?.source.content ?? '')
    .split(/[；;\n]/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 8),
)

const canSubmit = computed(() => readyToPractice.value && answer.value.trim().length >= 40 && !props.submitting)

async function buildVideo(): Promise<void> {
  if (videoBuilding.value) return
  videoBuilding.value = true
  videoError.value = ''
  videoElapsed.value = 0
  videoTimer = setInterval(() => { videoElapsed.value += 1 }, 1000)
  try {
    // 首次渲染需要跑 Remotion，给足 3 分钟
    const response = await api.post<ApiEnvelope<{ url: string }>>(
      `/training-plans/${props.plan.id}/lesson/video`,
      { task_key: 'course' },
      { timeout: 180_000 },
    )
    const payload = response.data.data as { url: string; chapters?: Array<{ title: string; start: number; duration: number }> }
    videoUrl.value = `${(import.meta.env.VITE_API_BASE ?? '/api/v1').replace('/api/v1', '')}${payload.url}`
    chapters.value = payload.chapters ?? []
  } catch (reason) {
    videoError.value = errorMessage(reason)
  } finally {
    videoBuilding.value = false
    if (videoTimer) { clearInterval(videoTimer); videoTimer = null }
  }
}

async function loadLesson(force = false): Promise<void> {
  lessonGenerating.value = true
  lessonError.value = ''
  try {
    const response = await api.post<ApiEnvelope<LessonResponse>>(
      `/training-plans/${props.plan.id}/lesson`,
      { task_key: props.task.key, force },
      { timeout: MODEL_REQUEST_TIMEOUT_MS },
    )
    generated.value = response.data.data
  } catch (reason) {
    lessonError.value = errorMessage(reason)
  } finally {
    lessonGenerating.value = false
  }
}

async function loadCachedVideo(): Promise<void> {
  try {
    const response = await api.get<ApiEnvelope<{ url: string | null; chapters?: Array<{ title: string; start: number; duration: number }> }>>(
      `/training-plans/${props.plan.id}/lesson/video`,
      { params: { task_key: props.task.key } },
    )
    const data = response.data.data
    if (data.url) {
      videoUrl.value = `${(import.meta.env.VITE_API_BASE ?? '/api/v1').replace('/api/v1', '')}${data.url}`
      chapters.value = data.chapters ?? []
    }
  } catch {
    // 查询失败不影响文字课件
  }
}

function seekChapter(index: number): void {
  const chapter = chapters.value[index]
  if (!chapter || !videoEl.value) return
  videoEl.value.currentTime = chapter.start
  activeChapter.value = index
  void videoEl.value.play().catch(() => undefined)
}

function onLoadedMetadata(): void {
  // 让视频停在第一帧，避免封面是空白
  if (videoEl.value && videoEl.value.currentTime === 0) {
    videoEl.value.currentTime = 0.35
  }
}

function onTimeUpdate(): void {
  if (!videoEl.value) return
  const time = videoEl.value.currentTime
  const index = chapters.value.findIndex((chapter, position) => {
    const next = chapters.value[position + 1]
    return time >= chapter.start && (!next || time < next.start)
  })
  if (index >= 0) activeChapter.value = index
}

onMounted(async () => {
  await loadLesson(false)
  await loadCachedVideo()
})
</script>

<template>
  <section v-if="lesson" class="personalized panel" aria-label="个性化沟通微课">
    <div class="lesson-header">
      <div>
        <p class="eyebrow">学习路径 · {{ plan.focusDimension }}</p>
        <h2>{{ lesson.title }}</h2>
        <p>{{ lesson.intro }}</p>
      </div>
      <div class="lesson-tools">
        <span class="source-tag">{{ lesson.aiGenerated ? '基于本次评分生成' : '离线示例课程' }}</span>
        <button class="swap-button" type="button" :disabled="videoBuilding" @click="buildVideo">
          <Play :size="13" :stroke-width="1.8" aria-hidden="true" />
          {{ videoBuilding ? `正在渲染视频 ${videoElapsed}s…` : '看视频版' }}
        </button>
        <button class="swap-button" type="button" :disabled="lessonGenerating" @click="loadLesson(true)">
          <RefreshCw :size="13" :stroke-width="1.8" aria-hidden="true" />
          {{ lessonGenerating ? '生成中…' : '换一门' }}
        </button>
      </div>
    </div>
    <div v-if="videoUrl" class="lesson-video">
      <video ref="videoEl" :src="videoUrl" controls playsinline preload="metadata" @loadedmetadata="onLoadedMetadata" @timeupdate="onTimeUpdate" />
      <div v-if="chapters.length" class="chapters">
        <button
          v-for="(chapter, index) in chapters"
          :key="chapter.start"
          type="button"
          :class="{ active: index === activeChapter }"
          @click="seekChapter(index)"
        >
          <span class="no">{{ String(index).padStart(2, '0') }}</span>
          {{ chapter.title }}
        </button>
      </div>
    </div>
    <p v-if="videoError" class="lesson-generating degraded">视频渲染失败：{{ videoError }}</p>
    <p v-if="lessonGenerating" class="lesson-generating">正在根据你这次的表现生成专属微课…</p>
    <p v-else-if="lessonError" class="lesson-generating degraded">本次未能生成个性化内容，下面是课件原文：{{ lessonError }}</p>

    <div class="learning-status">
      <span>学习进度 {{ task.learningProgress }}%</span>
      <span>{{ task.completed ? '课程与练习已完成' : `已完成 ${task.completedSteps.length}/3 个方法${task.practiceDegraded ? ' · 练习待评价' : ''}` }}</span>
    </div>
    <div class="learning-meter" role="progressbar" :aria-valuenow="task.learningProgress" aria-valuemin="0" aria-valuemax="100">
      <span :style="{ width: `${task.learningProgress}%` }" />
    </div>

    <details v-if="generated" class="lesson-source">
      <summary>查看原始课件素材 · {{ generated.source.title }}</summary>
      <p v-if="generated.source.description">{{ generated.source.description }}</p>
      <ul class="source-points">
        <li v-for="(point, index) in sourcePoints" :key="index">{{ point }}</li>
      </ul>
    </details>

    <div class="steps">
      <article v-for="(step, index) in lesson.steps" :key="index" class="step" :class="{ done: task.completedSteps.includes(index) }">
        <div class="step-rail" aria-hidden="true">
          <span class="step-number">0{{ index + 1 }}</span>
          <i class="rail-line" />
        </div>
        <div class="step-body">
          <header class="step-head">
            <h3>{{ step.title }}</h3>
            <button
              v-if="videoUrl && chapters[index + 1]"
              type="button"
              class="watch-button"
              @click="seekChapter(index + 1)"
            >看这一段</button>
          </header>
          <p>{{ step.explanation }}</p>
          <blockquote class="example"><span class="example-tag">示范</span>{{ step.example }}</blockquote>
          <button
            v-if="!task.completedSteps.includes(index)"
            class="button step-button"
            type="button"
            :disabled="index !== nextStep || submitting"
            @click="emit('completeStep', index)"
          >{{ index === nextStep ? '我理解了，学习下一步' : '请先完成上一步' }}</button>
          <span v-else class="done-label">✓ 已学习</span>
        </div>
      </article>
    </div>

    <div class="practice">
      <p class="eyebrow">表达练习</p>
      <h3>{{ lesson.exercise }}</h3>
      <p class="hint">用自己的话作答，至少 40 字。完成三个步骤后提交；模型会给出针对性反馈。</p>
      <textarea v-model="answer" class="field" rows="5" maxlength="2000" :disabled="!readyToPractice || task.completed" placeholder="在这里写下你的回答……" />
      <p v-if="task.practiceFeedback" class="feedback" :class="{ degraded: task.practiceDegraded }">
        {{ task.practiceDegraded ? '待评价：' : task.practicePassed ? '练习反馈：' : '还需改进：' }}{{ task.practiceFeedback }}
      </p>
      <button v-if="!task.completed" class="button signal" type="button" :disabled="!canSubmit" @click="emit('submitPractice', answer.trim())">
        {{ submitting ? '正在评价…' : '提交练习并获取反馈' }}
      </button>
      <RouterLink v-else class="button signal" :to="`/plans/${plan.id}`">查看下一项训练任务 →</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.personalized { padding: clamp(22px, 4vw, 42px); }
.lesson-header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; }
.lesson-header h2 { margin: 12px 0; font: 700 clamp(28px, 4vw, 42px)/1.2 var(--font-ui); }
.lesson-header p:last-child { max-width: 720px; line-height: 1.8; color: var(--ink-soft); }
.lesson-tools { display: flex; align-items: center; gap: 10px; flex: none; }
.swap-button {
  flex: none;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 11px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--card);
  color: var(--text-2);
  font-size: 12px;
  cursor: pointer;
  transition: border-color .16s var(--ease), color .16s var(--ease);
}
.swap-button:hover:not(:disabled) { border-color: var(--border-bright); color: var(--text); }
.swap-button:disabled { opacity: .55; cursor: progress; }
.lesson-generating { margin: 14px 0 0; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-2); color: var(--text-2); font-size: 12px; }
.lesson-generating.degraded { border-color: rgba(248, 113, 113, .3); color: #cf9a92; }
.lesson-source { margin: 16px 0 4px; padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-2); }
.lesson-source summary { color: var(--text-2); font-size: 12px; cursor: pointer; }
.lesson-source p { margin: 10px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.8; }
.lesson-source pre { margin: 10px 0 0; color: var(--text-2); font-size: 12px; line-height: 1.9; white-space: pre-wrap; font-family: inherit; }
.source-tag { flex: none; padding: 8px 12px; border-radius: 99px; background: var(--sky); color: var(--mint-dark); font-size: 12px; }
.learning-status { display: flex; justify-content: space-between; margin-top: 26px; font-size: 13px; color: var(--ink-soft); }
.learning-meter { height: 8px; margin: 10px 0 28px; border-radius: 99px; overflow: hidden; background: var(--track); }
.learning-meter span { display: block; height: 100%; background: var(--mint); transition: width .25s ease; }
.steps { display: grid; gap: 14px; }
.step { display: grid; grid-template-columns: 54px 1fr; gap: 18px; padding: 22px; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); }
.step.done { background: #f6faf8; }
.step-number { color: var(--mint-dark); font: 700 28px/1 var(--font-ui); }
.step-body h3 { margin: 0 0 10px; font-size: 20px; }
.step-body p { margin: 0 0 12px; color: var(--ink-soft); line-height: 1.7; }
.step-body blockquote { margin: 0 0 14px; padding: 12px 16px; border-left: 3px solid var(--mint); background: var(--sky); line-height: 1.7; }
.step-button { font-size: 13px; }
.done-label { color: var(--mint-dark); font-size: 13px; font-weight: 700; }
.practice { margin-top: 28px; padding: 24px; border-radius:var(--radius); background: var(--bg-2); }
.practice h3 { margin: 10px 0; font-size: 19px; line-height: 1.6; }
.hint { font-size: 13px; color: var(--ink-soft); }
.practice textarea { width: 100%; resize: vertical; margin: 10px 0 12px; }
.feedback { padding: 12px; border-radius:var(--radius-sm); color: var(--mint-dark); background: #dff4ef; line-height: 1.7; }
.feedback.degraded { color: var(--warning); background: rgba(194,168,119,.14); }
@media (max-width: 650px) { .lesson-header { flex-direction: column; } .step { grid-template-columns: 1fr; } }
.source-tag { border:1px solid var(--border);background:var(--bg-2);color:var(--text-2); }
.learning-meter { background:var(--track); }
.learning-meter span { background:var(--muted-progress);box-shadow:none; }
.step,.step.done { border-color:var(--border);background:var(--card); }
.step-number,.done-label { color:var(--text-2); }
.step-body blockquote { border-color:var(--divider);background:var(--bg-2); }
.practice { border:1px solid var(--border);background:var(--card); }
.feedback { color:var(--text-2);background:var(--bg-2); }
.feedback.degraded { color:var(--text-2);background:var(--bg-2); }
.lesson-video { margin: 18px 0 22px; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; background: #000; }
.lesson-video video { display: block; width: 100%; height: auto; }

/* ---------- 课程视觉：章节 + 时间轴 + 示范卡 ---------- */
.lesson-video { margin: 22px 0 8px; display: grid; gap: 10px; }
.lesson-video video { width: 100%; border: 1px solid var(--border); border-radius: var(--radius-md); background: #0b0b0e; }
.chapters { display: flex; flex-wrap: wrap; gap: 8px; }
.chapters button { max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 12px; border: 1px solid var(--border); border-radius: 999px;
  background: var(--card); color: var(--text-2); font-size: 12px; cursor: pointer;
  transition: border-color .14s var(--ease), color .14s var(--ease), background .14s var(--ease);
}
.chapters button:hover { border-color: var(--border-bright); color: var(--text); }
.chapters button.active { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.chapters .no { color: var(--text-3); font-variant-numeric: tabular-nums; }

.steps { display: grid; gap: 0; margin-top: 8px; }
.step { display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 18px; padding: 20px 0; border-top: 1px solid var(--divider); }
.step:first-child { border-top: 0; }
.step-rail { display: grid; justify-items: center; gap: 8px; }
.step-number {
  display: grid; place-items: center; width: 40px; height: 40px;
  border: 1px solid var(--border); border-radius: 50%;
  background: var(--card); color: var(--text-2);
  font-family: var(--font-num); font-size: 13px; letter-spacing: .02em;
}
.step.done .step-number { border-color: var(--accent); color: var(--accent-strong); }
.rail-line { width: 1px; flex: 1; min-height: 12px; background: var(--border); }
.step:last-child .rail-line { display: none; }
.step-head { display: flex; align-items: baseline; justify-content: space-between; gap: 14px; }
.step-body h3 { margin: 0 0 10px; font-size: 17px; font-weight: 600; }
.watch-button { flex: none; padding: 4px 10px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-3); font-size: 11.5px; cursor: pointer; }
.watch-button:hover { border-color: var(--accent); color: var(--accent-strong); }
.step-body p { margin: 0 0 12px; color: var(--text-2); font-size: 13.5px; line-height: 1.9; }
.example {
  margin: 0 0 14px; padding: 12px 14px 12px 14px;
  border: 1px solid var(--border); border-left: 2px solid var(--accent);
  border-radius: 0 8px 8px 0; background: var(--bg-2);
  color: var(--text-2); font-size: 13px; line-height: 1.85;
}
.example-tag { display: inline-block; margin-right: 8px; color: var(--accent-strong); font-size: 11px; letter-spacing: .06em; }
.source-points { margin: 8px 0 0; padding-left: 18px; color: var(--text-2); font-size: 12.5px; line-height: 1.9; }
</style>
