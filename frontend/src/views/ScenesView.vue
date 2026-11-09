<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import SceneCard from '@/components/scenes/SceneCard.vue'
import InterviewStartDialog from '@/components/scenes/InterviewStartDialog.vue'
import { useSceneFilters } from '@/composables/useSceneFilters'
import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'
import { DIFFICULTY_LEVELS } from '@/lib/sceneTaxonomy'
import SelectField from '@/components/ui/SelectField.vue'

const router = useRouter()
const scenes = shallowRef<Scene[]>([])
const loading = shallowRef(true)
const error = shallowRef('')
const startSelection = shallowRef<{ scene: Scene; mode: 'text' | 'voice' } | null>(null)
const advanced = shallowRef(false)
const DEPTH_KEY = 'yanjie-interview-depth'
const depth = shallowRef<'STANDARD' | 'THREE_LAYER' | 'PRESSURE'>(
  (localStorage.getItem(DEPTH_KEY) as 'STANDARD' | 'THREE_LAYER' | 'PRESSURE') || 'STANDARD',
)
function setDepth(value: 'STANDARD' | 'THREE_LAYER' | 'PRESSURE'): void {
  depth.value = value
  localStorage.setItem(DEPTH_KEY, value)
}
const LANGUAGE_KEY = 'yanjie-interview-language'
const language = shallowRef<'zh' | 'en'>((localStorage.getItem(LANGUAGE_KEY) as 'zh' | 'en') || 'zh')
function setLanguage(value: 'zh' | 'en'): void {
  language.value = value
  localStorage.setItem(LANGUAGE_KEY, value)
}

const starting = shallowRef(false)
const startError = shallowRef('')
const {
  activeCategory, activeIndustry, activePosition, activeDifficulty, query,
  categories, industries, positions, difficulties, visibleScenes, catalogScenes, foundationFocus,
  planId, taskKey, recommendedSceneId,
} = useSceneFilters(scenes)

onMounted(() => { void load() })

async function load() {
  loading.value = true
  try {
    const response = await api.get<ApiEnvelope<Scene[]>>('/scenes', { params: { size: 100 } })
    scenes.value = response.data.data
  } catch (reason) { error.value = errorMessage(reason) }
  finally { loading.value = false }
}

async function toggleFavorite(scene: Scene) {
  const response = await api.post<ApiEnvelope<{ favorite: boolean }>>(`/scenes/${scene.id}/favorite`)
  scenes.value = scenes.value.map((item) => item.id === scene.id ? { ...item, favorite: response.data.data.favorite } : item)
}

async function startDrill(scene: Scene): Promise<void> {
  startError.value = ''
  try {
    const created = await api.post<ApiEnvelope<{ id: string }>>('/training-sessions', {
      sceneId: scene.id,
      mode: 'DRILL',
      ...(planId.value && taskKey.value ? { planId: planId.value, taskKey: taskKey.value } : {}),
    })
    void router.push(`/training/${created.data.data.id}`)
  } catch (reason) {
    startError.value = errorMessage(reason)
  }
}

function start(scene: Scene, mode: 'text' | 'voice' | 'video' | 'drill') {
  if (mode === 'drill') {
    void startDrill(scene)
    return
  }
  startError.value = ''
  if (mode === 'video') {
    void router.push({ name: 'video', query: { sceneId: scene.id, depth: depth.value, lang: language.value } })
    return
  }
  if (mode === 'voice') {
    void router.push({
      name: 'voice',
      query: {
        sceneId: scene.id,
        depth: depth.value,
        lang: language.value,
        ...(planId.value && taskKey.value ? { planId: planId.value, taskKey: taskKey.value } : {}),
      },
    })
    return
  }
  startSelection.value = { scene, mode }
}

async function confirmStart(file: File | null): Promise<void> {
  if (!startSelection.value || starting.value) return
  const { scene, mode } = startSelection.value
  starting.value = true
  startError.value = ''
  try {
    const form = new FormData()
    if (file) {
      form.append('sceneId', scene.id)
      form.append('depth', depth.value)
      form.append('language', language.value)
      form.append('file', file)
    }
    const response = file
      ? await api.post<ApiEnvelope<{ id: string }>>('/training-sessions/with-resume', form, { timeout: MODEL_REQUEST_TIMEOUT_MS })
      : await api.post<ApiEnvelope<{ id: string }>>('/training-sessions', {
        sceneId: scene.id,
        depth: depth.value,
        language: language.value,
        ...(planId.value && taskKey.value ? { planId: planId.value, taskKey: taskKey.value } : {}),
      })
    startSelection.value = null
    await router.push({
      name: 'training',
      params: { id: response.data.data.id },
      query: { ...(planId.value && taskKey.value ? { planId: planId.value, taskKey: taskKey.value } : {}), mode },
    })
  } catch (reason) { startError.value = errorMessage(reason) }
  finally { starting.value = false }
}

