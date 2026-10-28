<script setup lang="ts">
import { computed, reactive, shallowRef } from 'vue'

import type { AdminCourseRecord } from '@/lib/types'

const props = defineProps<{ courses: AdminCourseRecord[]; busy: boolean }>()
const emit = defineEmits<{
  save: [value: Omit<AdminCourseRecord, 'id' | 'progress' | 'completed'>, id: string | null]
  toggle: [course: AdminCourseRecord]
}>()

const dimensions = ['全部', '逻辑性', '得体性', '感染力', '针对性', '简洁度']
const filter = shallowRef('全部')
const formOpen = shallowRef(false)
const selectedId = shallowRef<string | null>(null)
const selectedTitle = shallowRef('')

const empty = () => ({ title: '', dimension: '逻辑性', minutes: 15, description: '', content: '', active: true })
const form = reactive(empty())

const visibleCourses = computed(() => filter.value === '全部'
  ? props.courses
  : props.courses.filter((item) => item.dimension === filter.value))

const counts = computed(() => props.courses.length)

function openCreate(): void {
  selectedId.value = null
  selectedTitle.value = ''
  Object.assign(form, empty())
  formOpen.value = true
}

function edit(item: AdminCourseRecord): void {
  selectedId.value = item.id
  selectedTitle.value = item.title
  Object.assign(form, {
    title: item.title,
    dimension: item.dimension,
    minutes: item.minutes,
    description: item.description,
    content: item.content,
    active: item.active,
  })
  formOpen.value = true
}

function closeForm(): void {
  formOpen.value = false
  selectedId.value = null
  selectedTitle.value = ''
  Object.assign(form, empty())
}

function submit(): void {
  // 简介与时长在学员端已不展示：简介取正文首段兜底，时长保持不变
  const description = form.description.trim().length >= 5 ? form.description.trim() : form.content.trim().slice(0, 80)
  emit('save', {
    title: form.title.trim(),
    dimension: form.dimension,
    minutes: form.minutes || 15,
    description,
    content: form.content.trim(),
    active: form.active,
  }, selectedId.value)
  closeForm()
}
</script>

<template>
  <section class="courses">
    <header class="section-head">
      <div>
        <p class="eyebrow">微课素材</p>
        <h2>微课库</h2>
        <p class="hint">学员看到的是根据这里的标题与正文生成的个性化三步课程，而不是正文本身。</p>
      </div>
      <button class="button" type="button" :disabled="busy" @click="openCreate">新增微课</button>
    </header>

    <form v-if="formOpen" class="editor" @submit.prevent="submit">
      <header class="editor-head">
        <h3>{{ selectedId ? '编辑微课' : '新增微课' }}</h3>
        <span v-if="selectedTitle" class="editor-subject">{{ selectedTitle }}</span>
      </header>

      <label class="field-label">
        课程名称
        <input v-model.trim="form.title" class="field" required maxlength="120" placeholder="例如：金字塔表达：先结论，再证据" />
      </label>

      <label class="field-label">
        评分维度
        <select v-model="form.dimension" class="field">
          <option>逻辑性</option>
          <option>得体性</option>
          <option>感染力</option>
          <option>针对性</option>
          <option>简洁度</option>
        </select>
      </label>

      <label class="field-label">
        课程正文
        <textarea
          v-model.trim="form.content"
          class="field"
          rows="8"
          required
          minlength="20"
          placeholder="写清这一维度的方法要点，用分号或换行分隔；模型会据此生成三步课程。"
        />
        <small class="field-help">{{ form.content.length }} / 10000 字 · 至少 20 字，建议 150–400 字</small>
      </label>

      <label class="check"><input v-model="form.active" type="checkbox" /> 对学员开放</label>

      <div class="editor-actions">
        <button class="button" :disabled="busy">{{ selectedId ? '保存修改' : '创建微课' }}</button>
        <button class="button secondary" type="button" @click="closeForm">取消</button>
      </div>
    </form>

    <div class="filters" role="tablist" aria-label="按评分维度筛选微课">
      <button
        v-for="item in dimensions"
        :key="item"
        type="button"
        role="tab"
        class="chip"
        :class="{ active: filter === item }"
        :aria-selected="filter === item"
        @click="filter = item"
      >{{ item }}</button>
      <span class="count">{{ counts }} 条</span>
    </div>

    <ul v-if="visibleCourses.length" class="list">
      <li v-for="item in visibleCourses" :key="item.id" class="row" :class="{ inactive: !item.active }">
        <div class="row-main">
          <strong>{{ item.title }}</strong>
          <span class="meta">{{ item.dimension }} · {{ item.active ? '开放中' : '已停用' }}</span>
        </div>
        <div class="row-actions">
          <button type="button" class="text-btn" :disabled="busy" @click="edit(item)">编辑</button>
          <button type="button" class="text-btn" :class="{ danger: item.active }" :disabled="busy" @click="emit('toggle', item)">
            {{ item.active ? '停用' : '启用' }}
          </button>
        </div>
      </li>
    </ul>
    <p v-else class="empty">这个维度下还没有微课。</p>
  </section>
