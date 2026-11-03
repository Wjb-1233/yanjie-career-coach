<script setup lang="ts">
import { computed, onMounted, onUnmounted, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Moon, Sun, Bookmark, BookOpen, History, LayoutDashboard, MessageSquareText, MessagesSquare, Repeat2, Settings, TrendingUp, UserRound } from 'lucide-vue-next'

import AtmosphereBackdrop from '@/components/layout/AtmosphereBackdrop.vue'
import { useAuth } from '@/composables/useAuth'
import { useTheme } from '@/composables/useTheme'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const studentNavItems = [
  { to: '/', label: '成长看板', icon: LayoutDashboard },
  { to: '/scenes', label: '场景训练', icon: MessagesSquare },
  { to: '/practice', label: '通用练习', icon: Repeat2 },
  { to: '/plans', label: '能力提升', icon: TrendingUp },
  { to: '/stories', label: '故事库', icon: BookOpen },
  { to: '/scripts', label: '话术优化', icon: MessageSquareText },
  { to: '/favorites', label: '个人收藏', icon: Bookmark },
  { to: '/history', label: '训练记录', icon: History },
  { to: '/profile', label: '个人资料', icon: UserRound },
]
const adminNavItems = [
  { to: '/admin', label: '管理工作台', icon: Settings },
  { to: '/profile', label: '个人资料', icon: UserRound },
]
const navItems = computed(() => auth.user.value?.role === 'ADMIN' ? adminNavItems : studentNavItems)

const home = computed(() => auth.user.value?.role === 'ADMIN' ? '/admin' : '/')
const { theme, toggle: toggleTheme, applyScope } = useTheme()
const sidebarCollapsed = shallowRef(false)
const mobileMenuOpen = shallowRef(false)
const mobileView = shallowRef(false)
const roleLabel = computed(() => auth.user.value?.role === 'ADMIN' ? '管理员' : '训练学员')

// 学员与管理员各自记住自己的主题偏好
watch(() => auth.user.value?.role ?? null, (role) => {
  if (role) applyScope(role as 'STUDENT' | 'ADMIN')
}, { immediate: true })

watch(() => auth.user.value?.role ?? null, (role) => {
  if (role) applyScope(role as 'STUDENT' | 'ADMIN')
}, { immediate: true })



function syncViewport(): void { mobileView.value = window.matchMedia('(max-width: 768px)').matches }
onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
})
onUnmounted(() => window.removeEventListener('resize', syncViewport))

function toggleNavigation(): void {
  if (mobileView.value) mobileMenuOpen.value = !mobileMenuOpen.value
  else sidebarCollapsed.value = !sidebarCollapsed.value
}

async function signOut() {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="shell" :class="{ collapsed: sidebarCollapsed }">
    <div class="app-bg" aria-hidden="true"><AtmosphereBackdrop variant="app" /></div>
    <header class="topbar">
      <div class="topbar-start">
        <button class="menu-toggle" type="button" aria-label="切换导航" :aria-expanded="mobileView ? mobileMenuOpen : !sidebarCollapsed" @click="toggleNavigation">
          <svg width="15" height="10" viewBox="0 0 15 10" fill="none" aria-hidden="true">
            <path d="M0 1h15M0 5h15M0 9h15" stroke="currentColor" stroke-width="1.1" />
          </svg>
        </button>
        <RouterLink class="topbar-brand" :to="home">
          <strong>言阶</strong>
          <span>面试沟通训练</span>
        </RouterLink>
      </div>
      <div class="topbar-account">
        <button class="theme-toggle" type="button" :aria-label="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'" @click="toggleTheme">
          <Sun v-if="theme === 'dark'" :size="15" :stroke-width="1.7" aria-hidden="true" />
          <Moon v-else :size="15" :stroke-width="1.7" aria-hidden="true" />
        </button>
        <span class="role">{{ roleLabel }}</span>
        <strong>{{ auth.user.value?.displayName }}</strong>
        <button type="button" @click="signOut">退出</button>
      </div>
    </header>

    <aside class="sidebar" :class="{ open: mobileMenuOpen }">
      <nav class="nav" :aria-label="auth.user.value?.role === 'ADMIN' ? '管理导航' : '学员导航'">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: route.path === item.to || (item.to !== '/' && route.path.startsWith(item.to)) }"
          @click="mobileMenuOpen = false"
        >
          <component :is="item.icon" :size="15" :stroke-width="1.6" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <div class="side-account">
          <img v-if="auth.user.value?.avatar" class="side-avatar-img" :src="auth.user.value.avatar" alt="">
          <span v-else class="side-avatar">{{ auth.user.value?.displayName?.slice(0, 1) }}</span>
          <span class="side-copy">
            <strong>{{ auth.user.value?.displayName }}</strong>
            <small>{{ roleLabel }}</small>
          </span>
        </div>
      </div>
    </aside>

    <main class="content"><slot /></main>
  </div>
</template>