</script>

<template>
  <div class="page">
    <header class="scene-head">
      <div class="head-copy">
        <p class="eyebrow">{{ foundationFocus ? '基础练习' : '场景训练' }}</p>
        <h1>{{ foundationFocus ? '围绕一个维度，连续练几轮。' : '选择一场面试，直接开始。' }}</h1>
        <p class="lead">{{ foundationFocus ? '完成后查看四维反馈。' : '按行业、岗位和面试阶段筛选；难度越高，追问越深入。' }}</p>
      </div>
      <div class="head-side">
        <span>{{ catalogScenes.length }} 场</span>
        <RouterLink to="/my-scenes">自建场景 →</RouterLink>
        <RouterLink to="/favorites">我的收藏 →</RouterLink>
      </div>
    </header>

    <div v-if="planId" class="plan-notice">
      这是训练计划中的指定场景。请创建新会话，完成至少 6 轮对话并查看评分。
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <section class="scene-catalog" aria-label="选择面试场景">
      <div class="catalog-heading"><h2>场景</h2><span>{{ visibleScenes.length }} 个</span></div>
      <div v-if="recommendedSceneId" class="focus-notice">已打开指定训练场景。<RouterLink to="/scenes">查看全部场景 →</RouterLink></div>
      <div v-else class="filters panel">
        <div class="filter-row">
          <SelectField :model-value="activeIndustry" :options="industries.map((item) => ({ value: item, label: item }))" aria-label="按行业筛选" @update:model-value="activeIndustry = $event" />
          <SelectField :model-value="activePosition" :options="positions.map((item) => ({ value: item, label: item }))" aria-label="按岗位筛选" @update:model-value="activePosition = $event" />
          <SelectField :model-value="activeDifficulty" :options="difficulties.map((item) => ({ value: item, label: item }))" aria-label="按难度筛选" @update:model-value="activeDifficulty = $event" />
          <input v-model="query" class="field search" aria-label="搜索场景、角色或关键词" placeholder="搜索场景、角色或关键词" />
        </div>
        <div class="stage-filter">
          <div class="category-tabs" role="tablist" aria-label="面试阶段">
            <button v-for="category in categories" :key="category" type="button" role="tab" :aria-selected="activeCategory === category" :class="{ active: activeCategory === category }" @click="activeCategory = category">{{ category }}</button>
          </div>
        </div>
        <button class="more-toggle" type="button" @click="advanced = !advanced">{{ advanced ? '收起设置' : '更多设置' }}</button>
        <div v-if="advanced" class="extra-settings">
          <div class="depth-picker" role="group" aria-label="面试语言">
            <span>面试语言</span>
            <button type="button" :class="{ active: language === 'zh' }" @click="setLanguage('zh')">中文</button>
            <button type="button" :class="{ active: language === 'en' }" @click="setLanguage('en')">English</button>
          </div>
          <div class="depth-picker" role="group" aria-label="追问强度">
            <span>追问强度</span>
            <button type="button" :class="{ active: depth === 'STANDARD' }" @click="setDepth('STANDARD')">标准</button>
            <button type="button" :class="{ active: depth === 'THREE_LAYER' }" @click="setDepth('THREE_LAYER')">三层深挖</button>
            <button type="button" :class="{ active: depth === 'PRESSURE' }" @click="setDepth('PRESSURE')">压力面</button>
          </div>
          <div class="difficulty-guide" aria-label="难度说明"><span v-for="level in DIFFICULTY_LEVELS" :key="level.name" :class="level.tone"><i aria-hidden="true" />{{ level.name }}<small>{{ level.cue }}</small></span></div>
        </div>
      </div>
    </section>
    <section v-if="loading" class="scene-grid"><div v-for="n in 4" :key="n" class="skeleton scene-loading" /></section>
    <section v-else-if="visibleScenes.length" class="scene-grid">
      <SceneCard v-for="scene in visibleScenes" :key="scene.id" :scene="scene" @start="start" @favorite="toggleFavorite" />
    </section>
    <div v-else class="empty panel">没有匹配的场景。换一个关键词，或选择其他分类。</div>
    <InterviewStartDialog
      v-if="startSelection"
      :scene="startSelection.scene"
      :mode="startSelection.mode"
      :busy="starting"
      :error="startError"
      @confirm="confirmStart"
      @cancel="startSelection = null"
    />
  </div>
