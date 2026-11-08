<script setup lang="ts">
import { Play } from 'lucide-vue-next'
import { computed, onMounted, shallowRef } from 'vue'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

interface Problem {
  id: string
  title: string
  difficulty: string
  tags: string[]
  description: string
  languages: string[]
  template: Record<string, string>
  sample: { args: unknown[]; expected: unknown }
}
interface CaseResult {
  index: number
  input: unknown[]
  expected: unknown
  actual: unknown
  passed: boolean
  error: string | null
}
interface RunResult {
  passed: number
  total: number
  allPassed: boolean
  durationMs: number
  results: CaseResult[]
  error: string | null
}
interface HistoryItem { id: string; problemId: string; language: string; passed: number; total: number; durationMs: number; createdAt: string }

const problems = shallowRef<Problem[]>([])
const activeId = shallowRef('')
const language = shallowRef<'python' | 'javascript'>('python')
const code = shallowRef('')
const running = shallowRef(false)
const result = shallowRef<RunResult | null>(null)
const history = shallowRef<HistoryItem[]>([])
const error = shallowRef('')
const loading = shallowRef(true)

const active = computed(() => problems.value.find((item) => item.id === activeId.value) ?? null)

function select(problem: Problem): void {
  activeId.value = problem.id
  language.value = (problem.languages[0] as 'python' | 'javascript') || 'python'
  code.value = problem.template[language.value] || ''
  result.value = null
}

function switchLanguage(next: 'python' | 'javascript'): void {
  language.value = next
  code.value = active.value?.template[next] || ''
  result.value = null
}

async function run(): Promise<void> {
  if (!active.value || running.value) return
  running.value = true
  error.value = ''
  try {
    const response = await api.post<ApiEnvelope<RunResult>>(
      `/coding/problems/${active.value.id}/run`,
      { language: language.value, code: code.value },
      { timeout: 30_000 },
    )
    result.value = response.data.data
    await loadHistory()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    running.value = false
  }
}

async function loadHistory(): Promise<void> {
  try {
    const response = await api.get<ApiEnvelope<HistoryItem[]>>('/coding/submissions', { params: { limit: 8 } })
    history.value = response.data.data
  } catch {
    history.value = []
  }
}

