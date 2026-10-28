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
  <div class="page growth-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">能力提升</p>
        <h1 class="page-title">看清整场表现，<br /><span>再突破薄弱项。</span></h1>
        <p class="page-lead">可以先做五维通用场景对练；完成面试后，还能依据最近一次完整对话和评分证据，针对个人薄弱项深入练习。</p>
      </div>
    </header>
    <FoundationPracticeGrid v-if="foundationScenes.length" :scenes="foundationScenes" />
    <p v-if="foundationError" class="error-banner" role="alert">五维通用练习暂时无法加载：{{ foundationError }}</p>
    <div v-if="error" class="error-banner" role="alert">{{ error }} <button v-if="!practice" type="button" @click="load">重试</button></div>
    <div v-if="loading" class="panel skeleton loading" />
    <section v-else-if="!practice" class="panel empty-state">
      <p class="eyebrow">开始练习</p>
      <h2>完成面试后，解锁个人薄弱项分析</h2>
      <p>上方的五维通用练习可以直接开始。完成一场面试并生成报告后，这里会结合整场回答给出针对性分析。</p>
      <RouterLink class="button signal" to="/scenes">选择训练场景 →</RouterLink>
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
.growth-page{max-width:1160px}.page-title span{color:var(--text)}.loading{min-height:420px}.empty-state{padding:35px}.empty-state h2{margin:0 0 12px;font-weight:600;font-size:30px;line-height:1.2}.empty-state p:not(.eyebrow){color:var(--ink-soft)}.method-note{margin-top:18px;color:var(--ink-soft);font-size:12px;line-height:1.6}.error-banner button{border:0;background:transparent;text-decoration:underline;cursor:pointer}
</style>
