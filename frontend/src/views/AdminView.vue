<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'

import AdminCoursesPanel from '@/components/admin/AdminCoursesPanel.vue'
import AdminMetricsPanel from '@/components/admin/AdminMetricsPanel.vue'
import AdminTasksPanel from '@/components/admin/AdminTasksPanel.vue'
import AdminScenesPanel from '@/components/admin/AdminScenesPanel.vue'
import AdminSessionsPanel from '@/components/admin/AdminSessionsPanel.vue'
import AdminUsersPanel from '@/components/admin/AdminUsersPanel.vue'
import AdminQuestionBankPanel from '@/components/admin/AdminQuestionBankPanel.vue'
import LearnerReportPanel from '@/components/admin/LearnerReportPanel.vue'
import { api, errorMessage } from '@/lib/api'
import type { AdminCourseRecord, AdminLearnerRow, AdminSceneRecord, AdminUserRecord, ApiEnvelope } from '@/lib/types'

interface Overview { users: number; activeUsers: number; scenes: number; activeScenes: number; courses: number; activeCourses: number; sessions: number; averageScore: number }
interface LearnerReport { learner: { id: string; name: string; email: string; active: boolean; bio?: string; avatar?: string | null; createdAt?: string | null }; trainingCount: number; evaluationCount: number; averageScore: number; dimensions: Record<string, number>; weakestDimension: string | null; styleTags: string[]; trends: Array<{ date: string; score: number; dimensions: Record<string, number> }> }
type Tab = 'users' | 'scenes' | 'bank' | 'courses' | 'sessions' | 'coverage' | 'tasks' | 'metrics'
interface MistakeStat { name: string; count: number }
interface MistakeStats { total: number; resolvedRate: number; byDimension: MistakeStat[]; byScene: MistakeStat[] }
interface CoverageItem { sceneId: string; title: string; category: string; questions: number; sessions: number; coveredSessions: number }
interface Coverage { totalScenes: number; scenesWithBank: number; scenesWithoutBank: number; totalQuestions: number; neverTrained: number; items: CoverageItem[] }
interface RecordingUsage { count: number; totalBytes: number; totalMb: number; retentionDays: number }
interface TaskRow {
  id: string
  kind: string
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'
  progress: number
  stage: string | null
  error: string | null
  email: string
  createdAt: string
  updatedAt: string
}

const overview = shallowRef<Overview | null>(null)
const users = shallowRef<AdminUserRecord[]>([])
const scenes = shallowRef<AdminSceneRecord[]>([])
const courses = shallowRef<AdminCourseRecord[]>([])
const learners = shallowRef<AdminLearnerRow[]>([])
const coverage = shallowRef<Coverage | null>(null)
const recordings = shallowRef<RecordingUsage | null>(null)
const purging = shallowRef(false)
const tasks = shallowRef<TaskRow[]>([])
const metrics = shallowRef<Record<string, never> | null>(null)
const mistakeStats = shallowRef<MistakeStats | null>(null)
const tab = shallowRef<Tab>('users')
const report = shallowRef<LearnerReport | null>(null)
const busyId = shallowRef('')
const resetResult = shallowRef<{ name: string; password: string } | null>(null)
const passwordRequests = shallowRef<Array<{ id: string; userId: string; name: string; email: string; createdAt: string | null }>>([])
const loading = shallowRef(true)
const error = shallowRef('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [summary, userList, sceneList, courseList, learnerList, requestList, coverageResult, mistakeStatsResult, recordingsResult, tasksResult, metricsResult] = await Promise.all([
      api.get<ApiEnvelope<Overview>>('/admin/overview'),
      api.get<ApiEnvelope<AdminUserRecord[]>>('/admin/users?size=100'),
      api.get<ApiEnvelope<AdminSceneRecord[]>>('/admin/scenes'),
      api.get<ApiEnvelope<AdminCourseRecord[]>>('/admin/courses'),
      api.get<ApiEnvelope<AdminLearnerRow[]>>('/admin/learners'),
      // 旧版后端没有这个接口时不应拖垮整个管理页
      api.get<ApiEnvelope<typeof passwordRequests.value>>('/admin/password-requests').catch(() => null),
      api.get<ApiEnvelope<Coverage>>('/admin/question-coverage'),
      api.get<ApiEnvelope<MistakeStats>>('/admin/mistake-stats'),
      api.get<ApiEnvelope<RecordingUsage>>('/admin/recordings').catch(() => null),
      api.get<ApiEnvelope<TaskRow[]>>('/admin/tasks?limit=20').catch(() => null),
      api.get<ApiEnvelope<never>>('/admin/metrics').catch(() => null),
    ])
    overview.value = summary.data.data
    users.value = userList.data.data
    scenes.value = sceneList.data.data
    courses.value = courseList.data.data
    learners.value = learnerList.data.data
    passwordRequests.value = requestList ? requestList.data.data : []
    coverage.value = coverageResult.data.data
    mistakeStats.value = mistakeStatsResult.data.data
    recordings.value = recordingsResult ? recordingsResult.data.data : null
    tasks.value = tasksResult ? tasksResult.data.data : []
    metrics.value = metricsResult ? (metricsResult.data.data as never) : null
  } catch (reason) { error.value = errorMessage(reason) }
  finally { loading.value = false }
}

