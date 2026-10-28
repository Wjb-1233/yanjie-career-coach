<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import PersonalizedLesson from '@/components/courses/PersonalizedLesson.vue'
import { useCourseLearning } from '@/composables/useCourseLearning'

const route = useRoute()
const learning = useCourseLearning()
onMounted(() => learning.load(String(route.query.planId ?? '')))
</script>

<template>
  <div class="page">
    <RouterLink :to="route.query.planId ? `/plans/${route.query.planId}` : '/plans'">← 返回训练计划</RouterLink>
    <div v-if="learning.error.value" class="error-banner">{{ learning.error.value }}</div>
    <PersonalizedLesson v-if="learning.plan.value && learning.courseTask.value?.lesson" :plan="learning.plan.value" :task="learning.courseTask.value" :submitting="learning.submitting.value" @complete-step="learning.completeStep" @submit-practice="learning.submitPractice" />
    <div v-else-if="!learning.loading.value" class="panel legacy-empty">这份历史计划没有可继续学习的课程。</div>
  </div>
</template>

<style scoped>.legacy-empty { margin-top: 20px; padding: 28px; }</style>
