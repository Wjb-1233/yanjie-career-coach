<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'

import AbilityAttempts from '@/components/ability/AbilityAttempts.vue'
import AbilityDrill from '@/components/ability/AbilityDrill.vue'
import AbilityReview from '@/components/ability/AbilityReview.vue'
import AbilityScores from '@/components/ability/AbilityScores.vue'
import FoundationPracticeGrid from '@/components/ability/FoundationPracticeGrid.vue'
import { useAbilityPractice } from '@/composables/useAbilityPractice'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

const { practice, dashboard, loading, sending, error, load, submit } = useAbilityPractice()
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
        <p class="page-lead">五个维度各自独立，不需要先完成面试。完成一场面试并生成报告后，下方还会出现针对你薄弱项的单题改答。</p>
      </div>
    </header>

    <FoundationPracticeGrid v-if="foundationScenes.length" :scenes="foundationScenes" />
    <p v-if="foundationError" class="error-banner" role="alert">五维通用练习暂时无法加载：{{ foundationError }}</p>

    <div v-if="error" class="error-banner" role="alert">{{ error }} <button v-if="!practice" type="button" @click="load">重试</button></div>
    <div v-if="loading" class="panel skeleton loading" />

    <section v-else-if="!practice" class="panel empty-state">
      <p class="eyebrow">个人薄弱项</p>
      <h2>完成一次面试后，这里会给出针对性改答</h2>
      <p>上方的五维通用练习可以直接开始。生成评分报告后，这里会结合整场对话给出薄弱项分析和单题改写练习。</p>
      <RouterLink class="button secondary" to="/scenes">选择训练场景 →</RouterLink>
    </section>

    <template v-else>
      <AbilityReview :practice="practice" :scores="dashboard?.dimensions ?? null" />
      <AbilityScores v-if="dashboard" :scores="dashboard.dimensions" :focus="practice.dimension" />
      <AbilityDrill :practice="practice" :sending="sending" @submit="submit" />
      <AbilityAttempts :attempts="practice.attempts" />
      <p class="method-note">上方分析依据最近一场完整对话与已保存报告；下方改答是单题巩固，分数与整场报告分使用不同评价范围，不直接相减。</p>
    </template>
  </div>
</template>

<style scoped>
.practice-page { max-width: 1080px; }
.loading { min-height: 320px; }
.empty-state { padding: 30px; margin-top: 34px; }
.empty-state h2 { margin: 0 0 12px; font-size: 22px; font-weight: 600; line-height: 1.4; }
.empty-state p:not(.eyebrow) { margin: 0 0 20px; color: var(--text-2); font-size: 13px; line-height: 1.9; }
.method-note { margin-top: 18px; color: var(--text-3); font-size: 12px; line-height: 1.7; }
.error-banner button { border: 0; background: transparent; text-decoration: underline; cursor: pointer; }
</style>
