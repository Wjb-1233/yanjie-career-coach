<script setup lang="ts">
import { computed } from 'vue'
interface LearnerReportData {
  learner: { id: string; name: string; email: string; active: boolean; bio?: string; avatar?: string | null; createdAt?: string | null }
  trainingCount: number
  evaluationCount: number
  averageScore: number
  dimensions: Record<string, number>
  weakestDimension: string | null
  styleTags: string[]
  trends: Array<{ date: string; score: number }>
}

const props = defineProps<{ report: LearnerReportData }>()
const emit = defineEmits<{ close: []; export: [] }>()

const LABELS: Record<string, string> = {
  logic: '逻辑性',
  appropriateness: '得体性',
  correctness: '正确性',
  relevance: '针对性',
  concision: '简洁度',
}

const topTags = computed(() => {
  const counts = new Map<string, number>()
  for (const tag of props.report.styleTags) counts.set(tag, (counts.get(tag) ?? 0) + 1)
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([name]) => name)
})

function joinedAt(): string {
  const value = props.report.learner.createdAt
  return value ? new Date(value).toLocaleDateString('zh-CN') : '—'
}
</script>

<template>
  <div class="backdrop" role="presentation" @click.self="emit('close')">
    <section class="report" role="dialog" aria-modal="true" aria-label="学员能力报告">
      <header class="report-head">
        <div class="who">
          <span class="avatar">
            <img v-if="report.learner.avatar" :src="report.learner.avatar" alt="">
            <template v-else>{{ report.learner.name.slice(0, 1) }}</template>
          </span>
          <div class="who-copy">
            <p class="eyebrow">学员能力报告</p>
            <h2>{{ report.learner.name }}</h2>
            <p class="meta">{{ report.learner.email }} · {{ report.learner.active ? '账号启用' : '账号停用' }}<template v-if="report.learner.createdAt"> · 注册于 {{ joinedAt() }}</template></p>
          </div>
        </div>
        <button class="button secondary" type="button" @click="emit('close')">关闭</button>
      </header>

      <section v-if="report.learner.bio" class="profile-block">
        <h3>基本资料</h3>
        <p class="bio">{{ report.learner.bio }}</p>
      </section>
      <p v-else class="note no-bio">这位学员还没有填写个人介绍。</p>

      <div class="metrics">
        <div><b>{{ report.trainingCount }}</b><span>训练次数</span></div>
        <div><b>{{ report.evaluationCount }}</b><span>有效评分</span></div>
        <div><b>{{ report.averageScore }}</b><span>平均综合分</span></div>
      </div>

      <h3>五维能力平均分</h3>
      <div class="dimensions">
        <div v-for="(score, key, index) in report.dimensions" :key="key">
          <span>{{ LABELS[key] ?? key }}</span>
          <i class="bar"><b :style="{ '--w': `${(score / 5) * 100}%`, animationDelay: `${index * 85}ms` }" /></i>
          <b class="num">{{ score }}/5</b>
        </div>
      </div>

      <p class="note">主要提升点：<strong>{{ report.weakestDimension ? (LABELS[report.weakestDimension] ?? report.weakestDimension) : '暂无评分数据' }}</strong></p>
      <p class="note tags-line">表达风格：<span v-for="tag in topTags" :key="tag" class="tag">{{ tag }}</span><span v-if="!topTags.length">暂无</span></p>

      <h3>近期评分</h3>
      <ol class="trend"><li v-for="point in report.trends.slice(-8)" :key="`${point.date}-${point.score}`">{{ point.date }}：{{ point.score }} 分</li></ol>

      <footer class="report-foot">
        <button class="button" type="button" @click="emit('export')">导出该学员报告</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.backdrop { position: fixed; z-index: 50; inset: 0; padding: 20px; display: grid; place-items: center; background: rgba(6, 4, 14, .62); backdrop-filter: blur(6px); }
.report {
  width: min(720px, 100%);
  max-height: 90vh;
  overflow: auto;
  padding: 26px 28px 22px;
  border: 1px solid rgba(255, 255, 255, .12);
  border-radius: 18px;
  background: linear-gradient(165deg, rgba(255, 255, 255, .07) 0%, rgba(255, 255, 255, .02) 100%), rgba(16, 13, 28, .96);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .12), 0 40px 80px -40px rgba(0, 0, 0, .95);
}

.report-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.who { display: flex; gap: 14px; align-items: center; }
.avatar {
  display: grid; place-items: center;
  width: 52px; height: 52px; border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--card-2);
  color: var(--text); font-size: 19px;
  overflow: hidden;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.who-copy h2 { margin: 2px 0 0; color: var(--text); font-size: 21px; font-weight: 500; }
.meta { margin: 4px 0 0; color: var(--text-3); font-size: 12px; }

.profile-block { margin-top: 18px; padding: 10px 16px 12px; border: 1px solid var(--border); border-radius: 12px; background: rgba(255, 255, 255, .03); }
.profile-block h3 { margin: 0 0 8px; font-size: 11.5px; font-weight: 400; color: var(--text-3); letter-spacing: .1em; }
.bio { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.9; }
.no-bio { margin-top: 16px; color: var(--text-3); }

.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 18px; }
.metrics div { padding: 14px 16px; border: 1px solid var(--border); border-radius: 12px; background: rgba(255, 255, 255, .035); }
.metrics b { display: block; color: var(--text); font-family: var(--font-num); font-size: 24px; font-weight: 300; }
.metrics span { color: var(--text-3); font-size: 11px; }

h3 { margin: 22px 0 10px; color: var(--text-3); font-size: 11.5px; font-weight: 400; letter-spacing: .1em; }
.dimensions { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 22px; }
.dimensions div { display: grid; grid-template-columns: 56px minmax(0, 1fr) 44px; align-items: center; gap: 10px; color: var(--text-2); font-size: 12.5px; }
.bar { position: relative; display: block; height: 4px; border-radius: 999px; background: rgba(255, 255, 255, .08); }
.bar b { position: absolute; inset: 0 auto 0 0; border-radius: 999px; background: var(--accent); }
.num { color: var(--text); font-family: var(--font-num); font-size: 12px; text-align: right; }

.note { margin: 12px 0 0; color: var(--text-3); font-size: 12.5px; }
.note strong { color: var(--text); font-weight: 500; }
.tags-line { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.tag { padding: 2px 8px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-2); font-size: 11px; }
.trend { display: flex; flex-wrap: wrap; gap: 8px 24px; margin: 0; padding-left: 18px; color: var(--text-3); font-size: 12.5px; }
.report-foot { display: flex; justify-content: flex-end; margin-top: 22px; }

@media (max-width: 620px) {
  .dimensions { grid-template-columns: 1fr; }
  .metrics { grid-template-columns: 1fr; }
}

/* 进度条：入场时从 0 长到目标值 */
.bar b {
  width: 0;
  animation: bar-grow .62s cubic-bezier(.22, .8, .28, 1) both;
}
@keyframes bar-grow {
  from { width: 0; }
  to { width: var(--w); }
}
@media (prefers-reduced-motion: reduce) {
  .bar b { animation: none; width: var(--w); }
}
</style>
