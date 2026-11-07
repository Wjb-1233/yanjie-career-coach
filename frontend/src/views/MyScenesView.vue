<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

const router = useRouter()
const scenes = shallowRef<Scene[]>([])
const loading = shallowRef(true)
const error = shallowRef('')
const saving = shallowRef(false)
const editingId = ref<string | null>(null)
const showForm = ref(false)

interface QuestionDraft { text: string; dimension: string }
interface FormState {
  title: string
  industry: string
  position: string
  roleName: string
  category: string
  difficulty: string
  background: string
  goal: string
  openingLine: string
  competency: string
  questions: QuestionDraft[]
}

const CATEGORIES = ['HR 初面', '技术一面', '技术二面/复面', '交叉面/总监面', 'HRBP/HR 终面', '大老板/高管终面', '基础能力提升', '自定义']
const DIMENSIONS = ['内容与逻辑', '贴合问题', '信息完整', '表达干净']

function blank(): FormState {
  return {
    title: '',
    industry: '互联网',
    position: '',
    roleName: '面试官',
    category: '技术一面',
    difficulty: '中级',
    background: '',
    goal: '',
    openingLine: '',
    competency: '',
    questions: [
      { text: '', dimension: '内容与逻辑' },
      { text: '', dimension: '信息完整' },
    ],
  }
}

const form = ref<FormState>(blank())

// P1：粘贴 JD 起草
const jdText = ref('')
const jdPosition = ref('')
const drafting = ref(false)
const draftNote = ref('')

async function draftFromJd(): Promise<void> {
  if (drafting.value) return
  if (jdText.value.trim().length < 80) {
    error.value = 'JD 太短了，至少粘贴 80 字，否则生成的问题会很空'
    return
  }
  drafting.value = true
  error.value = ''
  try {
    const response = await api.post<ApiEnvelope<{
      title: string
      industry: string
      position: string
      roleName: string
      category: string
      difficulty: string
      background: string
      goal: string
      openingLine: string
      competency: string | null
      questions: Array<{ text: string; dimension: string }>
      degraded: boolean
    }>>('/my-scenes/draft-from-jd', {
      jd: jdText.value.trim(),
      position: jdPosition.value.trim() || '目标岗位',
    })
    const data = response.data.data
    form.value = {
      title: data.title,
      industry: data.industry,
      position: data.position,
      roleName: data.roleName,
      category: data.category,
      difficulty: data.difficulty,
      background: data.background,
      goal: data.goal,
      openingLine: data.openingLine,
      competency: data.competency ?? '',
      questions: data.questions.map((item) => ({ text: item.text, dimension: item.dimension || '内容与逻辑' })),
    }
    draftNote.value = data.degraded
      ? '模型暂不可用，已按 JD 条目生成草稿，请逐条改成你想要的问题。'
      : 'AI 已按 JD 起草，请逐条确认后再保存；不符合的要求直接改掉。'
    showForm.value = true
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    drafting.value = false
  }
}
const count = computed(() => scenes.value.length)

