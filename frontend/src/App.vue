<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppShell from '@/components/layout/AppShell.vue'
import NetworkStatusBanner from '@/components/mobile/NetworkStatusBanner.vue'
import { useNetworkStatus } from '@/composables/useNetworkStatus'

const route = useRoute()
const usesShell = computed(() => route.meta.public !== true)
const { isOnline } = useNetworkStatus()
</script>

<template>
  <NetworkStatusBanner :is-online="isOnline" />
  <AppShell v-if="usesShell">
    <RouterView />
  </AppShell>
  <RouterView v-else />
</template>

