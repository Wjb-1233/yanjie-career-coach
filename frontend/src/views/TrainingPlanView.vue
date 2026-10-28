<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'

import PlanTaskCard from '@/components/plans/PlanTaskCard.vue'
import PlanComparison from '@/components/plans/PlanComparison.vue'
import { useTrainingPlan } from '@/composables/useTrainingPlan'

const route = useRoute()
const trainingPlan = useTrainingPlan(String(route.params.id))

onMounted(trainingPlan.load)

async function complete(taskKey: string, evidence?: string): Promise<void> {
  try {
    await trainingPlan.complete(taskKey, evidence)
  } catch {
    // 错误信息由 composable 统一展示。
  }
}
</script>

<template>
  <div class="page plan-page">
    <RouterLink class="back" to="/">← 返回成长看板</RouterLink>
    <div v-if="trainingPlan.error.value" class="error-banner">{{ trainingPlan.error.value }}</div>
    <div v-if="trainingPlan.loading.value" class="panel skeleton plan-loading" />
    <template v-else-if="trainingPlan.plan.value">
      <header class="plan-hero panel">
        <div>
          <p class="eyebrow">训练计划</p>
          <h1>{{ trainingPlan.plan.value.title }}</h1>
          <p v-if="trainingPlan.plan.value.tasks.some((task) => task.actionType === 'COURSE')">这是之前生成的课程型计划，完成后可查看五维评分变化。</p>
          <p v-else>根据五维评分锁定“{{ trainingPlan.plan.value.focusDimension }}”，先到基础能力场景专项对练，再回到原场景复测，用两次真实回答比较变化。</p>
        </div>
        <div class="task-count">
          <strong>{{ trainingPlan.plan.value.tasks.filter((task) => task.completed).length }} / {{ trainingPlan.plan.value.tasks.length }}</strong>
          <span>{{ trainingPlan.plan.value.status === 'COMPLETED' ? '已完成实战闭环' : '已完成训练任务' }}</span>
        </div>
      </header>
      <section class="task-list" aria-label="训练计划任务">
        <PlanTaskCard
          v-for="(task, index) in trainingPlan.plan.value.tasks"
          :key="task.key"
          :plan-id="trainingPlan.plan.value.id"
          :task="task"
          :submitting="trainingPlan.submitting.value"
          :locked="trainingPlan.plan.value.tasks.slice(0, index).some((previous) => !previous.completed)"
          :step-number="index + 1"
          @complete="complete"
        />
      </section>
      <PlanComparison
        v-if="trainingPlan.plan.value.comparison"
        :comparison="trainingPlan.plan.value.comparison"
        :focus-dimension="trainingPlan.plan.value.focusDimension"
      />
    </template>
  </div>
</template>

<style scoped>
.plan-page { max-width: 980px; }
.back { display: inline-block; margin-bottom: 18px; color: var(--ink-soft); font-size: 13px; }
.error-banner { margin-bottom: 18px; }
.plan-loading { min-height: 420px; }
.plan-hero { margin-bottom: 24px; padding: 32px; display: flex; align-items: center; justify-content: space-between; gap: 28px; border-color:var(--border);background:var(--card); }
.plan-hero h1 { margin: 0; font-size:clamp(30px, 5vw, 48px);font-weight:800;line-height:1.15;letter-spacing:-.035em; }
.plan-hero p:last-child { max-width: 600px; margin: 14px 0 0; color: var(--ink-soft); line-height: 1.8; }
.task-count { flex: none; display: grid; gap: 7px; padding: 18px; border-left: 1px solid var(--accent); border-radius:0 12px 12px 0;background:var(--bg-2); }
.task-count strong { font:600 32px/1 var(--font-ui);color:var(--text); }
.task-count span { color: var(--ink-soft); font-size: 12px; }
.task-list { display: grid; gap: 14px; }
@media (max-width: 650px) { .plan-hero { align-items: flex-start; flex-direction: column; } }
</style>
