<script setup lang="ts">
import { FileSearch, Upload } from 'lucide-vue-next'
import { onMounted, shallowRef } from 'vue'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

interface Suggestion { title: string; detail: string }
interface Diagnosis {
  id: string
  score: number
  coverage: number
  resumeChars?: number
  jdTerms?: number
  matched: string[]
  missing: string[]
  signals?: { digits: number; sections: string[] }
  suggestions: Suggestion[]
  summary: string
  filename?: string
  createdAt?: string
}
interface HistoryItem { id: string; score: number; coverage: number; filename: string; jdExcerpt: string; createdAt: string }

const jd = shallowRef('')
const resumeText = shallowRef('')
const file = shallowRef<File | null>(null)
const busy = shallowRef(false)
const error = shallowRef('')
const result = shallowRef<Diagnosis | null>(null)
const history = shallowRef<HistoryItem[]>([])

function pickFile(event: Event): void {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

async function submit(): Promise<void> {
  if (busy.value) return
  error.value = ''
  if (jd.value.trim().length < 20) {
    error.value = '岗位 JD 至少填 20 个字'
    return
  }
  if (!file.value && resumeText.value.trim().length < 100) {
    error.value = '请上传 .docx 简历，或粘贴至少 100 字的简历内容'
    return
  }
  busy.value = true
  try {
    const form = new FormData()
    form.append('jdText', jd.value.trim())
    if (resumeText.value.trim()) form.append('resumeText', resumeText.value.trim())
    if (file.value) form.append('file', file.value)
    const response = await api.post<ApiEnvelope<Diagnosis>>('/resume-diagnosis', form, { timeout: 60_000 })
    result.value = response.data.data
    await loadHistory()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = false
  }
}

async function loadHistory(): Promise<void> {
  try {
    const response = await api.get<ApiEnvelope<HistoryItem[]>>('/resume-diagnosis', { params: { limit: 10 } })
    history.value = response.data.data
  } catch {
    history.value = []
  }
}

async function openHistory(item: HistoryItem): Promise<void> {
  try {
    const response = await api.get<ApiEnvelope<Diagnosis>>(`/resume-diagnosis/${item.id}`)
    result.value = response.data.data
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

onMounted(() => { void loadHistory() })
</script>

<template>
  <div class="page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">简历诊断</p>
        <h1 class="page-title">简历先过一遍，<br /><span>再进面试场。</span></h1>
        <p class="page-lead">对照目标岗位 JD，检查关键词覆盖、结果数字和结构完整度，给出可执行的修改建议。</p>
      </div>
      <div class="method-card">
        <FileSearch :size="20" aria-hidden="true" />
        <p>不调用大模型：本地规则比对，几秒出结果，内容不会发给第三方。</p>
      </div>
    </header>

    <section class="diagnose-grid">
      <form class="form-panel panel" @submit.prevent="submit">
        <label class="field-block">
          <span>岗位 JD</span>
          <textarea v-model="jd" rows="7" class="field" placeholder="把目标岗位的职责与要求粘贴进来，至少 20 字" />
        </label>

        <label class="field-block">
          <span>简历文件（.docx，可选）</span>
          <span class="file-box">
            <Upload :size="16" aria-hidden="true" />
            <input type="file" accept=".docx" @change="pickFile" />
            <small>{{ file ? file.name : '未选择文件时，可直接粘贴下方简历文字' }}</small>
          </span>
        </label>

        <label class="field-block">
          <span>或粘贴简历文字</span>
          <textarea v-model="resumeText" rows="8" class="field" placeholder="粘贴简历正文，至少 100 字；上传了 .docx 时可以留空" />
        </label>

        <p v-if="error" class="form-error">{{ error }}</p>
        <button type="submit" class="button primary" :disabled="busy">{{ busy ? '诊断中…' : '开始诊断' }}</button>
      </form>

      <aside class="right-column">
        <section v-if="result" class="result panel" aria-live="polite">
          <div class="score-row">
            <div class="score"><strong>{{ result.score }}</strong><span>/ 100</span></div>
            <div class="score-meta">
              <p>{{ result.summary }}</p>
              <div class="meters">
                <span>关键词覆盖 {{ Math.round(result.coverage * 100) }}%</span>
                <span>数字 {{ result.signals?.digits ?? 0 }} 个</span>
                <span>板块 {{ result.signals?.sections?.length ?? 0 }} 个</span>
              </div>
            </div>
          </div>

          <div class="chips-block">
            <h3>已覆盖（{{ result.matched.length }}）</h3>
            <p class="chips"><span v-for="word in result.matched" :key="word" class="chip ok">{{ word }}</span><em v-if="!result.matched.length">暂无</em></p>
          </div>
          <div class="chips-block">
            <h3>缺失（{{ result.missing.length }}）</h3>
            <p class="chips"><span v-for="word in result.missing" :key="word" class="chip warn">{{ word }}</span><em v-if="!result.missing.length">全部覆盖</em></p>
          </div>

          <div class="suggestions">
            <h3>修改建议</h3>
            <ol>
              <li v-for="item in result.suggestions" :key="item.title">
                <strong>{{ item.title }}</strong>
                <p>{{ item.detail }}</p>
              </li>
            </ol>
          </div>
        </section>
        <section v-else class="result placeholder panel">
          <p>提交后会在这里显示分数、关键词覆盖和修改建议。</p>
        </section>

        <section v-if="history.length" class="history panel">
          <h3>历史诊断</h3>
          <ul>
            <li v-for="item in history" :key="item.id">
              <button type="button" @click="openHistory(item)">
                <strong>{{ item.score }}</strong>
                <span>{{ item.filename }}</span>
                <small>{{ new Date(item.createdAt).toLocaleString('zh-CN') }}</small>
              </button>
            </li>
          </ul>
        </section>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.page-heading { display: flex; justify-content: space-between; gap: 26px; align-items: end; margin-bottom: 24px; }
.page-title span { color: var(--accent-strong); }
.method-card { display: flex; gap: 10px; align-items: start; max-width: 300px; padding: 14px 16px; border: 1px solid var(--border); border-radius: var(--radius-sm, 14px); background: var(--surface); color: var(--text-3); font-size: 12px; }
.method-card p { margin: 0; line-height: 1.6; }
.diagnose-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); gap: 16px; align-items: start; }
.form-panel { display: grid; gap: 14px; padding: 18px; }
.field-block { display: grid; gap: 6px; font-size: 12.5px; color: var(--text-2); }
.field-block textarea { resize: vertical; }
.file-box { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border: 1px dashed var(--border); border-radius: 10px; color: var(--text-3); font-size: 12px; }
.file-box input { flex: 1; font-size: 12px; color: var(--text-2); }
.form-error { margin: 0; color: var(--danger); font-size: 12px; }
.right-column { display: grid; gap: 16px; }
.result { padding: 18px; }
.placeholder { color: var(--text-3); font-size: 13px; }
.score-row { display: flex; gap: 18px; align-items: center; }
.score { display: flex; align-items: baseline; gap: 4px; }
.score strong { font: 700 46px/1 var(--font-ui); color: var(--accent-strong); }
.score span { color: var(--text-3); font-size: 12px; }
.score-meta p { margin: 0 0 6px; color: var(--text-2); font-size: 12.5px; }
.meters { display: flex; flex-wrap: wrap; gap: 6px; color: var(--text-3); font-size: 11.5px; }
.meters span { padding: 3px 8px; border: 1px solid var(--border); border-radius: 999px; }
.chips-block { margin-top: 16px; }
.chips-block h3, .suggestions h3, .history h3 { margin: 0 0 8px; font-size: 12.5px; color: var(--text-2); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; }
.chip { padding: 3px 9px; border-radius: 999px; font-size: 11.5px; border: 1px solid var(--border); }
.chip.ok { color: var(--success); border-color: color-mix(in srgb, var(--success) 45%, transparent); }
.chip.warn { color: var(--accent-strong); border-color: var(--accent); }
.chips em { color: var(--text-3); font-size: 12px; }
.suggestions ol { margin: 0; padding-left: 18px; display: grid; gap: 10px; }
.suggestions li { font-size: 12.5px; color: var(--text); }
.suggestions p { margin: 3px 0 0; color: var(--text-2); line-height: 1.6; }
.history ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.history button { width: 100%; display: grid; grid-template-columns: 44px 1fr; gap: 2px 10px; text-align: left; border: 1px solid var(--border); background: transparent; border-radius: 10px; padding: 8px 10px; cursor: pointer; }
.history strong { grid-row: span 2; font-size: 20px; color: var(--accent-strong); }
.history span { font-size: 12px; color: var(--text-2); }
.history small { font-size: 11px; color: var(--text-3); }
@media (max-width: 900px) { .diagnose-grid { grid-template-columns: 1fr; } .page-heading { flex-direction: column; align-items: start; } }
</style>
