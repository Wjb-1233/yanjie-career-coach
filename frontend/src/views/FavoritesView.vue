<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'

import ScriptVersionCard from '@/components/scenes/ScriptVersionCard.vue'
import { api, errorMessage } from '@/lib/api'
import { difficultyTone } from '@/lib/sceneTaxonomy'
import type { ApiEnvelope, Scene, ScriptVersion } from '@/lib/types'

const scenes = shallowRef<Scene[]>([])
const scripts = shallowRef<ScriptVersion[]>([])
const scriptCount = shallowRef(8)
const shownScripts = computed(() => scripts.value.slice(0, scriptCount.value))
const remainingScripts = computed(() => Math.max(0, scripts.value.length - scriptCount.value))
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
      // 目录仅用于补场景标题，失败时降级为「历史场景」
      api.get<ApiEnvelope<Scene[]>>('/scenes', { params: { size: 100 } }).catch(() => null),
    ])
    scenes.value = sceneResponse.data.data
    scripts.value = scriptResponse.data.data
    allScenes.value = catalogResponse ? catalogResponse.data.data : []
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
    <header class="page-heading"><div><p class="eyebrow">收藏</p><h1 class="page-title">个人收藏</h1><p class="page-lead">收藏的场景和话术都在这里，取消收藏不会删除原记录。</p></div></header>
    <div v-if="error" class="error-banner" role="alert">{{ error }} <button type="button" @click="load">重试</button></div>
    <div v-if="loading" class="panel skeleton loading" />
    <template v-else>
      <section class="panel collection-section">
        <div class="section-heading"><h2>场景</h2><span>{{ scenes.length }} 个</span></div>
        <div v-if="!scenes.length" class="empty-note">还没有收藏场景。<RouterLink to="/scenes">去场景训练看看 →</RouterLink></div>
        <div v-else class="scene-list">
          <article v-for="scene in scenes" :key="scene.id" class="scene-item">
            <div><span class="scene-category">{{ scene.category }}</span><h3><RouterLink :to="{ name: 'scenes', query: { sceneId: scene.id } }">{{ scene.title }}</RouterLink></h3><p>{{ scene.roleName }} · {{ scene.industry }} / {{ scene.position }}</p><span class="difficulty" :class="difficultyTone(scene.difficulty)">{{ scene.difficulty }}</span></div>
            <div class="item-actions"><RouterLink class="button secondary" :to="{ name: 'scenes', query: { sceneId: scene.id } }">进入场景 →</RouterLink><button type="button" @click="removeScene(scene)">取消收藏</button></div>
          </article>
        </div>
      </section>
      <section class="panel collection-section">
        <div class="section-heading"><h2>话术</h2><span>{{ scripts.length }} 个</span></div>
        <div v-if="!scripts.length" class="empty-note">还没有收藏话术。<RouterLink to="/scripts">去话术优化看看 →</RouterLink></div>
        <div v-else class="script-list"><ScriptVersionCard v-for="script in shownScripts" :key="script.id" :version="script" :scene-title="sceneTitles.get(script.sceneId ?? '') ?? '历史场景'" show-actions @favorite="removeScript" />
          <button v-if="remainingScripts" class="button secondary load-more" type="button" @click="scriptCount += 8">显示更多（还有 {{ remainingScripts }} 个）</button>
        </div>
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
.scene-item { display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 0;border:0;border-bottom:1px solid var(--divider);border-radius:0;background:transparent; }
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
<style scoped>
.favorites-page { max-width: 820px; }
.page-title { font-size: clamp(28px, 3vw, 36px); letter-spacing: -.02em; }
.page-lead { margin-top: 10px; font-size: 14px; }
.favorites-page .collection-section { padding: 0; margin: 34px 0 0; border: 0; background: transparent; box-shadow: none; }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; padding-bottom: 10px; border-bottom: 1px solid var(--divider); margin-bottom: 4px; }
.section-heading h2 { margin: 0; font-size: 18px; font-weight: 600; }
.section-heading > span { color: var(--text-3); font-size: 12.5px; }
.scene-list, .script-list { display: grid; gap: 0; }
.scene-item { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 16px 0; border: 0; border-bottom: 1px solid var(--divider); border-radius: 0; background: transparent; }
.scene-item h3 { margin: 4px 0; font-size: 17px; }
.scene-item h3 a { color: var(--text); }
.scene-item h3 a:hover { color: var(--accent-strong); }
.scene-item p { margin: 0 0 4px; color: var(--text-3); font-size: 12.5px; }
.scene-category { color: var(--text-3); font-size: 12px; }
.difficulty { font-size: 12px; font-weight: 500; }
.item-actions { gap: 12px; }
.item-actions .button { padding: 7px 12px; font-size: 12.5px; }
.item-actions button:not(.button) { font-size: 12.5px; color: var(--text-3); }
.empty-note { padding: 18px 0; color: var(--text-3); font-size: 13.5px; }
.empty-note a { color: var(--text-2); }
@media (max-width: 680px) { .scene-item { flex-direction: column; align-items: flex-start; } }
:root[data-theme='light'] .favorites-page .scene-item { background: transparent; border: 0; border-bottom: 1px solid var(--divider); box-shadow: none; }
:root[data-theme='light'] .favorites-page .collection-section { background: transparent; }
</style>