async function load(): Promise<void> {
  loading.value = true
  try {
    const response = await api.get<ApiEnvelope<{ items: Scene[]; count: number; limit: number }>>('/my-scenes')
    scenes.value = response.data.data.items
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editingId.value = null
  form.value = blank()
  showForm.value = true
  error.value = ''
}

function openEdit(scene: Scene): void {
  editingId.value = scene.id
  const bank = (scene as unknown as { questionBank?: Array<{ text?: string; dimension?: string } | string> }).questionBank ?? []
  form.value = {
    title: scene.title,
    industry: scene.industry,
    position: scene.position,
    roleName: scene.roleName,
    category: scene.category,
    difficulty: scene.difficulty,
    background: scene.background,
    goal: scene.goal,
    openingLine: scene.openingLine ?? '',
    competency: scene.competency ?? '',
    questions: bank.map((item) => typeof item === 'string'
      ? { text: item, dimension: '内容与逻辑' }
      : { text: item.text ?? '', dimension: item.dimension ?? '内容与逻辑' }),
  }
  if (!form.value.questions.length) form.value.questions = blank().questions
  showForm.value = true
  error.value = ''
}

function addQuestion(): void {
  if (form.value.questions.length >= 8) return
  form.value.questions.push({ text: '', dimension: '内容与逻辑' })
}

function removeQuestion(index: number): void {
  if (form.value.questions.length <= 2) return
  form.value.questions.splice(index, 1)
}

async function save(): Promise<void> {
  if (saving.value) return
  const questions = form.value.questions
    .map((item) => ({ text: item.text.trim(), dimension: item.dimension || null }))
    .filter((item) => item.text.length >= 2)
  if (questions.length < 2) {
    error.value = '至少写两个不同的问题'
    return
  }
  saving.value = true
  error.value = ''
  const payload = {
    ...form.value,
    questions,
    competency: form.value.competency.trim() || null,
  }
  try {
    if (editingId.value) {
      await api.patch(`/my-scenes/${editingId.value}`, payload)
    } else {
      await api.post('/my-scenes', payload)
    }
    showForm.value = false
    editingId.value = null
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function remove(scene: Scene): Promise<void> {
  if (!confirm(`删除「${scene.title}」？已有训练记录会保留。`)) return
  try {
    await api.delete(`/my-scenes/${scene.id}`)
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

async function practice(scene: Scene): Promise<void> {
  try {
    const created = await api.post<ApiEnvelope<{ id: string }>>('/training-sessions', { sceneId: scene.id })
    await router.push(`/training/${created.data.data.id}`)
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

onMounted(load)
</script>

<template>
  <div class="page my-scenes">
    <header class="page-heading">
      <div>
        <p class="eyebrow">我的场景</p>
        <h1 class="page-title">按你自己的岗位，<br /><span>练一场真的。</span></h1>
        <p class="page-lead">自建场景只属于你，可以随时改、随时练，也会进入个性化计划。</p>
      </div>
      <div class="hero-actions">
        <span class="count">{{ count }} / 50</span>
        <button class="button" type="button" @click="openCreate">新建场景</button>
      </div>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>
    <p v-if="loading" class="hint">正在加载…</p>

    <section v-if="!loading && !scenes.length && !showForm" class="empty panel">
      <h2>还没有自建场景</h2>
      <p>把要面的岗位、JD 要求、想问的问题填进去，就能按自己的情况练。</p>
      <button class="button" type="button" @click="openCreate">创建第一个场景</button>
    </section>

    <section class="jd-draft panel" aria-label="从 JD 起草">
      <header>
        <div>
          <h2>粘贴 JD，自动起草</h2>
          <p>只根据 JD 里的要求出题，不编造公司信息；生成后仍可逐条修改。</p>
        </div>
        <button class="button" type="button" :disabled="drafting" @click="draftFromJd">
          {{ drafting ? '正在起草…' : '生成草稿' }}
        </button>
      </header>
      <div class="jd-row">
        <input v-model="jdPosition" class="field" maxlength="40" placeholder="目标岗位（可选）" />
        <textarea v-model="jdText" class="field" rows="4" maxlength="4000" placeholder="把岗位 JD 粘贴到这里（至少 80 字）" />
      </div>
      <p v-if="draftNote" class="draft-note">{{ draftNote }}</p>
    </section>

    <section v-if="showForm" class="editor panel">
      <header>
        <h2>{{ editingId ? '编辑场景' : '新建场景' }}</h2>
        <button type="button" class="mini" @click="showForm = false">收起</button>
      </header>

      <div class="grid">
        <label>标题<input v-model="form.title" class="field" maxlength="60" placeholder="例：字节跳动-后端开发-二面" /></label>
        <label>行业<input v-model="form.industry" class="field" maxlength="30" /></label>
        <label>岗位<input v-model="form.position" class="field" maxlength="40" placeholder="例：后端开发工程师" /></label>
        <label>面试官角色<input v-model="form.roleName" class="field" maxlength="30" /></label>
        <label>面试阶段
          <select v-model="form.category" class="field">
            <option v-for="item in CATEGORIES" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label>难度
          <select v-model="form.difficulty" class="field">
            <option v-for="item in ['入门', '中级', '进阶']" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
      </div>

      <label>背景<textarea v-model="form.background" class="field" rows="2" maxlength="500" placeholder="公司/团队/业务背景；留空会按岗位自动补一句" /></label>
      <label>考察目标<textarea v-model="form.goal" class="field" rows="2" maxlength="300" placeholder="这场想练什么" /></label>
      <label>开场白<input v-model="form.openingLine" class="field" maxlength="200" placeholder="留空由面试官开场" /></label>

      <div class="questions">
        <div class="questions-head">
          <span>必问题（2–8 条）</span>
          <button type="button" class="mini" :disabled="form.questions.length >= 8" @click="addQuestion">加一条</button>
        </div>
        <div v-for="(item, index) in form.questions" :key="index" class="question-row">
          <span class="q-no num">{{ index + 1 }}</span>
          <input v-model="item.text" class="field" maxlength="120" placeholder="这道题问什么" />
          <select v-model="item.dimension" class="field dim">
            <option v-for="dim in DIMENSIONS" :key="dim" :value="dim">{{ dim }}</option>
          </select>
          <button type="button" class="mini" :disabled="form.questions.length <= 2" @click="removeQuestion(index)">删</button>
        </div>
      </div>

      <div class="editor-actions">
        <button class="button" type="button" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存场景' }}</button>
        <button class="button secondary" type="button" @click="showForm = false">取消</button>
      </div>
    </section>

    <section v-if="scenes.length" class="scene-list">
      <article v-for="scene in scenes" :key="scene.id" class="scene-item panel">
        <div class="scene-main">
          <h3>{{ scene.title }}</h3>
          <p class="meta">{{ scene.difficulty }} · {{ scene.category }} · {{ scene.roleName }}</p>
          <p class="goal">{{ scene.goal }}</p>
        </div>
        <div class="scene-actions">
          <button class="button" type="button" @click="practice(scene)">试练</button>
          <button class="button secondary" type="button" @click="openEdit(scene)">编辑</button>
          <button class="mini danger" type="button" @click="remove(scene)">删除</button>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
.my-scenes .hero-actions { display: flex; align-items: center; gap: 14px; }
.count { color: var(--text-3); font-size: 12px; }
.empty { display: grid; gap: 10px; justify-items: start; margin-top: 28px; }
.empty h2 { margin: 0; font-size: 16px; }
.empty p { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
.editor { margin-top: 22px; display: grid; gap: 12px; border: 1px solid var(--border); border-radius: 12px; }
.editor header { display: flex; align-items: baseline; justify-content: space-between; }
.editor h2 { margin: 0; font-size: 16px; }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
label { display: grid; gap: 6px; color: var(--text-3); font-size: 11.5px; }
.questions { display: grid; gap: 8px; padding-top: 8px; border-top: 1px solid var(--divider); }
.questions-head { display: flex; align-items: baseline; justify-content: space-between; color: var(--text-2); font-size: 12px; }
.question-row { display: grid; grid-template-columns: 22px minmax(0, 1fr) 130px 40px; gap: 8px; align-items: center; }
.q-no { color: var(--text-3); font-size: 11px; }
.dim { min-width: 0; }
.editor-actions { display: flex; gap: 10px; }
.scene-list { display: grid; gap: 12px; margin-top: 22px; }
.scene-item { display: flex; align-items: center; justify-content: space-between; gap: 18px; border: 1px solid var(--border); border-radius: 12px; }
.scene-main h3 { margin: 0 0 4px; font-size: 15px; }
.meta { margin: 0; color: var(--text-3); font-size: 11.5px; }
.goal { margin: 6px 0 0; color: var(--text-2); font-size: 12.5px; line-height: 1.7; }
.scene-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.mini.danger { color: var(--error, #b4553f); }
.hint { color: var(--text-3); font-size: 12.5px; }
@media (max-width: 880px) {
  .grid { grid-template-columns: 1fr; }
  .question-row { grid-template-columns: 20px minmax(0, 1fr); }
  .dim, .mini { grid-column: 2; }
  .scene-item { flex-direction: column; align-items: flex-start; }
}

.jd-draft { margin: 22px 0 0; display: grid; gap: 10px; border: 1px solid var(--border); border-radius: 12px; }
.jd-draft header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.jd-draft h2 { margin: 0; font-size: 15px; }
.jd-draft p { margin: 4px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.7; }
.jd-row { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 10px; }
.draft-note { color: var(--accent-strong) !important; }
@media (max-width: 880px) { .jd-row { grid-template-columns: 1fr; } }
</style>
