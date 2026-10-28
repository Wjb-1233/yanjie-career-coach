<script setup lang="ts">
defineProps<{
  hasBottomNavigation: boolean
  isIos: boolean
  visible: boolean
}>()

defineEmits<{
  dismiss: []
  install: []
}>()
</script>

<template>
  <Transition name="install-card">
    <aside
      v-if="visible"
      class="install-banner"
      :class="{ 'with-bottom-navigation': hasBottomNavigation }"
      aria-label="安装移动端应用"
    >
      <div class="app-icon" aria-hidden="true">
        <span class="app-icon-bars"><i /><i /><i /></span>
      </div>
      <div class="install-copy">
        <strong>把“言阶”装到手机</strong>
        <span v-if="isIos">点击 Safari 分享按钮，再选择“添加到主屏幕”。</span>
        <span v-else>桌面图标直达，全屏训练，使用起来更像原生 App。</span>
      </div>
      <button v-if="!isIos" class="install-action" type="button" @click="$emit('install')">安装</button>
      <button class="dismiss-action" type="button" aria-label="暂时关闭安装提示" @click="$emit('dismiss')">×</button>
    </aside>
  </Transition>
</template>

<style scoped>
.install-banner {
  position: fixed;
  z-index: 50;
  right: 24px;
  bottom: 24px;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  width: min(520px, calc(100vw - 48px));
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
  box-shadow: var(--shadow);
  color: var(--text);
  backdrop-filter: none;
}

.app-icon {
  position: relative;
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius:var(--radius-sm);
  background: var(--bg-2);
  overflow: hidden;
}

.app-icon::after {
  position: absolute;
  right: 7px;
  top: 7px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted-progress);
  content: '';
}

.app-icon-bars { display: flex; align-items: flex-end; gap: 3px; height: 22px; }
.app-icon-bars i { display: block; width: 4px; border-radius: 99px; background: var(--text-2); }
.app-icon-bars i:nth-child(1) { height: 9px; }
.app-icon-bars i:nth-child(2) { height: 15px; }
.app-icon-bars i:nth-child(3) { height: 22px; }
.install-copy { min-width: 0; }
.install-copy strong, .install-copy span { display: block; }
.install-copy strong { margin-bottom: 4px; font-size: 14px; }
.install-copy span { color: var(--text-2); font-size: 12px; line-height: 1.55; }
.install-action {
  min-height: 38px;
  padding: 0 16px;
  border: 0;
  border-radius:var(--radius-sm);
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}
.dismiss-action {
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  font-size: 23px;
  line-height: 1;
}
.install-card-enter-active, .install-card-leave-active { transition: opacity .22s, transform .22s; }
.install-card-enter-from, .install-card-leave-to { opacity: 0; transform: translateY(12px); }

@media (max-width: 760px) {
  .install-banner {
    right: 14px;
    bottom: 14px;
    grid-template-columns: 44px minmax(0, 1fr) auto;
    width: calc(100vw - 28px);
    padding: 12px;
    border-radius:var(--radius);
  }
  .install-banner.with-bottom-navigation { bottom: calc(88px + env(safe-area-inset-bottom)); }
  .app-icon { width: 44px; height: 44px; border-radius:var(--radius) 14px 5px 14px; }
  .install-action { grid-column: 2; width: fit-content; min-height: 34px; margin-top: 2px; }
  .dismiss-action { grid-column: 3; grid-row: 1; align-self: start; }
}
</style>