</template>

<style scoped>
.depth-picker { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-3); }
.depth-picker button { border: 1px solid var(--border); background: transparent; color: var(--text-2); border-radius: 999px; padding: 4px 12px; font-size: 12px; cursor: pointer; }
.depth-picker button.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); }
.scene-hero { position: relative; min-height: 320px; margin-bottom: 30px; padding: 34px 40px; overflow: hidden; align-items: end; border-radius: var(--radius); background: linear-gradient(115deg,#1e40af,#2563eb); color: #fff; isolation: isolate; }
.scene-hero::before { content: ''; position: absolute; z-index: -1; width: 460px; height: 460px; top: -275px; right: 3%; border: 1px solid rgba(191,219,254,.34); border-radius: 50%; box-shadow: 0 0 0 62px rgba(191,219,254,.045), 0 0 0 125px rgba(191,219,254,.035); }
.scene-hero::after { content: ''; position: absolute; z-index: -1; width: 260px; height: 260px; right: 15%; bottom: -225px; border: 1px solid rgba(191,219,254,.35); border-radius: 50%; }
.scene-hero .eyebrow { color: var(--text-3); }
.scene-hero .page-title { font-size: clamp(34px, 3.6vw, 50px); line-height: 1.14; }
.scene-hero .page-title span { color: var(--border); }
.scene-hero .page-lead { max-width: 610px; color: var(--border); }
.hero-aside { min-width: 158px; padding: 0 0 2px 22px; display: grid; gap: 4px; border-left: 1px solid var(--border-bright); }
.hero-aside span { color: var(--border); font-size: 12px; }
.hero-aside strong { font: 700 62px/.98 var(--font-ui); color: #fff; }
.hero-aside small { color: var(--text-3); font-size: 11px; white-space: nowrap; }
.catalog-heading { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 17px; }
.catalog-heading h2 { margin: 0; font: 700 27px/1.25 var(--font-ui); }
.catalog-heading > span { padding-bottom: 3px; color: var(--ink-soft); font-size: 12px; }
.filters { margin-bottom: 20px; padding: 16px; display: grid; grid-template-columns: 1fr; align-items: center; gap: 13px; border: 1px solid var(--line); border-radius:var(--radius); background: var(--card); }
.metadata-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.metadata-filters select { min-width: 120px; }
.plan-notice { margin-bottom: 18px; padding: 12px 15px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--sky); color: var(--mint-dark); font-size: 13px; }
.focus-notice { margin-bottom: 20px; padding: 13px 16px; border: 1px solid var(--border); border-radius:var(--radius); background: var(--glass); color: var(--text-2); font-size: 13px; }
.focus-notice a { margin-left: 8px; color: var(--text); border-bottom: 1px solid var(--border-bright); padding-bottom: 1px; }
.stage-filter { display: flex; align-items: center; gap: 10px; min-width: 0; }
.stage-label { flex: none; color: var(--text-3); font-size: 12px; letter-spacing: .02em; }
.category-tabs { display: flex; gap: 8px; flex-wrap: nowrap; overflow-x: auto; padding-bottom: 2px; scrollbar-width: thin; }
.category-tabs button { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
@media (max-width: 720px) { .stage-filter { flex-direction: column; align-items: stretch; gap: 6px; } }
.category-tabs button { min-height: 38px; padding: 0 15px; border: 1px solid var(--line); border-radius: 7px; background:var(--card); cursor: pointer; color: var(--ink-soft); transition: background .18s, border-color .18s, color .18s; }
.category-tabs button:hover { border-color: var(--mint-dark); color: var(--mint-dark); }
.category-tabs button.active { border-color: var(--accent); background: var(--accent); color: var(--on-solid); }
.search { width: 100%; grid-column: 1 / -1; background: var(--bg-2); }
.scene-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.scene-loading { min-height: 330px; }
.scene-hero { border: 1px solid var(--border); background: var(--card); box-shadow: var(--shadow); }
.scene-hero::before,.scene-hero::after { display:none; }
.scene-hero .eyebrow { color:var(--text-2); }
.scene-hero .page-title span { background:none; color:var(--text); }
.scene-hero .page-lead,.hero-aside span { color: var(--text-2); }
.hero-aside strong { background:none; color:var(--text); font:500 54px/1 var(--font-ui); }
.filters { border-color: var(--border); background: var(--card); box-shadow: var(--shadow); }
.plan-notice { border-color: var(--border); background: var(--card); color: var(--text-2); }
.category-tabs button { border-color: var(--border); background: var(--bg-2); color: var(--text-2); transition: background var(--ease),border-color var(--ease),color var(--ease); }
.category-tabs button:hover { border-color: var(--border-bright); color: var(--text); }
.category-tabs button.active { border-color: var(--accent); background: var(--accent); color: var(--on-solid); box-shadow: none; }
.search { background: var(--bg-2); }
.difficulty-guide { display:flex;flex-wrap:wrap;gap:8px 18px;padding:2px 3px;color:var(--text);font-size:12px; }
.difficulty-guide span { display:inline-flex;align-items:center;gap:6px; }
.difficulty-guide i { width:7px;height:7px;border-radius:50%;background:currentColor; }
.difficulty-guide small { color:var(--text-2);font-size:11px; }
.difficulty-guide .easy { color:var(--success); }
.difficulty-guide .medium { color:var(--text-2); }
.difficulty-guide .hard { color:var(--danger); }
.difficulty-select.easy,.difficulty-select.medium,.difficulty-select.hard { border-color:var(--border);color:var(--text); }
.scene-grid > :nth-child(2n) { animation-delay: .1s; }
@media (max-width: 1100px) { .filters { grid-template-columns: 1fr; } }
@media (max-width: 650px) { .scene-hero { min-height: auto; padding: 28px 25px; } .hero-aside { display: none; } .scene-hero .page-title { font-size: 36px; } .scene-hero .page-lead { font-size: 13px; } .catalog-heading h2 { font-size: 23px; } .metadata-filters { display: grid; grid-template-columns: 1fr 1fr; } .metadata-filters select { min-width: 0; } .metadata-filters select:last-child { grid-column: 1 / -1; } .scene-grid { grid-template-columns: 1fr; } }

:root[data-theme='dark'] .scene-hero {
  background: #0a0a24;
  border: 1px solid rgba(255, 255, 255, .1);
  color: #fff;
}
:root[data-theme='dark'] .scene-hero > :not(.atmos) { position: relative; z-index: 2; }
:root[data-theme='dark'] .scene-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(6, 4, 20, 0) 34%, rgba(6, 4, 20, .55) 100%);
}
:root[data-theme='dark'] .scene-hero::before,
:root[data-theme='dark'] .scene-hero::after { border-color: var(--border); box-shadow: none; }
:root[data-theme='dark'] .scene-hero .eyebrow { color: rgba(255, 255, 255, .55); }
:root[data-theme='dark'] .scene-hero .page-title span { color: rgba(255, 255, 255, .5); }
:root[data-theme='dark'] .scene-hero .page-lead { color: rgba(255, 255, 255, .72); }
:root[data-theme='dark'] .hero-aside { border-left-color: var(--border); }
:root[data-theme='dark'] .hero-aside span { color: rgba(255, 255, 255, .55); }
:root[data-theme='dark'] .hero-aside strong { color: #fff; }

.my-scenes-link { margin: 10px 0 0; }
.my-scenes-link a { color: var(--accent-strong); font-size: 12.5px; }
</style>
<style scoped>
.scene-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 30px; }
.scene-head h1 { margin: 10px 0 0; font-size: clamp(28px, 3.2vw, 38px); font-weight: 650; letter-spacing: -.02em; line-height: 1.25; }
.scene-head .lead { margin: 12px 0 0; color: var(--text-3); font-size: 14px; line-height: 1.8; }
.head-side { display: flex; align-items: center; gap: 16px; flex: none; padding-bottom: 4px; font-size: 13px; color: var(--text-3); }
.head-side a { color: var(--text-2); }
.catalog-heading { display: flex; align-items: baseline; justify-content: space-between; margin: 0 0 12px; }
.catalog-heading h2 { margin: 0; font-size: 20px; font-weight: 600; }
.catalog-heading span { color: var(--text-3); font-size: 12.5px; }
.filters { display: grid; gap: 12px; padding: 16px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.filter-row :deep(.select-trigger) { width: auto; min-width: 130px; }
.search { flex: 1 1 240px; min-width: 200px; }
.stage-filter { min-width: 0; }
.extra-settings { display: grid; gap: 12px; padding-top: 4px; }
.more-toggle { justify-self: start; border: 0; background: transparent; color: var(--text-3); font-size: 12.5px; cursor: pointer; padding: 0; }
.more-toggle:hover { color: var(--text); }
.scene-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 16px; }
@media (max-width: 720px) { .scene-head { flex-direction: column; align-items: flex-start; } .head-side { padding: 0; } }
</style>