<style scoped>
.app-bg { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
.app-scrim { position: fixed; inset: 0; z-index: 0; pointer-events: none; background: linear-gradient(180deg, rgba(8, 7, 18, .58) 0%, rgba(8, 7, 18, .72) 45%, rgba(9, 8, 20, .86) 100%); }

.shell { position: relative; position: relative;
  display: grid;
  grid-template-columns: 212px minmax(0, 1fr);
  grid-template-rows: 58px minmax(0, 1fr);
  min-height: 100vh;
  transition: grid-template-columns .22s var(--ease);
}
.shell.collapsed { grid-template-columns: 0 minmax(0, 1fr); }

/* ---------- 顶栏 ---------- */
.topbar {
  position: sticky;
  z-index: 30;
  top: 0;
  grid-column: 1 / -1;
  grid-row: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 34px;
  border-bottom: 1px solid var(--panel-line);
  background: linear-gradient(180deg, rgba(28, 22, 44, .72) 0%, rgba(14, 11, 24, .55) 100%);
  backdrop-filter: blur(20px) saturate(125%);
  -webkit-backdrop-filter: blur(20px) saturate(125%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .1);
}
.topbar-start { display: flex; align-items: center; gap: 18px; }
.menu-toggle {
  display: grid;
  width: 26px;
  height: 26px;
  padding: 0;
  place-items: center;
  border: 0;
  background: none;
  color: var(--text-3);
  cursor: pointer;
  transition: color var(--ease);
}
.menu-toggle:hover { color: var(--text); }
.topbar-brand { display: flex; align-items: baseline; gap: 12px; white-space: nowrap; }
.topbar-brand strong { font-size: 16px; font-weight: 600; letter-spacing: .18em; }
.topbar-brand span { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.topbar-account { display: flex; align-items: center; gap: 18px; color: var(--text-3); font-size: 12px; letter-spacing: .04em; }
.topbar-account .role { color: var(--text-3); }
.topbar-account strong { color: var(--text-2); font-size: 12px; font-weight: 400; }
.theme-toggle { display: grid; place-items: center; width: 30px; height: 30px; border: 1px solid var(--border); border-radius: 8px; background: transparent; color: var(--text-2); cursor: pointer; transition: border-color .16s var(--ease), color .16s var(--ease); }
.theme-toggle:hover { border-color: var(--border-bright); color: var(--text); }
.topbar-account button {
  padding: 0;
  border: 0;
  background: none;
  color: var(--text-3);
  cursor: pointer;
  font-size: 12px;
  letter-spacing: .04em;
  transition: color var(--ease);
}
.topbar-account button:hover { color: var(--text); }

/* ---------- 侧栏 ---------- */
.sidebar {
  grid-column: 1;
  grid-row: 2;
  position: sticky;
  top: 58px;
  align-self: start;
  height: calc(100vh - 58px);
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, .07);
  background: linear-gradient(180deg, rgba(255, 255, 255, .07) 0%, rgba(255, 255, 255, .015) 100%);
  box-shadow: inset 1px 0 0 rgba(255, 255, 255, .05);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow-y: auto;
  padding: 24px 0 22px;
  border-right: 1px solid var(--divider);
  background: var(--bg-2);
}
.nav { display: flex; flex-direction: column; gap: 1px; }
.nav-link {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 26px;
  color: var(--text-3);
  font-size: 13px;
  letter-spacing: .04em;
  white-space: nowrap;
  transition: color .16s var(--ease), transform .16s var(--ease);
}
.nav-group { margin: 18px 0 6px; padding: 0 22px; color: var(--text-3); font-size: 10px; letter-spacing: .18em; }
.nav-group:first-child { margin-top: 4px; }
.nav-link:hover { color: var(--text-2); transform: translateX(2px); }
.nav-link.active { color: var(--text); }
.nav-link.active::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  width: 2px;
  height: 14px;
  transform: translateY(-50%);
  background: var(--accent);
}
.sidebar-foot {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: auto;
  padding: 18px 26px 0;
  border-top: 1px solid var(--divider);
  white-space: nowrap;
}
.download-link { color: var(--text-3); font-size: 12px; letter-spacing: .04em; transition: color var(--ease); }
.download-link:hover { color: var(--text-2); }
.side-account { display: flex; align-items: center; gap: 10px; }
.side-avatar-img { width: 26px; height: 26px; border-radius: 50%; object-fit: cover; border: 1px solid var(--border); }
.side-avatar {
  display: grid;
  width: 26px;
  height: 26px;
  flex: none;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 50%;
  color: var(--text-2);
  font-size: 11px;
}
.side-copy strong { display: block; color: var(--text-2); font-size: 12px; font-weight: 400; }
.side-copy small { display: block; margin-top: 3px; color: var(--text-3); font-size: 11px; letter-spacing: .06em; }

.collapsed .nav-link { padding-inline: 0; opacity: 0; pointer-events: none; }
.collapsed .sidebar-foot { opacity: 0; pointer-events: none; }

.content { grid-column: 2; grid-row: 2; min-width: 0; background: transparent; position: relative; z-index: 1; }

@media (max-width: 768px) {
  .shell, .shell.collapsed { display: block; padding-top: 58px; }
  .topbar { position: fixed; inset: 0 0 auto; padding: 0 20px; }
  .topbar-brand span, .topbar-account .role, .topbar-account strong { display: none; }
  .sidebar {
    position: fixed;
    z-index: 25;
    inset: 58px auto 0 0;
    width: 212px;
    height: calc(100vh - 58px);
    padding: 18px 0;
    background: var(--bg-2);
    transform: translateX(-102%);
    transition: transform .22s var(--ease);
  }
  .sidebar.open { transform: translateX(0); box-shadow: 24px 0 48px rgba(0, 0, 0, .5); }
  .nav-link { padding: 11px 24px; }
  .content { min-height: calc(100vh - 58px); }
}

:root[data-theme='dark'] .topbar {
  background: rgba(10, 8, 22, .72);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-bottom-color: var(--border);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
:root[data-theme='dark'] .sidebar {
  background: rgba(10, 8, 22, .55);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-right-color: var(--border);
}
:root[data-theme='dark'] .nav-link:hover { color: var(--text-2); background: transparent; }
:root[data-theme='dark'] .nav-link.active { color: var(--text); background: transparent; box-shadow: none; }
</style>
