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
const emit = defineEmits<{ completeCourse: [] }>()

const generated = shallowRef<LessonResponse | null>(null)
const lessonGenerating = shallowRef(true)
const lessonError = shallowRef('')
const videoUrl = shallowRef('')
const videoBuilding = shallowRef(false)
const videoError = shallowRef('')
const videoElapsed = shallowRef(0)
const chapters = shallowRef<Array<{ title: string; start: number; duration: number }>>([])
const videoEl = shallowRef<HTMLVideoElement | null>(null)
const activeChapter = shallowRef(0)
const watched = shallowRef(0)
const duration = shallowRef(0)

let videoTimer: ReturnType<typeof setInterval> | null = null

const lesson = computed(() => generated.value?.lesson ?? props.task.lesson)
const courseTitle = computed(() => lesson.value?.title ?? '沟通微课')
const progress = computed(() => props.task.learningProgress ?? 0)
const canFinish = computed(() => Boolean(videoUrl.value) && !props.task.completed)
const watchedPercent = computed(() => (duration.value > 0 ? Math.min(100, Math.round((watched.value / duration.value) * 100)) : 0))

async function buildVideo(): Promise<void> {
  if (videoBuilding.value) return
  videoBuilding.value = true
  videoError.value = ''
  videoElapsed.value = 0
  videoTimer = setInterval(() => { videoElapsed.value += 1 }, 1000)
  try {
    // 首次渲染要跑 Remotion，给足 3 分钟
    const response = await api.post<ApiEnvelope<{ url: string; chapters?: typeof chapters.value }>>(
      `/training-plans/${props.plan.id}/lesson/video`,
      { task_key: props.task.key },
      { timeout: 180_000 },
    )
    const payload = response.data.data
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
    const response = await api.get<ApiEnvelope<{ url: string | null; chapters?: typeof chapters.value }>>(
      `/training-plans/${props.plan.id}/lesson/video`,
      { params: { task_key: props.task.key } },
    )
    const data = response.data.data
    if (data.url) {
      videoUrl.value = `${(import.meta.env.VITE_API_BASE ?? '/api/v1').replace('/api/v1', '')}${data.url}`
      chapters.value = data.chapters ?? []
    }
  } catch {
    // 没有缓存视频时下面会自动渲染
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
  duration.value = videoEl.value?.duration ?? 0
  if (videoEl.value && videoEl.value.currentTime === 0) {
    videoEl.value.currentTime = 0.35
  }
}

function onTimeUpdate(): void {
  if (!videoEl.value) return
  const time = videoEl.value.currentTime
  watched.value = Math.max(watched.value, time)
  const index = chapters.value.findIndex((chapter, position) => {
    const next = chapters.value[position + 1]
    return time >= chapter.start && (!next || time < next.start)
  })
  if (index >= 0) activeChapter.value = index
}

onMounted(async () => {
  await loadLesson(false)
  await loadCachedVideo()
  if (!videoUrl.value && !videoBuilding.value) {
    await buildVideo()
  }
})
</script>

<template>
  <section class="course" aria-label="沟通微课">
    <header class="course-head">
      <div>
        <p class="eyebrow">能力微课 · {{ plan.focusDimension }}</p>
        <h1>{{ courseTitle }}</h1>
      </div>
      <div class="course-tools">
        <span class="tag" v-if="props.task.completed">已完成 · 可回看</span>
        <button class="ghost" type="button" :disabled="lessonGenerating || videoBuilding" @click="loadLesson(true); buildVideo()">
          <RefreshCw :size="13" :stroke-width="1.8" aria-hidden="true" />
          换一门
        </button>
      </div>
    </header>

    <div class="player" :class="{ empty: !videoUrl && !videoBuilding }">
      <video
        v-if="videoUrl"
        ref="videoEl"
        :src="videoUrl"
        controls
        playsinline
        preload="metadata"
        @loadedmetadata="onLoadedMetadata"
        @timeupdate="onTimeUpdate"
      />
      <div v-else class="player-placeholder">
        <template v-if="videoBuilding">
          <span class="spinner" aria-hidden="true" />
          <p>正在生成这节课 {{ videoElapsed }}s</p>
          <small>首次生成会慢一些，之后就快了</small>
        </template>
        <template v-else>
          <p>这节课的视频还没生成</p>
          <button class="button" type="button" @click="buildVideo">
            <Play :size="14" :stroke-width="1.8" aria-hidden="true" />
            生成视频
          </button>
        </template>
      </div>
    </div>

    <p v-if="videoError" class="error">视频生成失败：{{ videoError }}</p>
    <p v-if="lessonError" class="hint">课程内容生成降级：{{ lessonError }}</p>

    <nav v-if="chapters.length" class="chapters" aria-label="课程章节">
      <button
        v-for="(chapter, index) in chapters"
        :key="chapter.start"
        type="button"
        :class="{ active: index === activeChapter }"
        @click="seekChapter(index)"
      >
        <span class="no">{{ String(index + 1).padStart(2, '0') }}</span>
        {{ chapter.title }}
      </button>
    </nav>

    <section v-if="lesson" class="reading" aria-label="课程文字版">
      <p v-if="lesson.intro" class="course-intro">{{ lesson.intro }}</p>
      <ol v-if="lesson.steps.length" class="reading-steps">
        <li v-for="(step, index) in lesson.steps" :key="step.title">
          <span class="no">{{ String(index + 1).padStart(2, '0') }}</span>
          <div>
            <strong>{{ step.title }}</strong>
            <p>{{ step.explanation }}</p>
            <p v-if="step.example" class="example">例：{{ step.example }}</p>
          </div>
        </li>
      </ol>
      <p v-if="lesson.exercise" class="exercise">练习：{{ lesson.exercise }}</p>
      <p v-if="props.task.practiceFeedback" class="feedback">上次练习反馈：{{ props.task.practiceFeedback }}</p>
    </section>

    <footer class="course-foot">
      <div class="progress">
        <span>观看 {{ watchedPercent }}%<template v-if="duration"> · 共 {{ Math.round(duration / 60) }} 分钟</template></span>
        <div class="bar" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
          <i :style="{ width: `${props.task.completed ? 100 : progress}%` }" />
        </div>
      </div>
      <button v-if="!props.task.completed" class="button" type="button" :disabled="!canFinish || submitting" @click="emit('completeCourse')">
        {{ submitting ? '提交中…' : '我看完了，完成课程' }}
      </button>
      <RouterLink v-else class="button secondary" :to="`/plans/${plan.id}`">返回计划看下一项 →</RouterLink>
    </footer>
  </section>
</template>

<style scoped>
.course { display: grid; gap: 18px; padding: clamp(20px, 3vw, 34px); border: 1px solid var(--border); border-radius: 16px; background: var(--card); }
.course-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.course-head h1 { margin: 10px 0 6px; font: 700 clamp(24px, 3vw, 34px)/1.25 var(--font-display); }
.course-intro { margin: 0; max-width: 720px; color: var(--text-2); font-size: 13.5px; line-height: 1.8; }
.course-tools { display: flex; align-items: center; gap: 10px; }
.tag { padding: 3px 10px; border: 1px solid var(--success); border-radius: 999px; color: var(--success); font-size: 11px; }
.ghost { display: inline-flex; align-items: center; gap: 6px; padding: 7px 12px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-2); font-size: 12px; cursor: pointer; }
.player { border-radius: 14px; overflow: hidden; background: #0b0b0e; }
.player video { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: contain; background: #0b0b0e; }
.player-placeholder { display: grid; place-items: center; gap: 8px; padding: 64px 20px; color: rgba(255, 255, 255, .8); text-align: center; }
.player-placeholder p { margin: 0; font-size: 14px; }
.player-placeholder small { color: rgba(255, 255, 255, .55); font-size: 12px; }
.spinner { width: 26px; height: 26px; border: 2px solid rgba(255, 255, 255, .2); border-top-color: #fff; border-radius: 50%; animation: spin .9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.chapters { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 2px; }
.chapters button { display: inline-flex; align-items: center; gap: 8px; flex: none; padding: 8px 14px; border: 1px solid var(--border); border-radius: 999px; background: var(--card); color: var(--text-2); font-size: 12px; cursor: pointer; }
.chapters button.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); }
.chapters .no { color: var(--text-3); font-size: 10.5px; font-variant-numeric: tabular-nums; }
.reading { display: grid; gap: 12px; padding-top: 14px; border-top: 1px solid var(--divider); }
.reading-steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; }
.reading-steps li { display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 10px; }
.reading-steps .no { padding-top: 2px; color: var(--text-3); font-size: 11px; font-variant-numeric: tabular-nums; }
.reading-steps strong { display: block; color: var(--text); font-size: 13.5px; font-weight: 600; }
.reading-steps p { margin: 4px 0 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
.reading-steps .example { color: var(--text-3); }
.exercise, .feedback { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
.feedback { color: var(--text-3); }
.course-foot { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-top: 14px; border-top: 1px solid var(--divider); }
.progress { display: grid; gap: 6px; min-width: 220px; color: var(--text-3); font-size: 12px; }
.bar { height: 5px; border-radius: 99px; background: var(--track); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); transition: width .2s var(--ease); }
.error { margin: 0; color: var(--danger); font-size: 12.5px; }
.hint { margin: 0; color: var(--text-3); font-size: 12px; }
@media (max-width: 720px) { .course-head { flex-direction: column; } .course-foot { flex-direction: column; align-items: flex-start; } }
</style>
