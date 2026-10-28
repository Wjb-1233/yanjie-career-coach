<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'

import ScriptVersionCard from '@/components/scenes/ScriptVersionCard.vue'
import { api, errorMessage } from '@/lib/api'
import { difficultyTone } from '@/lib/sceneTaxonomy'
import type { ApiEnvelope, Scene, ScriptVersion } from '@/lib/types'

const scenes = shallowRef<Scene[]>([])
const scripts = shallowRef<ScriptVersion[]>([])
const allScenes = shallowRef<Scene[]>([])
const loading = shallowRef(true)
const error = shallowRef('')
const sceneTitles = computed(() => new Map(allScenes.value.map((scene) => [scene.id, scene.title])))

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [sceneResponse, scriptResponse, catalogResponse] = await Promise.all([
      api.get<ApiEnvelope<Scene[]>>('/scenes/favorites'),
      api.get<ApiEnvelope<ScriptVersion[]>>('/scripts/favorites'),
      api.get<ApiEnvelope<Scene[]>>('/scenes', { params: { size: 100 } }),
    ])
    scenes.value = sceneResponse.data.data
    scripts.value = scriptResponse.data.data
    allScenes.value = catalogResponse.data.data
  } catch (reason) { error.value = errorMessage(reason) }
  finally { loading.value = false }
}

async function removeScene(scene: Scene): Promise<void> {
  try {
    await api.post(`/scenes/${scene.id}/favorite`)
    scenes.value = scenes.value.filter((item) => item.id !== scene.id)
  } catch (reason) { error.value = errorMessage(reason) }
}

async function removeScript(script: ScriptVersion): Promise<void> {
  try {
    await api.post(`/scripts/${script.id}/favorite`)
    scripts.value = scripts.value.filter((item) => item.id !== script.id)
  } catch (reason) { error.value = errorMessage(reason) }
}

onMounted(load)
</script>

<template>
  <div class="page favorites-page">
    <header class="page-heading"><div><p class="eyebrow">个人收藏</p><h1 class="page-title">想再练的场景，<br><span>想留下的话术。</span></h1><p class="page-lead">从场景训练或话术优化点收藏后，都会集中到这里。取消收藏不会删除原记录。</p></div></header>
    <div v-if="error" class="error-banner" role="alert">{{ error }} <button type="button" @click="load">重试</button></div>
    <div v-if="loading" class="panel skeleton loading" />
    <template v-else>
      <section class="panel collection-section">
        <div class="section-heading"><div><p class="eyebrow">收藏的场景</p><h2>场景收藏</h2></div><span>{{ scenes.length }} 个</span></div>
        <div v-if="!scenes.length" class="empty-note">还没有收藏场景。<RouterLink to="/scenes">去场景训练看看 →</RouterLink></div>
        <div v-else class="scene-list">
          <article v-for="scene in scenes" :key="scene.id" class="scene-item">
            <div><span class="scene-category">{{ scene.category }}</span><h3>{{ scene.title }}</h3><p>{{ scene.roleName }} · {{ scene.industry }} / {{ scene.position }}</p><span class="difficulty" :class="difficultyTone(scene.difficulty)">{{ scene.difficulty }}</span></div>
            <div class="item-actions"><RouterLink class="button secondary" :to="{ name: 'scenes', query: { sceneId: scene.id } }">进入场景 →</RouterLink><button type="button" @click="removeScene(scene)">取消收藏</button></div>
          </article>
        </div>
      </section>
      <section class="panel collection-section">
        <div class="section-heading"><div><p class="eyebrow">收藏的话术</p><h2>话术收藏</h2></div><span>{{ scripts.length }} 个</span></div>
        <div v-if="!scripts.length" class="empty-note">还没有收藏话术。<RouterLink to="/scripts">去话术优化看看 →</RouterLink></div>
        <div v-else class="script-list"><ScriptVersionCard v-for="script in scripts" :key="script.id" :version="script" :scene-title="sceneTitles.get(script.sceneId ?? '') ?? '历史场景'" show-actions @favorite="removeScript" /></div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.favorites-page { max-width: 1120px; }
.page-title span { background:none;color:var(--text);font-weight:600; }
.collection-section { padding: 28px; margin-bottom: 22px; }
.section-heading { display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:20px; }
.section-heading h2 { margin:0;font-size:24px; }
.section-heading > span { color:var(--text-2);font-size:13px; }
.loading { min-height:320px; }
.empty-note { padding:28px 4px;color:var(--text-2);line-height:1.8; }
.empty-note a { color:var(--text-2);font-weight:600; }
.scene-list,.script-list { display:grid;gap:12px; }
.scene-item { display:flex;align-items:center;justify-content:space-between;gap:18px;padding:20px;border:1px solid var(--border);border-radius:var(--radius);background:rgba(9,15,29,.48); }
.scene-item h3 { margin:10px 0 6px;font-size:20px; }
.scene-item p { margin:0 0 10px;color:var(--text-2);font-size:12px; }
.scene-category { color:var(--text-2);font-size:11px;font-weight:600; }
.difficulty { font-size:11px;font-weight:800; }
.difficulty.easy { color:var(--success); }.difficulty.medium { color:var(--text-2); }.difficulty.hard { color:var(--danger); }
.item-actions { display:flex;align-items:center;gap:12px;flex:none; }
.item-actions button:not(.button) { border:0;background:transparent;color:var(--text-2);cursor:pointer; }
.error-banner button { border:0;background:transparent;color:inherit;text-decoration:underline;cursor:pointer; }
@media (max-width:680px) { .collection-section { padding:20px; }.scene-item { align-items:stretch;flex-direction:column; }.item-actions { justify-content:space-between; } }
</style>
