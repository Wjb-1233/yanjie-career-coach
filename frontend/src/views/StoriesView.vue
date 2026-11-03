<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import { api, errorMessage } from '@/lib/api'
import EmptyState from '@/components/ui/EmptyState.vue'
import type { ApiEnvelope } from '@/lib/types'

interface Story {
  id: string
  title: string
  situation: string
  task: string
  action: string
  result: string
  tags: string[]
  usageCount: number
  updatedAt: string
}

const route = useRoute()
const stories = shallowRef<Story[]>([])
const loading = shallowRef(true)
const error = shallowRef('')
const busy = shallowRef('')
const editing = shallowRef<Partial<Story> | null>(null)
const keyword = shallowRef('')

const filtered = computed(() => {
  const word = keyword.value.trim()
  if (!word) return stories.value
  return stories.value.filter((story) =>
    [story.title, story.situation, story.task, story.action, story.result, ...story.tags].join(' ').includes(word),
  )
})

const coverage = computed(() => {
  const total = stories.value.length
  const quantified = stories.value.filter((story) => /\d/.test(story.result)).length
  const reused = stories.value.filter((story) => story.usageCount > 0).length
  return { total, quantified, reused }
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const response = await api.get<ApiEnvelope<Story[]>>('/stories')
    stories.value = response.data.data
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

function startCreate(): void {
  editing.value = { title: '', situation: '', task: '', action: '', result: '', tags: [] }
}

function startEdit(story: Story): void {
  editing.value = { ...story }
}

async function save(): Promise<void> {
  const draft = editing.value
  if (!draft || !draft.title?.trim() || !draft.action?.trim()) {
    error.value = '标题和行动描述不能为空'
    return
  }
  busy.value = 'save'
  error.value = ''
  const payload = {
    title: draft.title.trim(),
    situation: draft.situation ?? '',
    task: draft.task ?? '',
    action: draft.action.trim(),
    result: draft.result ?? '',
    tags: draft.tags ?? [],
  }
  try {
    if (draft.id) {
      await api.patch(`/stories/${draft.id}`, payload)
    } else {
      await api.post('/stories', payload)
    }
    editing.value = null
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = ''
  }
}

async function remove(story: Story): Promise<void> {
  if (!window.confirm(`删除「${story.title}」？`)) return
  busy.value = story.id
  try {
    await api.delete(`/stories/${story.id}`)
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = ''
  }
}

async function markUsed(story: Story): Promise<void> {
  busy.value = story.id
  try {
    await api.post(`/stories/${story.id}/use`)
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = ''
  }
}

async function extractFromSession(sessionId: string): Promise<void> {
  busy.value = 'extract'
  try {
    await api.post('/stories/extract', { session_id: sessionId })
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = ''
  }
}

onMounted(async () => {
  await load()
  const sessionId = typeof route.query.sessionId === 'string' ? route.query.sessionId : ''
  if (sessionId) {
    await extractFromSession(sessionId)
  }
})
</script>

<template>
  <div class="page stories-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">故事库</p>
        <h1 class="page-title">把讲过的经历，变成能反复用的故事</h1>
        <p class="page-lead">面试里真正拉开差距的是具体例子。这里按 STAR 结构收好你的经历，上场前不用现编。</p>
      </div>
      <button class="button" type="button" @click="startCreate">新增故事</button>
    </header>

    <div class="stats">
      <div class="panel"><strong>{{ coverage.total }}</strong><span>已收录故事</span></div>
      <div class="panel"><strong>{{ coverage.quantified }}</strong><span>结果带数字</span></div>
      <div class="panel"><strong>{{ coverage.reused }}</strong><span>已用过至少一次</span></div>
    </div>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section v-if="editing" class="panel editor">
      <h2>{{ editing.id ? '编辑故事' : '新增故事' }}</h2>
      <label>标题<input v-model="editing.title" class="field" maxlength="40" placeholder="如：订单系统降延迟" /></label>
      <label>情境（S）<textarea v-model="editing.situation" class="field" rows="2" placeholder="当时是什么背景、什么问题" /></label>
      <label>任务（T）<textarea v-model="editing.task" class="field" rows="2" placeholder="你要解决什么、目标是什么" /></label>
      <label>行动（A）<textarea v-model="editing.action" class="field" rows="3" placeholder="你具体做了什么，用了什么方法" /></label>
      <label>结果（R）<textarea v-model="editing.result" class="field" rows="2" placeholder="结果如何，尽量带数字" /></label>
      <div class="editor-actions">
        <button class="button" type="button" :disabled="busy === 'save'" @click="save">{{ busy === 'save' ? '保存中…' : '保存' }}</button>
        <button class="button secondary" type="button" @click="editing = null">取消</button>
      </div>
    </section>

    <section class="panel list-panel">
      <header class="list-head">
        <h2>我的故事</h2>
        <input v-model="keyword" class="field search" placeholder="搜索标题、内容或标签" />
      </header>

      <div v-if="loading" class="skeleton loading-line" />
      <EmptyState
        v-else-if="!filtered.length"
        title="还没有故事"
        description="故事库用来放你已经讲顺的项目经历。可以从训练报告一键沉淀，也可以手动补一条。"
        action-label="去训练"
        action-to="/scenes"
      />

      <ul v-else class="story-list">
        <li v-for="story in filtered" :key="story.id" class="story">
          <header>
            <h3>{{ story.title }}</h3>
            <span class="usage">用过 {{ story.usageCount }} 次</span>
          </header>
          <dl>
            <div v-if="story.situation"><dt>S</dt><dd>{{ story.situation }}</dd></div>
            <div v-if="story.task"><dt>T</dt><dd>{{ story.task }}</dd></div>
            <div><dt>A</dt><dd>{{ story.action }}</dd></div>
            <div><dt>R</dt><dd :class="{ quantified: /\d/.test(story.result) }">{{ story.result }}</dd></div>
          </dl>
          <footer>
            <span v-for="tag in story.tags" :key="tag" class="tag">{{ tag }}</span>
            <div class="actions">
              <button type="button" class="link" @click="markUsed(story)">记一次使用</button>
              <button type="button" class="link" @click="startEdit(story)">编辑</button>
              <button type="button" class="link danger" @click="remove(story)">删除</button>
            </div>
          </footer>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.stories-page { display: grid; gap: 18px; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stats div { padding: 16px 18px; display: grid; gap: 6px; }
.stats strong { font-size: 26px; font-weight: 750; }
.stats span { color: var(--text-2); font-size: 12px; }
.editor { padding: 22px; display: grid; gap: 12px; }
.editor h2 { margin: 0; font-family: var(--font-display); font-size: 18px; }
.editor label { display: grid; gap: 6px; color: var(--text-3); font-size: 12px; }
.editor-actions { display: flex; gap: 10px; }
.list-panel { padding: 22px; }
.list-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 16px; }
.list-head h2 { margin: 0; font-family: var(--font-display); font-size: 18px; }
.search { max-width: 260px; }
.empty { margin: 0; padding: 26px 0; text-align: center; color: var(--text-3); font-size: 13px; }
.story-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; }
.story { padding: 16px 18px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-2); display: grid; gap: 10px; }
.story header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.story h3 { margin: 0; font-size: 15px; font-weight: 650; }
.usage { color: var(--text-3); font-size: 11.5px; }
.story dl { margin: 0; display: grid; gap: 6px; }
.story dl div { display: grid; grid-template-columns: 22px 1fr; gap: 8px; }
.story dt { color: var(--accent-strong); font-size: 11.5px; font-weight: 700; }
.story dd { margin: 0; color: var(--text-2); font-size: 12.5px; line-height: 1.8; }
.story dd.quantified { color: var(--text); }
.story footer { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.story .tag { padding: 2px 9px; border: 1px solid var(--line); border-radius: 999px; color: var(--text-3); font-size: 11px; }
.actions { margin-left: auto; display: flex; gap: 14px; }
.link { padding: 0; border: 0; background: none; color: var(--primary-hover); font-size: 12px; cursor: pointer; }
.link.danger { color: #a4342a; }
@media (max-width: 860px) { .stats { grid-template-columns: 1fr; } .list-head { flex-direction: column; align-items: stretch; } }
</style>
