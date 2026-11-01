<script setup lang="ts">
import { computed, reactive, shallowRef } from 'vue'
import SelectField from '@/components/ui/SelectField.vue'
import type { AdminSceneRecord, QuestionItem } from '@/lib/types'
import { DIFFICULTY_LEVELS, normalizeSceneCategory, SCENE_CATEGORIES } from '@/lib/sceneTaxonomy'

const props = defineProps<{ scenes: AdminSceneRecord[]; busy: boolean }>()
const emit = defineEmits<{ save: [value: Omit<AdminSceneRecord, 'id'>, id: string | null]; deactivate: [id: string] }>()
const empty = (): Omit<AdminSceneRecord, 'id'> => ({ category: 'HR 初面', title: '', industry: '', position: '', roleName: '', difficulty: '中级', background: '', goal: '', coreIdea: '', tags: [], openingLine: '', questionBank: [], active: true })
const selectedId = shallowRef<string | null>(null)
const form = reactive(empty())
const tagText = shallowRef('')
const editing = computed(() => selectedId.value !== null)
const interviewScenes = computed(() => props.scenes.filter((item) => item.category !== '基础能力提升'))

function edit(item?: AdminSceneRecord) {
  selectedId.value = item?.id ?? null
  Object.assign(form, item
    ? { ...item, category: normalizeSceneCategory(item.category) === '全部' ? 'HR 初面' : normalizeSceneCategory(item.category), questionBank: (item.questionBank ?? []).map((q) => ({ ...q })) }
    : empty())
  tagText.value = item?.tags.join('，') ?? ''
}

