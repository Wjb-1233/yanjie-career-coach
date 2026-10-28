<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import SceneCard from '@/components/scenes/SceneCard.vue'
import InterviewStartDialog from '@/components/scenes/InterviewStartDialog.vue'
import { useSceneFilters } from '@/composables/useSceneFilters'
import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'
import { DIFFICULTY_LEVELS, difficultyTone } from '@/lib/sceneTaxonomy'

const router = useRouter()
const scenes = shallowRef<Scene[]>([])
const loading = shallowRef(true)
const error = shallowRef('')
const startSelection = shallowRef<{ scene: Scene; mode: 'text' | 'voice' } | null>(null)
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

function start(scene: Scene, mode: 'text' | 'voice') {
  startError.value = ''
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
      form.append('file', file)
    }
    const response = file
      ? await api.post<ApiEnvelope<{ id: string }>>('/training-sessions/with-resume', form, { timeout: MODEL_REQUEST_TIMEOUT_MS })
      : await api.post<ApiEnvelope<{ id: string }>>('/training-sessions', { sceneId: scene.id })
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
    <header class="page-heading scene-hero">
      <div class="hero-copy"><p class="eyebrow">{{ foundationFocus ? '五维基础练习' : '场景训练' }}</p><h1 class="page-title">把难回答的问题，<br /><span>先在这里练一遍。</span></h1><p class="page-lead">{{ foundationFocus ? '围绕一个表达维度进行连续对练，完成后查看五维反馈。' : '先选行业与岗位，再按真实招聘阶段选择面试。不同岗位只展示适用的阶段；难度越高，追问越深入。' }}</p></div>
      <div class="hero-aside" aria-label="场景概览"><span>训练场景</span><strong>{{ catalogScenes.length.toString().padStart(2, '0') }}</strong><small>从模拟对话到五维复盘</small></div>
    </header>

    <div v-if="planId" class="plan-notice">
      这是训练计划中的指定场景。请创建新会话，完成至少 6 轮对话并查看评分。
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>
    <section class="scene-catalog" aria-label="选择面试场景">
      <div class="catalog-heading"><div><p class="eyebrow">练习库</p><h2>选择一场对练</h2></div><span>{{ visibleScenes.length }} 个匹配场景</span></div>
      <div v-if="recommendedSceneId" class="focus-notice">已打开指定训练场景。<RouterLink :to="foundationFocus ? '/practice' : '/scenes'">{{ foundationFocus ? '返回通用练习' : '查看全部场景' }} →</RouterLink></div>
      <div v-else class="filters">
        <div class="metadata-filters">
          <select v-model="activeIndustry" class="field" aria-label="按行业筛选"><option v-for="industry in industries" :key="industry">{{ industry }}</option></select>
          <select v-model="activePosition" class="field" aria-label="按岗位筛选"><option v-for="position in positions" :key="position">{{ position }}</option></select>
          <select v-model="activeDifficulty" class="field difficulty-select" :class="activeDifficulty === '全部难度' ? '' : difficultyTone(activeDifficulty)" aria-label="按难度筛选"><option v-for="difficulty in difficulties" :key="difficulty">{{ difficulty }}</option></select>
        </div>
        <div class="category-tabs" aria-label="面试阶段"><button v-for="category in categories" :key="category" type="button" :class="{ active: activeCategory === category }" @click="activeCategory = category">{{ category }}</button></div>
        <div class="difficulty-guide" aria-label="难度说明"><span v-for="level in DIFFICULTY_LEVELS" :key="level.name" :class="level.tone"><i aria-hidden="true" />{{ level.name }}<small>{{ level.cue }}</small></span></div>
        <input v-model="query" class="field search" aria-label="搜索场景、角色或关键词" placeholder="搜索场景、角色或关键词" />
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
.scene-hero { position: relative; min-height: 286px; margin-bottom: 30px; padding: 34px 40px; overflow: hidden; align-items: end; border-radius: var(--radius); background: linear-gradient(115deg,#1e40af,#2563eb); color: #fff; isolation: isolate; }
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
.category-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.category-tabs button { min-height: 38px; padding: 0 15px; border: 1px solid var(--line); border-radius: 999px; background:var(--card); cursor: pointer; color: var(--ink-soft); transition: background .18s, border-color .18s, color .18s; }
.category-tabs button:hover { border-color: var(--mint-dark); color: var(--mint-dark); }
.category-tabs button.active { border-color: var(--ink); background: var(--ink); color: white; }
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
.category-tabs button.active { border-color: var(--text); background: var(--text); color: var(--on-solid); box-shadow: none; }
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
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--text);
}
:root[data-theme='dark'] .scene-hero::before,
:root[data-theme='dark'] .scene-hero::after { border-color: var(--border); box-shadow: none; }
:root[data-theme='dark'] .scene-hero .eyebrow { color: var(--text-3); }
:root[data-theme='dark'] .scene-hero .page-title span { color: var(--text-3); }
:root[data-theme='dark'] .scene-hero .page-lead { color: var(--text-2); }
:root[data-theme='dark'] .hero-aside { border-left-color: var(--border); }
:root[data-theme='dark'] .hero-aside span { color: var(--text-3); }
:root[data-theme='dark'] .hero-aside strong { color: var(--text); }
</style>

