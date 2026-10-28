<script setup lang="ts">
import { computed, onMounted, reactive, shallowRef } from 'vue'
import { useRoute } from 'vue-router'

import ScriptScenePicker from '@/components/scenes/ScriptScenePicker.vue'
import ScriptVersionCard from '@/components/scenes/ScriptVersionCard.vue'
import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'
import type { ApiEnvelope, Scene, ScriptVersion } from '@/lib/types'

interface ScriptResult { versions: ScriptVersion[]; coachNote: string; degraded: boolean }

const route = useRoute()
const scenes = shallowRef<Scene[]>([])
const history = shallowRef<ScriptVersion[]>([])
const result = shallowRef<ScriptResult | null>(null)
const generating = shallowRef(false)
const error = shallowRef('')
const form = reactive({
  sceneId: String(route.query.sceneId ?? ''),
  objective: '回答当前面试问题，突出真实经历和个人行动',
  originalText: '',
  extraContext: '',
})
const sceneTitles = computed(() => new Map(scenes.value.map((scene) => [scene.id, scene.title])))
const styleHistory = computed(() => history.value.filter((item) => ['专业', '正式', '简洁', '亲和'].includes(item.style)))
const reviewHistory = computed(() => history.value.filter((item) => !['专业', '正式', '简洁', '亲和'].includes(item.style)))

onMounted(async () => {
  try {
    const [sceneResponse, historyResponse] = await Promise.all([
      api.get<ApiEnvelope<Scene[]>>('/scenes', { params: { size: 100 } }),
      api.get<ApiEnvelope<ScriptVersion[]>>('/scripts'),
    ])
    scenes.value = sceneResponse.data.data
    history.value = historyResponse.data.data
    if (!scenes.value.some((scene) => scene.id === form.sceneId)) form.sceneId = scenes.value[0]?.id ?? ''
  } catch (reason) { error.value = errorMessage(reason) }
})

async function generate(): Promise<void> {
  if (!form.sceneId || form.objective.trim().length < 2 || !form.originalText.trim() || generating.value) return
  generating.value = true
  error.value = ''
  try {
    const response = await api.post<ApiEnvelope<ScriptResult>>('/scripts/generate', {
      sceneId: form.sceneId,
      objective: form.objective,
      originalText: form.originalText.trim(),
      extraContext: form.extraContext || null,
    }, { timeout: MODEL_REQUEST_TIMEOUT_MS })
    result.value = response.data.data
    const refreshed = await api.get<ApiEnvelope<ScriptVersion[]>>('/scripts')
    history.value = refreshed.data.data
  } catch (reason) { error.value = errorMessage(reason) }
  finally { generating.value = false }
}

async function favorite(item: ScriptVersion): Promise<void> {
  try {
    const response = await api.post<ApiEnvelope<{ favorite: boolean }>>(`/scripts/${item.id}/favorite`)
    history.value = history.value.map((version) => version.id === item.id ? { ...version, favorite: response.data.data.favorite } : version)
  } catch (reason) { error.value = errorMessage(reason) }
}

async function remove(item: ScriptVersion): Promise<void> {
  if (!window.confirm('确定删除这个话术版本吗？删除后无法恢复。')) return
  try {
    await api.delete(`/scripts/${item.id}`)
    history.value = history.value.filter((version) => version.id !== item.id)
    if (result.value) result.value = { ...result.value, versions: result.value.versions.filter((version) => version.id !== item.id) }
  } catch (reason) { error.value = errorMessage(reason) }
}
</script>

<template>
  <div class="page scripts-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">话术优化</p>
        <h1 class="page-title">把你的原话，<br><span>改得更准确。</span></h1>
        <p class="page-lead">先选沟通对象和场景，再写下你的原话。专业、简洁、亲和三种表达分别突出不同重点，不补造经历。</p>
      </div>
    </header>
    <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
    <section class="panel studio">
      <ScriptScenePicker v-model="form.sceneId" :scenes="scenes" />
      <label>本次沟通目标<input v-model="form.objective" class="field" maxlength="500"></label>
      <label>我的原话<textarea v-model="form.originalText" class="field" rows="5" maxlength="2000" placeholder="粘贴你在训练中说过的话，或写下你现在会怎样回答…" /></label>
      <label>补充背景（可选）<input v-model="form.extraContext" class="field" maxlength="1000" placeholder="只填写真实的岗位、项目或沟通背景"></label>
      <div class="studio-actions"><span>请提供自己的原话，系统才会生成改写。</span><button class="button signal" type="button" :disabled="generating || !form.sceneId || form.objective.trim().length < 2 || !form.originalText.trim()" @click="generate">{{ generating ? '生成中…' : '生成三种优化版本' }}</button></div>
    </section>
    <section v-if="result?.versions.length" class="panel results">
      <div class="section-heading"><h2>三种表达，一眼看出侧重点</h2><p>看每版的适用场合与要点，选择最符合你真实想法的一版。</p></div>
      <div class="versions"><ScriptVersionCard v-for="version in result.versions" :key="version.id" :version="version" /></div>
      <p class="coach-note">教练提示：{{ result.coachNote }}<span v-if="result.degraded"> · 当前为本地演示模式</span></p>
    </section>
    <section class="panel history">
      <div class="history-heading"><div><h2>已保存的风格版本</h2><p>专业、简洁、亲和各有不同侧重点；收藏的版本也会出现在“个人收藏”。</p></div><span>{{ styleHistory.length }} 个</span></div>
      <div v-if="!styleHistory.length" class="empty">还没有风格版本。填写原话并生成后，三种表达会保存在这里。</div>
      <div v-else class="history-list">
        <ScriptVersionCard v-for="item in styleHistory" :key="item.id" :version="item" :scene-title="sceneTitles.get(item.sceneId ?? '') ?? '历史场景'" show-actions allow-delete @favorite="favorite" @remove="remove" />
      </div>
      <details v-if="reviewHistory.length" class="review-history"><summary>查看历史训练报告中的改写建议（{{ reviewHistory.length }}）</summary><div class="history-list"><ScriptVersionCard v-for="item in reviewHistory" :key="item.id" :version="item" :scene-title="sceneTitles.get(item.sceneId ?? '') ?? '历史场景'" show-actions allow-delete @favorite="favorite" @remove="remove" /></div></details>
    </section>
  </div>
</template>

<style scoped>
.scripts-page { max-width: 1120px; }
.page-title span { background:none;color:var(--text);font-weight:600; }
.studio,.results,.history { padding: 28px; margin-bottom: 22px; }
.studio { display: grid; gap: 18px; }
.studio > label { display: grid; gap: 8px; font-size: 13px; font-weight: 750; }
textarea { resize: vertical; min-height: 130px; line-height: 1.7; }
.studio-actions,.history-heading { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
.studio-actions span,.history-heading span,.coach-note,.section-heading p,.history-heading p { color: var(--text-2); font-size: 12px; }
.section-heading h2,.history h2 { margin: 0 0 8px; font-size: 24px; }
.section-heading p,.history-heading p { margin: 0 0 18px; }
.versions { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 12px; }
.history-list { display: grid; gap: 12px; }
.review-history { margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--border); }
.review-history summary { margin-bottom: 14px; color:var(--text-2); font-size: 13px; font-weight: 600; cursor: pointer; }
.coach-note { margin: 18px 0 0; line-height: 1.6; }
@media (max-width: 760px) { .versions { grid-template-columns: 1fr; }.studio-actions { align-items: stretch; flex-direction: column; }.studio,.results,.history { padding: 20px; } }
</style>
