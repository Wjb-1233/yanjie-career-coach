<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppShell from '@/components/layout/AppShell.vue'
import MobileInstallBanner from '@/components/mobile/MobileInstallBanner.vue'
import NetworkStatusBanner from '@/components/mobile/NetworkStatusBanner.vue'
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { usePwaInstall } from '@/composables/usePwaInstall'

const route = useRoute()
const usesShell = computed(() => route.meta.public !== true)
const { isOnline } = useNetworkStatus()
const { isIos, shouldShowInstall, install, dismiss } = usePwaInstall()
</script>

<template>
  <NetworkStatusBanner :is-online="isOnline" />
  <AppShell v-if="usesShell">
    <RouterView />
  </AppShell>
  <RouterView v-else />
  <MobileInstallBanner
    :has-bottom-navigation="usesShell"
    :is-ios="isIos"
    :visible="shouldShowInstall && usesShell"
    @dismiss="dismiss"
    @install="install"
  />
</template>

