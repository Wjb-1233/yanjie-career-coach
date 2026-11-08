<script setup lang="ts">
import { computed, shallowRef } from 'vue'

import SelectField from '@/components/ui/SelectField.vue'
import type { AdminSceneRecord, QuestionItem } from '@/lib/types'
import { DIFFICULTY_LEVELS } from '@/lib/sceneTaxonomy'

const props = defineProps<{ scenes: AdminSceneRecord[]; busy: boolean }>()
const emit = defineEmits<{ save: [value: Omit<AdminSceneRecord, 'id'>, id: string | null] }>()

const keyword = shallowRef('')
const selectedId = shallowRef<string | null>(null)
const questions = shallowRef<QuestionItem[]>([])
const dirty = shallowRef(false)

const filtered = computed(() => {
  const word = keyword.value.trim()
  const list = props.scenes.filter((item) => item.category !== '基础能力提升')
  if (!word) return list
  return list.filter((item) => `${item.title}${item.position}${item.industry}`.includes(word))
})
const selected = computed(() => props.scenes.find((item) => item.id === selectedId.value) ?? null)
const total = computed(() => props.scenes.reduce((sum, item) => sum + (item.questionBank?.length ?? 0), 0))
const dimensions = [
  { value: '', label: '不指定' },
  { value: '内容与逻辑', label: '内容与逻辑' },
  { value: '贴合问题', label: '贴合问题' },
  { value: '信息完整', label: '信息完整' },
  { value: '表达干净', label: '表达干净' },
]

function select(item: AdminSceneRecord): void {
  selectedId.value = item.id
  questions.value = (item.questionBank ?? []).map((q) => ({ ...q }))
  dirty.value = false
}

function add(): void {
  questions.value = [...questions.value, { text: '', dimension: '', difficulty: '' }]
  dirty.value = true
}

function remove(index: number): void {
  questions.value = questions.value.filter((_, i) => i !== index)
  dirty.value = true
}

function update(index: number, patch: Partial<QuestionItem>): void {
  questions.value = questions.value.map((item, i) => (i === index ? { ...item, ...patch } : item))
  dirty.value = true
}

function save(): void {
  const scene = selected.value
  if (!scene) return
  const list = questions.value
    .map((item) => ({
      text: item.text.trim(),
      dimension: item.dimension || '',
      difficulty: item.difficulty || '',
    }))
    .filter((item) => item.text)
  const { id: _id, ...rest } = scene
  emit('save', { ...rest, questionBank: list }, scene.id)
  dirty.value = false
}
</script>

<template>
  <section class="bank-manage">
    <aside class="bank-list panel">
      <header>
        <h2>题库管理</h2>
        <span>共 {{ total }} 道题</span>
      </header>
      <input v-model="keyword" class="field" type="search" placeholder="搜索场景、岗位或行业" aria-label="搜索场景" />
      <ul>
        <li v-for="item in filtered" :key="item.id">
          <button type="button" :class="{ active: item.id === selectedId }" @click="select(item)">
            <span class="scene-name">{{ item.title }}</span>
            <small>{{ item.position }} · {{ item.questionBank?.length ?? 0 }} 题</small>
          </button>
        </li>
      </ul>
    </aside>

    <div v-if="selected" class="bank-editor panel">
      <header>
        <div>
          <h2>{{ selected.title }}</h2>
          <span>{{ selected.category }} · {{ selected.position }}</span>
        </div>
        <div class="editor-actions">
          <button type="button" class="button secondary" :disabled="busy" @click="add">添加题目</button>
          <button type="button" class="button" :disabled="busy || !dirty" @click="save">保存题库</button>
        </div>
      </header>

      <p v-if="!questions.length" class="empty">这个场景还没有题目，点「添加题目」开始。</p>
      <ul v-else class="question-list">
        <li v-for="(question, index) in questions" :key="index">
          <span class="q-no num">{{ String(index + 1).padStart(2, '0') }}</span>
          <textarea
            :value="question.text"
            class="field"
            rows="2"
            maxlength="200"
            placeholder="题目正文"
            aria-label="题目正文"
            @input="update(index, { text: ($event.target as HTMLTextAreaElement).value })"
          />
          <div class="q-meta">
            <SelectField
              :model-value="question.dimension || ''"
              :options="dimensions"
              aria-label="考察维度"
              compact
              @update:model-value="update(index, { dimension: $event })"
            />
            <SelectField
              :model-value="question.difficulty || ''"
              :options="[{ value: '', label: '难度不限' }, ...DIFFICULTY_LEVELS.map((item) => ({ value: item.name, label: item.name }))]"
              aria-label="难度"
              compact
              @update:model-value="update(index, { difficulty: $event })"
            />
            <button type="button" class="remove" @click="remove(index)">删除</button>
          </div>
        </li>
      </ul>
    </div>
    <div v-else class="bank-editor panel empty">从左侧选一个场景，编辑它的题目。</div>
  </section>
</template>

<style scoped>
.bank-manage { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 16px; align-items: start; }
.bank-list { padding: 14px; display: grid; gap: 10px; max-height: 720px; overflow: auto; }
.bank-list header { display: flex; align-items: baseline; justify-content: space-between; }
.bank-list h2 { margin: 0; font-size: 15px; }
.bank-list span { color: var(--text-3); font-size: 11.5px; }
.bank-list ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.bank-list li button { width: 100%; text-align: left; border: 1px solid transparent; background: transparent; border-radius: 8px; padding: 8px 10px; cursor: pointer; display: grid; gap: 2px; color: var(--text); }
.bank-list li button.active { border-color: var(--accent); background: var(--accent-soft); }
.scene-name { font-size: 13px; }
.bank-list small { color: var(--text-3); font-size: 11px; }
.bank-editor { padding: 16px; }
.bank-editor header { display: flex; align-items: start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.bank-editor h2 { margin: 0; font-size: 17px; }
.bank-editor header span { color: var(--text-3); font-size: 12px; }
.editor-actions { display: flex; gap: 8px; }
.question-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
.question-list li { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 8px; border: 1px solid var(--border); border-radius: 10px; padding: 10px; }
.q-no { color: var(--text-3); font-size: 11.5px; padding-top: 4px; }
.q-meta { grid-column: 2; display: flex; gap: 8px; align-items: center; }
.remove { border: 0; background: transparent; color: var(--danger); font-size: 12px; cursor: pointer; }
.empty { color: var(--text-3); font-size: 13px; }
@media (max-width: 900px) { .bank-manage { grid-template-columns: 1fr; } }
</style>
