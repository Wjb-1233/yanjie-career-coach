<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'

import FoundationPracticeGrid from '@/components/ability/FoundationPracticeGrid.vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

const foundationScenes = shallowRef<Scene[]>([])
const foundationError = shallowRef('')

onMounted(async () => {
  try {
    const response = await api.get<ApiEnvelope<Scene[]>>('/scenes', { params: { category: '基础能力提升', size: 100 } })
    foundationScenes.value = response.data.data
  } catch (reason) { foundationError.value = errorMessage(reason) }
})
</script>

<template>
  <div class="page practice-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">通用练习</p>
        <h1 class="page-title">挑一个维度，<br />单独练一轮。</h1>
        <p class="page-lead">五个维度各自独立，不需要先完成面试。练完想看得分，回到「能力提升」里复盘。</p>
      </div>
    </header>

    <FoundationPracticeGrid v-if="foundationScenes.length" :scenes="foundationScenes" />
    <p v-if="foundationError" class="error-banner" role="alert">五维通用练习暂时无法加载：{{ foundationError }}</p>
    <div v-if="!foundationScenes.length && !foundationError" class="loading">
      <div class="skeleton loading-card" />
      <div class="skeleton loading-card" />
      <div class="skeleton loading-card" />
    </div>
  </div>
</template>

<style scoped>
.practice-page { max-width: 1080px; }
.loading { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin-top: 10px; }
.loading-card { min-height: 220px; }
@media (max-width: 850px) { .loading { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 580px) { .loading { grid-template-columns: 1fr; } }
</style>
