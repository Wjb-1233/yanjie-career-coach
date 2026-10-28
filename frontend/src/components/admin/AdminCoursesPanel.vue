<script setup lang="ts">
import { computed, reactive, shallowRef } from 'vue'
import type { AdminCourseRecord } from '@/lib/types'

defineProps<{ courses: AdminCourseRecord[]; busy: boolean }>()
const emit = defineEmits<{ save: [value: Omit<AdminCourseRecord, 'id' | 'progress' | 'completed'>, id: string | null]; deactivate: [id: string] }>()
const empty = () => ({ title: '', dimension: '逻辑性', minutes: 15, description: '', content: '', active: true })
const selectedId = shallowRef<string | null>(null)
const form = reactive(empty())
const editing = computed(() => selectedId.value !== null)
function edit(item?: AdminCourseRecord) {
  selectedId.value = item?.id ?? null
  Object.assign(form, item ? { title: item.title, dimension: item.dimension, minutes: item.minutes, description: item.description, content: item.content, active: item.active } : empty())
}
function submit() {
  emit('save', { ...form }, selectedId.value)
  if (!selectedId.value) edit()
}
</script>

<template>
  <section class="catalog-grid">
    <form class="panel editor" @submit.prevent="submit"><p class="eyebrow">微课</p><h2>{{ editing ? '编辑微课' : '新增微课' }}</h2>
      <label>课程名称<input v-model.trim="form.title" class="field" required maxlength="120"></label>
      <div class="two"><label>评分维度<select v-model="form.dimension" class="field"><option>逻辑性</option><option>得体性</option><option>感染力</option><option>针对性</option><option>简洁度</option></select></label><label>学习时长（分钟）<input v-model.number="form.minutes" class="field" type="number" min="1" max="240" required></label></div>
      <label>课程简介<textarea v-model.trim="form.description" class="field" rows="2" required minlength="5" /></label>
      <label>课程正文<textarea v-model.trim="form.content" class="field" rows="7" required minlength="20" /></label>
      <label class="check"><input v-model="form.active" type="checkbox"> 对学员开放</label>
      <div class="actions"><button class="button" :disabled="busy">{{ editing ? '保存修改' : '创建微课' }}</button><button v-if="editing" class="button secondary" type="button" @click="edit()">取消编辑</button></div>
    </form>
    <section class="panel listing"><header><div><p class="eyebrow">课程</p><h2>课程库</h2></div><span>{{ courses.length }} 条</span></header>
      <article v-for="item in courses" :key="item.id" class="row"><div><strong>{{ item.title }}</strong><small>{{ item.dimension }} · {{ item.minutes }} 分钟</small></div><span class="tag" :class="{ inactive: !item.active }">{{ item.active ? '开放' : '停用' }}</span><div class="actions"><button class="button secondary compact" @click="edit(item)">编辑</button><button v-if="item.active" class="button secondary compact" :disabled="busy" @click="emit('deactivate', item.id)">停用</button></div></article>
    </section>
  </section>
</template>

<style scoped>
.catalog-grid { display:grid; grid-template-columns:minmax(280px,.8fr) minmax(360px,1.2fr); gap:16px; align-items:start; } .editor,.listing { padding:22px; } h2 { margin:0 0 18px; font:700 22px var(--font-ui); } label { display:grid; gap:6px; margin:11px 0; color:var(--ink-soft); font-size:12px; } textarea { resize:vertical; } .two { display:grid; grid-template-columns:1fr 1fr; gap:10px; } .check { display:flex; align-items:center; } .actions { display:flex; gap:8px; flex-wrap:wrap; } .row { padding:13px 0; border-top:1px solid var(--line); display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px 12px; align-items:center; } .row strong,.row small { display:block; } .row small { margin-top:4px; color:var(--ink-soft); } .row .actions { grid-column:1/-1; } .compact { min-height:32px; padding:5px 9px; font-size:12px; } header { display:flex; justify-content:space-between; align-items:center; } header > span { color:var(--ink-soft); font-size:12px; } .inactive { background:#f2eeee; color:#899; }
@media(max-width:900px){.catalog-grid{grid-template-columns:1fr}}
.inactive { border-color:rgba(248,113,113,.25);background:rgba(248,113,113,.09);color:#cf9a92; }
.row:hover { background:var(--overlay-1); }
</style>
