<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import PlanTaskCard from '@/components/plans/PlanTaskCard.vue'
import PlanComparison from '@/components/plans/PlanComparison.vue'
import { useTrainingPlan } from '@/composables/useTrainingPlan'

const route = useRoute()
const trainingPlan = useTrainingPlan(String(route.params.id))

const plan = computed(() => trainingPlan.plan.value)
const completedCount = computed(() => plan.value ? plan.value.tasks.filter((task) => task.completed).length : 0)
const totalCount = computed(() => plan.value?.tasks.length ?? 0)

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
    <RouterLink class="back" to="/plans">← 返回能力提升</RouterLink>

    <div v-if="trainingPlan.error.value" class="error-banner">{{ trainingPlan.error.value }}</div>
    <div v-if="trainingPlan.loading.value" class="skeleton plan-loading" />

    <template v-else-if="plan">
      <header class="plan-head">
        <p class="eyebrow">训练计划 · 针对{{ plan.focusDimension }}</p>
        <h1>{{ plan.title }}</h1>
        <p class="lead">先学微课，再回场景复练与改写，最后复测对比两次真实回答。</p>

        <div class="progress-row">
          <span class="num">{{ completedCount }} / {{ totalCount }}</span>
          <i class="bar"><b :style="{ width: `${plan.progress}%` }" /></i>
          <span class="status">{{ plan.status === 'COMPLETED' ? '已完成' : '进行中' }}</span>
        </div>
      </header>

      <section class="task-list" aria-label="训练计划任务">
        <PlanTaskCard
          v-for="(task, index) in plan.tasks"
          :key="task.key"
          :plan-id="plan.id"
          :task="task"
          :submitting="trainingPlan.submitting.value"
          :locked="plan.tasks.slice(0, index).some((previous) => !previous.completed)"
          :step-number="index + 1"
          @complete="complete"
        />
      </section>

      <PlanComparison
        v-if="plan.comparison"
        :comparison="plan.comparison"
        :focus-dimension="plan.focusDimension"
      />
    </template>
  </div>
</template>

<style scoped>
.plan-page { max-width: 900px; }
.back {
  display: inline-block;
  margin-bottom: 22px;
  color: var(--text-3);
  font-size: 12px;
  letter-spacing: .04em;
  transition: color var(--ease);
}
.back:hover { color: var(--text); }
.error-banner { margin-bottom: 18px; }
.plan-loading { min-height: 380px; }

.plan-head { padding-bottom: 22px; border-bottom: 1px solid var(--divider); }
.plan-head h1 {
  margin: 10px 0 0;
  color: var(--text);
  font-size: clamp(22px, 3vw, 28px);
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: -.01em;
}
.lead { max-width: 60ch; margin: 12px 0 0; color: var(--text-2); font-size: 13px; line-height: 1.9; }

.progress-row { display: flex; align-items: center; gap: 16px; margin-top: 22px; }
.progress-row .num { color: var(--text-2); font-family: var(--font-num); font-size: 13px; letter-spacing: .02em; }
.progress-row .bar { flex: 1; height: 2px; background: var(--track); }
.progress-row .bar b { display: block; height: 100%; background: var(--accent); }
.progress-row .status { color: var(--text-3); font-size: 11px; letter-spacing: .08em; }

.task-list { margin-top: 8px; }
</style>