</template>

<style scoped>
.courses { display: block; }

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--divider);
}
.section-head h2 { margin: 6px 0 0; color: var(--text); font-size: 22px; font-weight: 600; letter-spacing: -.01em; }
.hint { max-width: 52ch; margin: 10px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.8; }

.editor {
  margin-top: 18px;
  padding: 24px 26px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
  display: grid;
  gap: 14px;
}
.editor-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 2px; }
.editor-head h3 { margin: 0; color: var(--text); font-size: 15px; font-weight: 500; }
.editor-subject { color: var(--text-3); font-size: 12px; }
.field-help { color: var(--text-3); font-size: 11px; line-height: 1.6; }
.check { display: flex; align-items: center; gap: 8px; color: var(--text-2); font-size: 12px; }
.editor-actions { display: flex; gap: 10px; margin-top: 4px; }
textarea { resize: vertical; }

.filters { display: flex; align-items: center; gap: 6px; margin-top: 22px; flex-wrap: wrap; }
.chip {
  padding: 6px 12px;
  border: 1px solid transparent;
  border-radius: 3px;
  background: transparent;
  color: var(--text-3);
  font-size: 12px;
  letter-spacing: .04em;
  cursor: pointer;
  transition: color var(--ease), border-color var(--ease), background var(--ease);
}
.chip:hover { color: var(--text-2); border-color: var(--border); }
.chip.active { border-color: var(--border-bright); background: var(--overlay-2); color: var(--text); }
.count { margin-left: auto; color: var(--text-3); font-size: 11px; letter-spacing: .06em; }

.list { margin: 10px 0 0; padding: 0; list-style: none; }
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 2px;
  border-bottom: 1px solid var(--divider);
  transition: background var(--ease);
}
.row:hover { background: var(--overlay-1); }
.row-main { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.row-main strong { color: var(--text); font-size: 14px; font-weight: 500; line-height: 1.5; }
.meta { color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.row.inactive .row-main strong { color: var(--text-3); }

.row-actions { display: flex; gap: 18px; flex: none; }
.text-btn {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-3);
  font-size: 12px;
  letter-spacing: .04em;
  cursor: pointer;
  transition: color var(--ease);
}
.text-btn:hover { color: var(--text); }
.text-btn.danger:hover { color: var(--danger); }
.text-btn:disabled { opacity: .5; cursor: not-allowed; }

.empty { margin: 24px 0 0; color: var(--text-3); font-size: 13px; }

@media (max-width: 640px) {
  .section-head { align-items: flex-start; flex-direction: column; gap: 14px; }
  .row { flex-direction: column; align-items: flex-start; gap: 10px; }
  .row-actions { gap: 22px; }
  .count { margin-left: 0; }
}
</style>