onMounted(async () => {
  try {
    const response = await api.get<ApiEnvelope<Problem[]>>('/coding/problems')
    problems.value = response.data.data
    if (problems.value.length) select(problems.value[0])
    await loadHistory()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">编程笔试</p>
        <h1 class="page-title">先写对，<br /><span>再说清楚。</span></h1>
        <p class="page-lead">三道算法题，支持 Python 与 JavaScript；本地判题会跑完整用例并记录每次提交。</p>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <section v-if="loading" class="coding-grid"><div class="problem-list panel skeleton" /><div class="editor panel skeleton" /></section>
    <section v-else class="coding-grid">
      <aside class="problem-list panel" aria-label="题目列表">
        <button
          v-for="problem in problems"
          :key="problem.id"
          type="button"
          class="problem-item"
          :class="{ active: problem.id === activeId }"
          @click="select(problem)"
        >
          <span class="title">{{ problem.title }}</span>
          <small>{{ problem.difficulty }} · {{ problem.tags.join(' / ') }}</small>
        </button>
      </aside>

      <div class="editor panel" v-if="active">
        <div class="problem-head">
          <h2>{{ active.title }}</h2>
          <span class="tag">{{ active.difficulty }}</span>
        </div>
        <p class="description">{{ active.description }}</p>
        <p class="sample">示例：输入 {{ JSON.stringify(active.sample.args) }} → 输出 {{ JSON.stringify(active.sample.expected) }}</p>

        <div class="editor-bar">
          <div class="langs" role="group" aria-label="语言">
            <button type="button" :class="{ active: language === 'python' }" @click="switchLanguage('python')">Python</button>
            <button type="button" :class="{ active: language === 'javascript' }" @click="switchLanguage('javascript')">JavaScript</button>
          </div>
          <button type="button" class="button primary" :disabled="running" @click="run">
            <Play :size="14" aria-hidden="true" />{{ running ? '判题中…' : '运行代码' }}
          </button>
        </div>
        <textarea v-model="code" class="code" spellcheck="false" aria-label="代码编辑器" />
        <p class="sandbox-note">本地沙箱运行，最多 6 秒；仅用于练习，请不要运行不可信代码。</p>

        <section v-if="result" class="run-result" aria-live="polite">
          <div class="run-head">
            <strong :class="{ ok: result.allPassed }">{{ result.allPassed ? '全部通过' : '部分未通过' }}</strong>
            <span>{{ result.passed }} / {{ result.total }} · {{ result.durationMs }} ms</span>
          </div>
          <p v-if="result.error" class="run-error">{{ result.error }}</p>
          <ol class="cases">
            <li v-for="item in result.results" :key="item.index" :class="{ pass: item.passed }">
              <span class="case-no">用例 {{ item.index }}</span>
              <span class="case-status">{{ item.passed ? '通过' : '未通过' }}</span>
              <p v-if="!item.passed" class="case-detail">输入 {{ JSON.stringify(item.input) }} · 期望 {{ JSON.stringify(item.expected) }} · 实际 {{ JSON.stringify(item.actual) }}</p>
              <p v-if="item.error && !item.passed" class="case-detail">{{ item.error }}</p>
            </li>
          </ol>
        </section>

        <section v-if="history.length" class="history">
          <h3>最近提交</h3>
          <ul>
            <li v-for="item in history" :key="item.id">
              <span>{{ item.problemId }}</span>
              <small>{{ item.language }} · {{ item.passed }}/{{ item.total }}</small>
              <small>{{ new Date(item.createdAt).toLocaleString('zh-CN') }}</small>
            </li>
          </ul>
        </section>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page-heading { margin-bottom: 22px; }
.page-title span { color: var(--accent-strong); }
.coding-grid { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 16px; align-items: start; }
.problem-list { padding: 10px; display: grid; gap: 6px; }
.problem-item { text-align: left; border: 1px solid transparent; background: transparent; border-radius: 10px; padding: 10px; cursor: pointer; display: grid; gap: 3px; color: var(--text); }
.problem-item.active { border-color: var(--accent); background: var(--accent-soft); }
.problem-item .title { font-size: 13.5px; font-weight: 600; }
.problem-item small { color: var(--text-3); font-size: 11.5px; }
.editor { padding: 16px; display: grid; gap: 12px; }
.problem-head { display: flex; align-items: center; gap: 8px; }
.problem-head h2 { margin: 0; font-size: 18px; }
.description { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.7; }
.sample { margin: 0; color: var(--text-3); font-size: 12px; }
.editor-bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.langs { display: flex; gap: 6px; }
.langs button { border: 1px solid var(--border); background: transparent; color: var(--text-2); border-radius: 999px; padding: 5px 12px; font-size: 12px; cursor: pointer; }
.langs button.active { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.code { width: 100%; min-height: 280px; resize: vertical; border: 1px solid var(--border); border-radius: 12px; background: #11161d; color: #e6edf3; font: 13px/1.65 ui-monospace, SFMono-Regular, Consolas, monospace; padding: 14px; tab-size: 2; }
.sandbox-note { margin: 0; color: var(--text-3); font-size: 11.5px; }
.run-result { border-top: 1px solid var(--border); padding-top: 12px; display: grid; gap: 8px; }
.run-head { display: flex; align-items: baseline; gap: 10px; }
.run-head strong { color: var(--accent-strong); font-size: 14px; }
.run-head strong.ok { color: var(--success); }
.run-head span { color: var(--text-3); font-size: 12px; }
.run-error { margin: 0; color: var(--danger); font-size: 12px; }
.cases { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.cases li { display: flex; gap: 10px; align-items: baseline; border: 1px solid var(--border); border-radius: 8px; padding: 6px 10px; font-size: 12px; color: var(--danger); flex-wrap: wrap; }
.cases li.pass { color: var(--success); }
.case-no { color: var(--text-2); }
.case-detail { margin: 0; color: var(--text-3); flex-basis: 100%; }
.history { border-top: 1px solid var(--border); padding-top: 10px; }
.history h3 { margin: 0 0 6px; font-size: 12.5px; color: var(--text-2); }
.history ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.history li { display: flex; gap: 10px; font-size: 12px; color: var(--text-2); }
.history small { color: var(--text-3); margin-left: auto; }
.skeleton { min-height: 240px; }
@media (max-width: 860px) { .coding-grid { grid-template-columns: 1fr; } }
</style>