async function updateUser(user: AdminUserRecord, patch: { active?: boolean }) {
  busyId.value = user.id
  try { await api.patch(`/admin/users/${user.id}`, patch); await load() }
  catch (reason) { error.value = errorMessage(reason) }
  finally { busyId.value = '' }
}

async function purgeRecordings() {
  purging.value = true
  try {
    const result = await api.post<ApiEnvelope<{ removed: number; orphans: number; freedBytes: number }>>('/admin/recordings/purge')
    const freed = Math.round((result.data.data.freedBytes / 1024 / 1024) * 10) / 10
    error.value = ''
    alert(`已清理 ${result.data.data.removed + result.data.data.orphans} 个文件，释放 ${freed} MB`)
    await load()
  } catch (reason) { error.value = errorMessage(reason) }
  finally { purging.value = false }
}

async function copyPassword() {
  if (!resetResult.value) return
  try { await navigator.clipboard.writeText(resetResult.value.password) } catch { /* 忽略 */ }
}

async function resolveRequest(item: { id: string; name: string }) {
  busyId.value = item.id
  try {
    const response = await api.post<ApiEnvelope<{ temporaryPassword: string; name: string }>>(`/admin/password-requests/${item.id}/resolve`)
    resetResult.value = { name: response.data.data.name, password: response.data.data.temporaryPassword }
    await load()
  } catch (reason) { error.value = errorMessage(reason) }
  finally { busyId.value = '' }
}

async function dismissRequest(item: { id: string }) {
  busyId.value = item.id
  try { await api.post(`/admin/password-requests/${item.id}/dismiss`); await load() }
  catch (reason) { error.value = errorMessage(reason) }
  finally { busyId.value = '' }
}

async function resetPassword(user: AdminUserRecord) {
  if (!window.confirm(`确定重置 ${user.displayName} 的密码吗？他的登录状态会失效。`)) return
  busyId.value = user.id
  try {
    const response = await api.post<ApiEnvelope<{ temporaryPassword: string }>>(`/admin/users/${user.id}/reset-password`)
    resetResult.value = { name: user.displayName, password: response.data.data.temporaryPassword }
  } catch (reason) { error.value = errorMessage(reason) }
  finally { busyId.value = '' }
}

async function saveScene(value: Omit<AdminSceneRecord, 'id'>, id: string | null) {
  try { if (id) await api.patch(`/admin/scenes/${id}`, value); else await api.post('/admin/scenes', value); await load() }
  catch (reason) { error.value = errorMessage(reason) }
}

async function deactivateScene(id: string) {
  if (!window.confirm('停用后学员将无法开启该场景，历史训练记录会保留。继续吗？')) return
  try { await api.delete(`/admin/scenes/${id}`); await load() } catch (reason) { error.value = errorMessage(reason) }
}

async function saveCourse(value: Omit<AdminCourseRecord, 'id' | 'progress' | 'completed'>, id: string | null) {
  try { if (id) await api.patch(`/admin/courses/${id}`, value); else await api.post('/admin/courses', value); await load() }
  catch (reason) { error.value = errorMessage(reason) }
}

async function toggleCourse(item: AdminCourseRecord) {
  if (item.active && !window.confirm('停用后该微课不再推荐，学员历史进度会保留。继续吗？')) return
  busyId.value = item.id
  try {
    await api.patch(`/admin/courses/${item.id}`, {
      title: item.title,
      dimension: item.dimension,
      minutes: item.minutes,
      description: item.description,
      content: item.content,
      active: !item.active,
    })
    await load()
  } catch (reason) { error.value = errorMessage(reason) } finally { busyId.value = '' }
}

