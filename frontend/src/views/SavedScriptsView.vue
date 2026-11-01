<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { ArrowLeft } from 'lucide-vue-next'

import ScriptVersionCard from '@/components/scenes/ScriptVersionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Scene, ScriptVersion } from '@/lib/types'

const versions = shallowRef<ScriptVersion[]>([])
const scenes = shallowRef<Scene[]>([])
const loading = shallowRef(true)
const error = shallowRef('')
const page = shallowRef(1)
const PAGE_SIZE = 9

const sceneTitles = computed(() => new Map(scenes.value.map((scene) => [scene.id, scene.title])))
const pageCount = computed(() => Math.max(1, Math.ceil(versions.value.length / PAGE_SIZE)))
const paged = computed(() => versions.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

onMounted(load)

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [scriptResponse, sceneResponse] = await Promise.all([
      api.get<ApiEnvelope<ScriptVersion[]>>('/scripts'),
      api.get<ApiEnvelope<Scene[]>>('/scenes', { params: { size: 100 } }).catch(() => null),
    ])
    versions.value = scriptResponse.data.data
    scenes.value = sceneResponse ? sceneResponse.data.data : []
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

async function favorite(version: ScriptVersion): Promise<void> {
  try {
    const response = await api.post<ApiEnvelope<{ favorite: boolean }>>(`/scripts/${version.id}/favorite`)
    versions.value = versions.value.map((item) => item.id === version.id ? { ...item, favorite: response.data.data.favorite } : item)
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

async function remove(version: ScriptVersion): Promise<void> {
  if (!window.confirm('确定删除这个版本吗？删除后无法恢复。')) return
  try {
    await api.delete(`/scripts/${version.id}`)
    versions.value = versions.value.filter((item) => item.id !== version.id)
    if (page.value > pageCount.value) page.value = pageCount.value
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}
</script>

<template>
  <div class="page saved-page">
    <RouterLink class="back" to="/scripts"><ArrowLeft :size="13" :stroke-width="1.8" aria-hidden="true" /> 返回话术优化</RouterLink>

    <header class="page-heading">
      <div>
        <p class="eyebrow">话术版本</p>
        <h1 class="page-title">已保存的版本</h1>
        <p class="page-lead">每次在待优化里生成的三种风格都会存在这里；收藏的会同时出现在个人收藏。</p>
      </div>
      <span class="count num">{{ versions.length }} 个</span>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-if="loading" class="skeleton loading" />

    <EmptyState
      v-else-if="!versions.length"
      title="还没有保存过版本"
      description="在话术优化里挑一条待优化的回答，生成三种风格后就会出现在这里。"
    >
      <RouterLink class="button secondary" to="/scripts">去话术优化</RouterLink>
    </EmptyState>

    <template v-else>
      <div class="versions">
        <ScriptVersionCard
          v-for="version in paged"
          :key="version.id"
          :version="version"
          :scene-title="sceneTitles.get(version.sceneId ?? '') ?? '历史场景'"
          show-actions
          allow-delete
          @favorite="favorite"
          @remove="remove"
        />
      </div>

      <nav v-if="pageCount > 1" class="pager" aria-label="版本分页">
        <button class="text-btn" type="button" :disabled="page <= 1" @click="page -= 1">上一页</button>
        <span class="num">{{ page }} / {{ pageCount }}</span>
        <button class="text-btn" type="button" :disabled="page >= pageCount" @click="page += 1">下一页</button>
      </nav>
    </template>
  </div>
</template>

<style scoped>
.saved-page { max-width: 1040px; }
.back { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 18px; color: var(--text-3); font-size: 12px; }
.back:hover { color: var(--text-2); }
.count { color: var(--text-3); font-size: 12px; }
.loading { min-height: 220px; }
.versions { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
.pager { display: flex; align-items: center; justify-content: center; gap: 18px; padding-top: 22px; color: var(--text-3); font-size: 12px; }
.text-btn { padding: 0; border: 0; background: none; color: var(--text-3); font-size: 12px; cursor: pointer; }
.text-btn:disabled { opacity: .45; cursor: not-allowed; }
.text-btn:hover:not(:disabled) { color: var(--text); }
</style>
