<script setup lang="ts">
import { computed, reactive, shallowRef } from 'vue'
import type { AdminSceneRecord } from '@/lib/types'
import { DIFFICULTY_LEVELS, normalizeSceneCategory, SCENE_CATEGORIES } from '@/lib/sceneTaxonomy'

const props = defineProps<{ scenes: AdminSceneRecord[]; busy: boolean }>()
const emit = defineEmits<{ save: [value: Omit<AdminSceneRecord, 'id'>, id: string | null]; deactivate: [id: string] }>()
const empty = (): Omit<AdminSceneRecord, 'id'> => ({ category: 'HR 初面', title: '', industry: '', position: '', roleName: '', difficulty: '中级', background: '', goal: '', tags: [], openingLine: '', active: true })
const selectedId = shallowRef<string | null>(null)
const form = reactive(empty())
const tagText = shallowRef('')
const editing = computed(() => selectedId.value !== null)
const interviewScenes = computed(() => props.scenes.filter((item) => item.category !== '基础能力提升'))
function edit(item?: AdminSceneRecord) {
  selectedId.value = item?.id ?? null
  Object.assign(form, item ? { ...item, category: normalizeSceneCategory(item.category) === '全部' ? 'HR 初面' : normalizeSceneCategory(item.category) } : empty())
  tagText.value = item?.tags.join('，') ?? ''
}
function submit() {
  emit('save', { ...form, tags: tagText.value.split(/[，,]/).map((tag) => tag.trim()).filter(Boolean) }, selectedId.value)
  if (!selectedId.value) edit()
}
</script>

<template>
  <section class="catalog-grid">
    <form class="panel editor" @submit.prevent="submit">
      <p class="eyebrow">场景设计</p><h2>{{ editing ? '编辑训练场景' : '设计新场景' }}</h2><p class="editor-help">按招聘阶段设计面试问题，再指定行业、岗位和难度。基础能力练习在学员的能力提升页展示。</p>
      <label>场景名称<input v-model.trim="form.title" class="field" required minlength="2" maxlength="100"></label>
      <div class="two"><label>场景分类<select v-model="form.category" class="field" required><option v-for="category in SCENE_CATEGORIES.slice(1)" :key="category" :value="category">{{ category }}</option></select></label><label>难度<select v-model="form.difficulty" class="field" required><option v-for="level in DIFFICULTY_LEVELS" :key="level.name" :value="level.name">{{ level.name }} · {{ level.cue }}</option></select></label></div>
      <div class="two"><label>行业<input v-model.trim="form.industry" class="field" required></label><label>岗位<input v-model.trim="form.position" class="field" required></label></div>
      <label>面试官角色<input v-model.trim="form.roleName" class="field" required></label>
      <label>场景背景<textarea v-model.trim="form.background" class="field" rows="3" required minlength="10" /></label>
      <label>训练目标<textarea v-model.trim="form.goal" class="field" rows="2" required /></label>
      <label>开场问题<input v-model.trim="form.openingLine" class="field" required></label>
      <label>标签（逗号分隔）<input v-model="tagText" class="field"></label>
      <label class="check"><input v-model="form.active" type="checkbox"> 对学员开放</label>
      <div class="actions"><button class="button" :disabled="busy">{{ editing ? '保存修改' : '创建场景' }}</button><button v-if="editing" class="button secondary" type="button" @click="edit()">取消编辑</button></div>
    </form>
    <section class="panel listing"><header><div><p class="eyebrow">场景</p><h2>场景库</h2></div><span>{{ interviewScenes.length }} 条</span></header>
      <article v-for="item in interviewScenes" :key="item.id" class="row"><div><strong>{{ item.title }}</strong><small>{{ item.category }} · {{ item.industry }} · {{ item.position }} · {{ item.difficulty }}</small></div><span class="tag" :class="{ inactive: !item.active }">{{ item.active ? '开放' : '停用' }}</span><div class="actions"><button class="button secondary compact" @click="edit(item)">编辑</button><button v-if="item.active" class="button secondary compact" :disabled="busy" @click="emit('deactivate', item.id)">停用</button></div></article>
    </section>
  </section>
</template>

<style scoped>
.catalog-grid { display:grid; grid-template-columns:minmax(280px,.8fr) minmax(360px,1.2fr); gap:16px; align-items:start; } .editor,.listing { padding:22px; } h2 { margin:0 0 14px;font-size:22px;line-height:1.3; }.editor-help{margin:0 0 18px;color:var(--text-2);font-size:13px;line-height:1.7} label { display:grid; gap:6px; margin:11px 0; color:var(--text-2); font-size:12px; } textarea { resize:vertical; } .two { display:grid; grid-template-columns:1fr 1fr; gap:10px; } .check { display:flex; align-items:center; } .actions { display:flex; gap:8px; flex-wrap:wrap; } .row { padding:13px 0; border-top:1px solid var(--border); display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px 12px; align-items:center; } .row strong,.row small { display:block; } .row small { margin-top:4px; color:var(--text-2); } .row .actions { grid-column:1/-1; } .compact { min-height:32px; padding:5px 9px; font-size:12px; } header { display:flex; justify-content:space-between; align-items:center; } header > span { color:var(--text-2); font-size:12px; } .inactive { background:#f2eeee; color:#899; }
@media(max-width:900px){.catalog-grid{grid-template-columns:1fr}}
.inactive { border-color:rgba(248,113,113,.25);background:rgba(248,113,113,.09);color:#cf9a92; }
.row:hover { background:var(--overlay-1); }
</style>