function exportBank(): void {
  const payload = JSON.stringify(form.questionBank, null, 2)
  const blob = new Blob([payload], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${form.title || '场景'}-题库.json`
  link.click()
  URL.revokeObjectURL(url)
}

async function importBank(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    const raw = JSON.parse(await file.text())
    const list = Array.isArray(raw) ? raw : Array.isArray(raw?.questionBank) ? raw.questionBank : null
    if (!list) throw new Error('格式不对')
    form.questionBank = list
      .map((item: unknown) => (typeof item === 'string'
        ? { text: item, dimension: '', difficulty: '' }
        : {
            text: String((item as { text?: string }).text ?? ''),
            dimension: String((item as { dimension?: string }).dimension ?? ''),
            difficulty: String((item as { difficulty?: string }).difficulty ?? ''),
          }))
      .filter((item: { text: string }) => item.text.trim())
  } catch {
    window.alert('导入失败：需要一个 JSON 数组，元素形如 {"text":"题目","dimension":"逻辑性","difficulty":"中级"}')
  }
}

function addQuestion() {
  form.questionBank.push({ text: '', dimension: '', difficulty: '' })
}

function removeQuestion(index: number) {
  form.questionBank.splice(index, 1)
}

function submit() {
  const bank: QuestionItem[] = form.questionBank
    .filter((item) => item.text.trim())
    .slice(0, 3)
    .map((item) => ({ text: item.text.trim(), dimension: null, difficulty: null }))
  emit('save', {
    ...form,
    tags: tagText.value.split(/[，,]/).map((tag) => tag.trim()).filter(Boolean),
    questionBank: bank,
  }, selectedId.value)
  if (!selectedId.value) edit()
}
</script>

<template>
  <section class="catalog-grid">
    <form class="panel editor" @submit.prevent="submit">
      <p class="eyebrow">场景设计</p><h2>{{ editing ? '编辑训练场景' : '设计新场景' }}</h2><p class="editor-help">按招聘阶段设计面试问题，再指定行业、岗位和难度。基础能力练习在学员的能力提升页展示。</p>
      <label>场景名称<input v-model.trim="form.title" class="field" required minlength="2" maxlength="100"></label>
      <div class="two"><label>场景分类<SelectField :model-value="form.category" :options="SCENE_CATEGORIES.slice(1).map((item) => ({ value: item, label: item }))" aria-label="场景分类" @update:model-value="form.category = $event" /></label><label>难度<SelectField :model-value="form.difficulty" :options="DIFFICULTY_LEVELS.map((level) => ({ value: level.name, label: level.name, hint: level.cue }))" aria-label="难度" @update:model-value="form.difficulty = $event" /></label></div>
      <div class="two"><label>行业<input v-model.trim="form.industry" class="field" required></label><label>岗位<input v-model.trim="form.position" class="field" required></label></div>
      <label>面试官角色<input v-model.trim="form.roleName" class="field" required></label>
      <label>场景背景<textarea v-model.trim="form.background" class="field" rows="3" required minlength="10" /></label>
      <label>训练目标<textarea v-model.trim="form.goal" class="field" rows="2" required /></label>
      <label>场景核心思想（大模型每轮追问都围绕它）<textarea v-model.trim="form.coreIdea" class="field" rows="2" maxlength="500" placeholder="例如：考察候选人能否用可核对的事实说明自己的贡献，而不是空泛表态。" /></label>
      <label>开场问题（选填）<input v-model.trim="form.openingLine" class="field" placeholder="留空则由大模型根据场景背景与学员简历生成"></label>

      <div class="bank">
        <div class="bank-head">
          <div>
            <strong>必问问题</strong>
            <span>{{ editing ? '1–2 个即可，问完由大模型结合核心思想、JD 与简历继续追问' : '保存场景后，可以回来补必问题' }}</span>
          </div>
          <div class="bank-tools">
            <button class="button secondary compact" type="button" :disabled="form.questionBank.length >= 3" @click="addQuestion">+ 添加一题</button>
            <button
              class="button secondary compact"
              type="button"
              :disabled="!form.questionBank.length"
              :title="form.questionBank.length ? '导出当前必问题为 JSON' : '还没有必问题'"
              @click="exportBank"
            >导出</button>
            <label class="button secondary compact import-label">
              导入
              <input type="file" accept="application/json,.json" hidden @change="importBank">
            </label>
          </div>
        </div>
        <p v-if="!form.questionBank.length" class="bank-empty">
          {{ editing
            ? '还没有必问题。不设置时，面试官完全按核心思想与简历自由出题。'
            : '新建场景时可以先不设必问题，保存后回到这里补。' }}
        </p>
        <div v-for="(item, index) in form.questionBank" :key="index" class="bank-row">
          <span class="bank-index num">{{ String(index + 1).padStart(2, '0') }}</span>
          <input v-model="item.text" class="field" maxlength="300" placeholder="例如：先做一个简短的自我介绍">
          <button class="bank-remove" type="button" aria-label="删除这一题" @click="removeQuestion(index)">✕</button>
        </div>
      </div>

      <label>标签（逗号分隔）<input v-model="tagText" class="field"></label>
      <label class="check"><input v-model="form.active" type="checkbox"> 对学员开放</label>
      <div class="actions"><button class="button" :disabled="busy">{{ editing ? '保存修改' : '创建场景' }}</button><button v-if="editing" class="button secondary" type="button" @click="edit()">取消编辑</button></div>
    </form>
    <section class="panel listing"><header><div><p class="eyebrow">场景</p><h2>场景库</h2></div><span>{{ interviewScenes.length }} 条</span></header>
      <article v-for="item in interviewScenes" :key="item.id" class="row">
        <div>
          <strong>{{ item.title }}</strong>
          <small>{{ item.category }} · {{ item.industry }} · {{ item.position }} · {{ item.difficulty }}</small>
          <small class="bank-stat">{{ item.questionBank?.length ?? 0 }} 道题 · 被训练 {{ item.sessionCount ?? 0 }} 次 · 有覆盖 {{ item.coveredSessionCount ?? 0 }} 次</small>
        </div>
        <span class="tag" :class="{ inactive: !item.active }">{{ item.active ? '开放' : '停用' }}</span>
        <div class="actions"><button class="button secondary compact" @click="edit(item)">编辑</button><button v-if="item.active" class="button secondary compact" :disabled="busy" @click="emit('deactivate', item.id)">停用</button></div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.catalog-grid { display:grid; grid-template-columns:minmax(320px,.9fr) minmax(360px,1.1fr); gap:16px; align-items:start; } .editor,.listing { padding:22px; } h2 { margin:0 0 14px;font-size:22px;line-height:1.3; }.editor-help{margin:0 0 18px;color:var(--text-2);font-size:13px;line-height:1.7} label { display:grid; gap:6px; margin:11px 0; color:var(--text-2); font-size:12px; } textarea { resize:vertical; } .two { display:grid; grid-template-columns:1fr 1fr; gap:10px; } .check { display:flex; align-items:center; } .actions { display:flex; gap:8px; flex-wrap:wrap; } .row { padding:13px 0; border-top:1px solid var(--border); display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px 12px; align-items:center; } .row strong,.row small { display:block; } .row small { margin-top:4px; color:var(--text-2); } .row .actions { grid-column:1/-1; } .compact { min-height:32px; padding:5px 9px; font-size:12px; } header { display:flex; justify-content:space-between; align-items:center; } header > span { color:var(--text-2); font-size:12px; } .inactive { background:#f2eeee; color:#899; }
@media(max-width:900px){.catalog-grid{grid-template-columns:1fr}}
.inactive { border-color:rgba(248,113,113,.25);background:rgba(248,113,113,.09);color:#cf9a92; }
.row:hover { background:var(--overlay-1); }
.bank { margin:16px 0 6px; padding:14px; border:1px solid var(--border); border-radius:var(--radius); background:var(--bg-2); }
.bank-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.bank-head strong { display:block; color:var(--text); font-size:12.5px; font-weight:500; }
.bank-head span { display:block; margin-top:4px; color:var(--text-3); font-size:11px; }
.bank-empty { margin:12px 0 0; color:var(--text-3); font-size:11.5px; }
.bank-row { display:grid; grid-template-columns:26px minmax(0,1fr) 24px; align-items:center; gap:10px; margin-top:10px; }
.bank-index { color:var(--text-3); font-size:11px; }
.bank-remove { padding:0; border:0; background:transparent; color:var(--text-3); font-size:12px; cursor:pointer; }
.bank-remove:hover { color:var(--danger); }
.bank-stat { color:var(--text-3) !important; }

</style>
