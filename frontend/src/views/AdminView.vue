<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'

import AdminCoursesPanel from '@/components/admin/AdminCoursesPanel.vue'
import AdminScenesPanel from '@/components/admin/AdminScenesPanel.vue'
import AdminSessionsPanel from '@/components/admin/AdminSessionsPanel.vue'
import AdminUsersPanel from '@/components/admin/AdminUsersPanel.vue'
import LearnerReportPanel from '@/components/admin/LearnerReportPanel.vue'
import { api, errorMessage } from '@/lib/api'
import type { AdminCourseRecord, AdminSceneRecord, AdminSessionRecord, AdminUserRecord, ApiEnvelope } from '@/lib/types'

interface Overview { users: number; activeUsers: number; scenes: number; activeScenes: number; courses: number; activeCourses: number; sessions: number; averageScore: number }
interface LearnerReport { learner: { id: string; name: string; email: string; active: boolean }; trainingCount: number; evaluationCount: number; averageScore: number; dimensions: Record<string, number>; weakestDimension: string | null; styleTags: string[]; trends: Array<{ date: string; score: number; dimensions: Record<string, number> }> }
type Tab = 'users' | 'scenes' | 'courses' | 'sessions'

const overview = shallowRef<Overview | null>(null)
const users = shallowRef<AdminUserRecord[]>([])
const scenes = shallowRef<AdminSceneRecord[]>([])
const courses = shallowRef<AdminCourseRecord[]>([])
const sessions = shallowRef<AdminSessionRecord[]>([])
const tab = shallowRef<Tab>('users')
const report = shallowRef<LearnerReport | null>(null)
const busyId = shallowRef('')
const loading = shallowRef(true)
const error = shallowRef('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [summary, userList, sceneList, courseList, sessionList] = await Promise.all([
      api.get<ApiEnvelope<Overview>>('/admin/overview'),
      api.get<ApiEnvelope<AdminUserRecord[]>>('/admin/users?size=100'),
      api.get<ApiEnvelope<AdminSceneRecord[]>>('/admin/scenes'),
      api.get<ApiEnvelope<AdminCourseRecord[]>>('/admin/courses'),
      api.get<ApiEnvelope<AdminSessionRecord[]>>('/admin/sessions?size=100'),
    ])
    overview.value = summary.data.data
    users.value = userList.data.data
    scenes.value = sceneList.data.data
    courses.value = courseList.data.data
    sessions.value = sessionList.data.data
  } catch (reason) { error.value = errorMessage(reason) }
  finally { loading.value = false }
}

async function updateUser(user: AdminUserRecord, patch: { role?: 'STUDENT' | 'ADMIN'; active?: boolean }) {
  busyId.value = user.id
  try { await api.patch(`/admin/users/${user.id}`, patch); await load() }
  catch (reason) { error.value = errorMessage(reason) }
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

async function deactivateCourse(id: string) {
  if (!window.confirm('停用后该微课不再推荐，学员历史进度会保留。继续吗？')) return
  try { await api.delete(`/admin/courses/${id}`); await load() } catch (reason) { error.value = errorMessage(reason) }
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
      <div class="panel"><strong>{{ overview.courses }}</strong><span>微课（{{ overview.activeCourses }} 开放）</span></div>
      <div class="panel"><strong>{{ overview.sessions }}</strong><span>训练会话</span></div>
      <div class="panel"><strong>{{ overview.averageScore }}</strong><span>平均综合评分</span></div>
    </div>
    <nav class="admin-tabs" aria-label="管理功能">
      <button v-for="item in [{ id: 'users', label: '学员与权限' }, { id: 'scenes', label: '场景设计' }, { id: 'courses', label: '微课管理' }, { id: 'sessions', label: '训练与报告' }]" :key="item.id" :class="{ active: tab === item.id }" @click="tab = item.id as Tab">{{ item.label }}</button>
    </nav>
    <div v-if="loading" class="panel loading" aria-label="正在加载管理数据"><div class="skeleton loading-line" /><div class="skeleton loading-line short" /><div class="skeleton loading-card" /></div>
    <AdminUsersPanel v-else-if="tab === 'users'" :users="users" :busy-id="busyId" @update="updateUser" />
    <AdminScenesPanel v-else-if="tab === 'scenes'" :scenes="scenes" :busy="loading" @save="saveScene" @deactivate="deactivateScene" />
    <AdminCoursesPanel v-else-if="tab === 'courses'" :courses="courses" :busy="loading" @save="saveCourse" @deactivate="deactivateCourse" />
    <AdminSessionsPanel v-else :sessions="sessions" :loading="loading" @export="download('/admin/reports/export', '学员训练能力报告.csv')" @report="showLearnerReport" />
    <LearnerReportPanel v-if="report" :report="report" @close="report = null" @export="download(`/admin/learners/${report.learner.id}/report/export`, `${report.learner.name}-能力报告.csv`)" />
  </div>
</template>

<style scoped>
.admin-page { max-width: 1100px; } .workflow { display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:20px;padding:16px 20px;color:var(--text-2);font-size:13px; } .workflow span { color:var(--primary-hover);font-weight:700; } .workflow i {font-style:normal;color:var(--text-3)}.admin-metrics { margin-bottom:20px; display:grid; grid-template-columns:repeat(5,1fr); gap:10px; } .admin-metrics div { min-height:96px; padding:16px; display:flex; flex-direction:column; justify-content:space-between; } .admin-metrics strong { font-size:30px;line-height:1;font-weight:750; } .admin-metrics span { color:var(--text-2); font-size:11px; } .admin-tabs { margin:0 0 16px; display:flex; gap:8px; overflow:auto; } .admin-tabs button { padding:10px 16px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--card); color:var(--text-2); white-space:nowrap; cursor:pointer;transition:all .2s ease; } .admin-tabs button:hover{border-color:var(--primary);color:var(--primary)}.admin-tabs button.active { border-color:var(--primary); background:var(--primary); color:#fff; } .loading { padding:28px; display:grid;gap:14px; } .loading-line{height:20px;width:60%}.loading-line.short{width:36%}.loading-card{height:150px;width:100%} @media(max-width:900px){.admin-metrics{grid-template-columns:repeat(2,1fr)}}
.admin-tabs button { border-color:var(--border);background:var(--overlay-2);color:var(--text-2); }
.admin-tabs button:hover { border-color:var(--border-bright);color:var(--text); }
.admin-tabs button.active { border-color:var(--border);background:var(--accent);box-shadow:none; }
.workflow span { color:var(--text); }
.admin-metrics .panel:nth-child(2) { animation-delay:.06s; }
.admin-metrics .panel:nth-child(3) { animation-delay:.12s; }
.admin-metrics .panel:nth-child(4) { animation-delay:.18s; }
.admin-metrics .panel:nth-child(5) { animation-delay:.24s; }
</style>