async function download(path: string, filename: string) {
  try {
    const response = await api.get<Blob>(path, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (reason) { error.value = errorMessage(reason) }
}

async function showLearnerReport(userId: string) {
  try { const response = await api.get<ApiEnvelope<LearnerReport>>(`/admin/learners/${userId}/report`); report.value = response.data.data }
  catch (reason) { error.value = errorMessage(reason) }
}

onMounted(load)
</script>

<template>
  <div class="page admin-page">
    <header class="page-heading"><div><p class="eyebrow">管理工作台</p><h1 class="page-title">场景设计与学员管理</h1><p class="page-lead">管理员设计并开放面试场景，管理学员账号，查看训练报告；学员在独立的学习空间完成模拟与能力练习。</p></div><button class="button secondary" :disabled="loading" @click="load">刷新数据</button></header>
    <section class="panel workflow"><span>01 设计场景</span><i aria-hidden="true">→</i><span>02 对学员开放</span><i aria-hidden="true">→</i><span>03 学员训练</span><i aria-hidden="true">→</i><span>04 查看报告并调整场景</span></section>
    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-if="overview" class="admin-metrics">
      <div class="panel"><strong>{{ overview.users }}</strong><span>学员账号（{{ overview.activeUsers }} 启用）</span></div>
      <div class="panel"><strong>{{ overview.scenes }}</strong><span>面试场景（{{ overview.activeScenes }} 开放）</span></div>
      <div class="panel"><strong>{{ overview.courses }}</strong><span>微课素材（{{ overview.activeCourses }} 开放）</span></div>
      <div class="panel"><strong>{{ overview.sessions }}</strong><span>训练会话</span></div>
      <div class="panel"><strong>{{ overview.averageScore }}</strong><span>平均综合评分</span></div>
      <div class="panel recording-metric">
        <strong>{{ recordings ? recordings.totalMb : '—' }}<small>MB</small></strong>
        <span>录制占用（{{ recordings ? recordings.count : 0 }} 个文件 · 保留 {{ recordings ? recordings.retentionDays : 30 }} 天）</span>
        <button type="button" class="link" :disabled="purging" @click="purgeRecordings">{{ purging ? '清理中…' : '立即清理过期录制' }}</button>
      </div>
    </div>
    <nav class="admin-tabs" aria-label="管理功能">
      <button v-for="item in [{ id: 'users', label: '学员与权限' }, { id: 'scenes', label: '场景设计' }, { id: 'bank', label: '题库管理' }, { id: 'courses', label: '微课素材' }, { id: 'sessions', label: '训练与报告' }, { id: 'coverage', label: '题库与错题' }, { id: 'tasks', label: '后台任务' }, { id: 'metrics', label: '运行指标' }]" :key="item.id" :class="{ active: tab === item.id }" @click="tab = item.id as Tab">{{ item.label }}</button>
    </nav>
    <div v-if="loading" class="panel loading" aria-label="正在加载管理数据"><div class="skeleton loading-line" /><div class="skeleton loading-line short" /><div class="skeleton loading-card" /></div>
    <AdminUsersPanel v-else-if="tab === 'users'" :users="users" :busy-id="busyId" :requests="passwordRequests" @update="updateUser" @reset="resetPassword" @resolve-request="resolveRequest" @dismiss-request="dismissRequest" />
    <AdminScenesPanel v-else-if="tab === 'scenes'" :scenes="scenes" :busy="loading" @save="saveScene" @deactivate="deactivateScene" />
    <AdminQuestionBankPanel v-else-if="tab === 'bank'" :scenes="scenes" :busy="loading" @save="saveScene" />
    <AdminCoursesPanel v-else-if="tab === 'courses'" :courses="courses" :busy="loading" @save="saveCourse" @toggle="toggleCourse" />
    <AdminMetricsPanel v-else-if="tab === 'metrics'" :metrics="metrics as never" />
    <AdminTasksPanel v-else-if="tab === 'tasks'" :tasks="tasks" :loading="loading" @refresh="load" />
    <AdminSessionsPanel v-else-if="tab === 'sessions'" :learners="learners" :loading="loading" @export="download('/admin/reports/export', '学员训练能力报告.csv')" @report="showLearnerReport" />
    <section v-else-if="tab === 'coverage'" class="panel coverage panel-pad">
      <template v-if="coverage">
        <dl class="coverage-stats">
          <div><dt>场景总数</dt><dd class="num">{{ coverage.totalScenes }}<small>个</small></dd></div>
          <div><dt>从未被训练</dt><dd class="num">{{ coverage.neverTrained }}<small>个</small></dd></div>
        </dl>
        <div class="coverage-list">
          <div v-for="item in coverage.items" :key="item.sceneId" class="coverage-row">
            <span class="coverage-title">{{ item.title }}</span>
            <span class="coverage-cat">{{ item.category }}</span>
            <span class="coverage-num num">{{ item.questions }} 题</span>
            <span class="coverage-num num">{{ item.sessions }} 次训练</span>
            <span class="coverage-bar"><b :style="{ width: `${item.questions ? Math.min(100, Math.round((item.coveredSessions / Math.max(item.sessions, 1)) * 100)) : 0}%` }" /></span>
          </div>
        </div>

        <template v-if="mistakeStats">
          <dl class="coverage-stats mistake-stats">
            <div><dt>错题总数</dt><dd class="num">{{ mistakeStats.total }}</dd></div>
            <div><dt>已解决比例</dt><dd class="num">{{ Math.round(mistakeStats.resolvedRate * 100) }}%</dd></div>
            <div><dt>涉及维度</dt><dd class="num">{{ mistakeStats.byDimension.filter((item) => item.count > 0).length }}</dd></div>
            <div><dt>涉及场景</dt><dd class="num">{{ mistakeStats.byScene.length }}</dd></div>
          </dl>
          <div class="stat-columns">
            <section>
              <h3>最常错的维度</h3>
              <div v-for="item in mistakeStats.byDimension" :key="item.name" class="stat-row">
                <span>{{ item.name }}</span>
                <i class="coverage-bar"><b :style="{ width: `${mistakeStats.total ? Math.round((item.count / mistakeStats.total) * 100) : 0}%` }" /></i>
                <span class="coverage-num num">{{ item.count }}</span>
              </div>
            </section>
            <section>
              <h3>错得最多的场景</h3>
              <div v-for="item in mistakeStats.byScene" :key="item.name" class="stat-row">
                <span class="scene-name">{{ item.name }}</span>
                <i class="coverage-bar"><b :style="{ width: `${mistakeStats.byScene[0]?.count ? Math.round((item.count / mistakeStats.byScene[0].count) * 100) : 0}%` }" /></i>
                <span class="coverage-num num">{{ item.count }}</span>
              </div>
              <p v-if="!mistakeStats.byScene.length" class="block-empty">还没有错题数据。</p>
            </section>
          </div>
        
    <div v-if="resetResult" class="reset-backdrop" role="presentation" @click.self="resetResult = null">
      <section class="reset-dialog" role="dialog" aria-modal="true" aria-label="临时密码">
        <h3>已重置 {{ resetResult.name }} 的密码</h3>
        <p>已重置为默认密码 <strong>123456789</strong>，请转告学员，登录后到个人资料页自行修改。</p>
        <div class="reset-password"><code>{{ resetResult.password }}</code><button class="button secondary compact" type="button" @click="copyPassword">复制</button></div>
        <div class="reset-actions"><button class="button" type="button" @click="resetResult = null">知道了</button></div>
      </section>
    </div>
</template>
      </template>
    </section>
    <LearnerReportPanel v-if="report" :report="report" @close="report = null" @export="download(`/admin/learners/${report.learner.id}/report/export`, `${report.learner.name}-能力报告.csv`)" />
  </div>
</template>

<style scoped>
.admin-page { max-width: 1100px; } .workflow { display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:20px;padding:16px 20px;color:var(--text-2);font-size:13px; } .workflow span { color:var(--primary-hover);font-weight:700; } .workflow i {font-style:normal;color:var(--text-3)}.admin-metrics { margin-bottom:20px; display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; } .admin-metrics div { min-height:96px; padding:16px; display:flex; flex-direction:column; justify-content:space-between; } .admin-metrics strong { font-size:30px;line-height:1;font-weight:750; } .admin-metrics span { color:var(--text-2); font-size:11px; } .admin-tabs { margin:0 0 16px; display:flex; gap:8px; overflow:auto; } .admin-tabs button { padding:10px 16px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--card); color:var(--text-2); white-space:nowrap; cursor:pointer;transition:all .2s ease; } .admin-tabs button:hover{color:var(--text-2)}.coverage.panel-pad { padding: 22px; }
.recording-metric strong small { margin-left: 4px; font-size: 12px; color: var(--text-3); }
.recording-metric .link { align-self: flex-start; padding: 0; border: 0; background: none; color: var(--primary-hover); font-size: 12px; cursor: pointer; }
.recording-metric .link:disabled { opacity: .6; cursor: default; }
@media (max-width: 900px) { .admin-metrics { grid-template-columns: repeat(2, 1fr); } }
.coverage-stats { display: flex; justify-content: space-between; gap: 18px; margin: 0 0 22px; }
.coverage-stats.mistake-stats { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); justify-content: initial; }
.coverage-stats dt { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.coverage-stats dd { margin: 8px 0 0; color: var(--text); font-family: var(--font-num); font-size: 26px; font-weight: 300; }
.coverage-stats dd small { margin-left: 4px; color: var(--text-3); font-size: 11px; font-weight: 400; }
.stat-columns { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: 32px; }
.stat-columns h3 { margin: 0 0 12px; color: var(--text-3); font-size: 11px; font-weight: 400; letter-spacing: .14em; }
.stat-row { display: grid; grid-template-columns: 96px minmax(0,1fr) 40px; align-items: center; gap: 12px; padding: 8px 0; color: var(--text-2); font-size: 12.5px; }
.scene-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.coverage-list { display: grid; gap: 0; }
.coverage-row { display: grid; grid-template-columns: minmax(0,1fr) 92px 64px 82px 90px; align-items: center; gap: 12px; padding: 10px 0; border-top: 1px solid var(--divider); font-size: 12.5px; color: var(--text-2); }
.coverage-cat { color: var(--text-3); font-size: 11px; }
.coverage-num { color: var(--text-3); font-size: 11.5px; text-align: right; }
.coverage-bar { height: 2px; background: var(--track); }
.coverage-bar b { display: block; height: 100%; background: var(--accent); }
.admin-tabs button.active { border-color:var(--border);background:var(--accent);color:#1a1207;box-shadow:none; } .loading { padding:28px; display:grid;gap:14px; } .loading-line{height:20px;width:60%}.loading-line.short{width:36%}.loading-card{height:150px;width:100%} @media(max-width:900px){.admin-metrics{grid-template-columns:repeat(2,1fr)}}

.admin-tabs button:hover { border-color:var(--border-bright);color:var(--text); }

.workflow span { color:var(--text); }
.admin-metrics .panel:nth-child(2) { animation-delay:.06s; }
.admin-metrics .panel:nth-child(3) { animation-delay:.12s; }
.admin-metrics .panel:nth-child(4) { animation-delay:.18s; }
.admin-metrics .panel:nth-child(5) { animation-delay:.24s; }

.reset-backdrop { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; padding: 20px; background: rgba(6, 4, 14, .55); backdrop-filter: blur(6px); }
.reset-dialog { width: min(460px, 100%); padding: 24px 26px; border: 1px solid var(--border); border-radius: 16px; background: var(--card); box-shadow: 0 30px 60px -30px rgba(0, 0, 0, .8); }
.reset-dialog h3 { margin: 0; font-size: 16px; }
.reset-dialog p { margin: 10px 0 0; color: var(--text-2); font-size: 12.5px; line-height: 1.8; }
.reset-password { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; padding: 12px 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--bg-2); }
.reset-password code { color: var(--text); font-family: ui-monospace, monospace; font-size: 15px; letter-spacing: .04em; }
.reset-actions { display: flex; justify-content: flex-end; margin-top: 18px; }
</style>
<style scoped>
.admin-page { max-width: 1180px; }
.page-title { font-size: clamp(28px, 3vw, 34px); letter-spacing: -.02em; }
.page-lead { margin-top: 8px; font-size: 13.5px; }
.workflow { padding: 12px 16px; font-size: 12.5px; margin-bottom: 18px; }
.workflow span { font-weight: 600; }
.admin-metrics { gap: 12px; margin-bottom: 22px; }
.admin-metrics div { min-height: 100px; padding: 18px; border-radius: 12px; }
.admin-metrics strong { font-size: 32px; font-weight: 650; }
.admin-metrics span { font-size: 12.5px; color: var(--text-3); }
.admin-tabs { gap: 6px; margin-bottom: 20px; }
.admin-tabs button { padding: 9px 15px; border-radius: 999px; font-size: 13px; }
.admin-tabs button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.admin-page :deep(table) { width: 100%; font-size: 13px; border-collapse: collapse; }
.admin-page :deep(th) { padding: 10px 8px; font-size: 12px; font-weight: 500; color: var(--text-3); text-align: left; border-bottom: 1px solid var(--divider); }
.admin-page :deep(td) { padding: 12px 8px; border-bottom: 1px solid var(--divider); color: var(--text-2); }
.admin-page :deep(tbody tr:hover) { background: var(--overlay-1); }
</style>
