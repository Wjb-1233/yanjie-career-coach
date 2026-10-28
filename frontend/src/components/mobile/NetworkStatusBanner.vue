<script setup lang="ts">
defineProps<{
  isOnline: boolean
}>()
</script>

<template>
  <Transition name="network-banner">
    <div v-if="!isOnline" class="network-status" role="status" aria-live="polite">
      <span class="network-dot" aria-hidden="true" />
      当前处于离线状态，已打开的页面仍可查看；训练提交需恢复网络。
    </div>
  </Transition>
</template>

<style scoped>
.network-status {
  position: fixed;
  z-index: 60;
  inset: 12px 50% auto auto;
  width: max-content;
  max-width: calc(100vw - 32px);
  padding: 10px 14px;
  transform: translateX(50%);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
  box-shadow: var(--shadow);
  backdrop-filter: none;
  color: var(--text-2);
  font-size: 13px;
  font-weight: 700;
  text-align: center;
}

.network-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 7px;
  border-radius: 50%;
  background: var(--warning);
}

.network-banner-enter-active, .network-banner-leave-active { transition: opacity .2s, transform .2s; }
.network-banner-enter-from, .network-banner-leave-to { opacity: 0; transform: translate(50%, -10px); }

@media (max-width: 760px) {
  .network-status { inset: 10px 16px auto; width: auto; transform: none; border-radius:var(--radius); }
  .network-banner-enter-from, .network-banner-leave-to { transform: translateY(-10px); }
}
</style>
