<script setup lang="ts">
interface Metrics {
  evaluations: {
    total: number
    degraded: number
    degradedRatio: number
    avgDurationMs: number | null
    avgScore: number | null
    scoreBuckets: Record<string, number>
  }
  tasks: { total: number; byStatus: Record<string, number>; failedRatio: number }
  daily: Array<{ date: string; count: number }>
}

defineProps<{ metrics: Metrics | null }>()

const BUCKETS = ['1-2', '3', '4', '5']

function seconds(ms: number | null): string {
  if (!ms) return '—'
  return `${(ms / 1000).toFixed(1)}s`
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}
</script>

<template>
  <section class="panel metrics-panel">
    <header class="metrics-head">
      <h2>运行指标</h2>
      <p>评分质量与后台任务的实时统计，用来判断系统是否健康。</p>
    </header>

    <p v-if="!metrics" class="empty">还没有统计数据</p>
    <template v-else>
      <div class="cards">
        <div class="card">
          <strong>{{ metrics.evaluations.total }}</strong>
          <span>评分总数</span>
        </div>
        <div class="card">
          <strong>{{ seconds(metrics.evaluations.avgDurationMs) }}</strong>
          <span>平均评分耗时</span>
        </div>
        <div class="card" :class="{ warn: metrics.evaluations.degradedRatio > 0.3 }">
          <strong>{{ percent(metrics.evaluations.degradedRatio) }}</strong>
          <span>规则兜底占比</span>
        </div>
        <div class="card">
          <strong>{{ metrics.evaluations.avgScore ?? '—' }}</strong>
          <span>平均综合分</span>
        </div>
        <div class="card" :class="{ warn: metrics.tasks.failedRatio > 0.2 }">
          <strong>{{ percent(metrics.tasks.failedRatio) }}</strong>
          <span>任务失败率（{{ metrics.tasks.total }} 个）</span>
        </div>
      </div>

      <div class="split">
        <div>
          <h3>分数分布</h3>
          <ul class="bars">
            <li v-for="key in BUCKETS" :key="key">
              <span class="label">{{ key }} 分</span>
              <i><b :style="{ width: `${metrics.evaluations.total ? ((metrics.evaluations.scoreBuckets[key] ?? 0) / metrics.evaluations.total) * 100 : 0}%` }" /></i>
              <span class="num">{{ metrics.evaluations.scoreBuckets[key] ?? 0 }}</span>
            </li>
          </ul>
        </div>
        <div>
          <h3>近两周训练量</h3>
          <ul class="daily">
            <li v-for="item in metrics.daily" :key="item.date">
              <span class="date">{{ item.date.slice(5) }}</span>
              <span class="count num">{{ item.count }}</span>
            </li>
          </ul>
          <p v-if="!metrics.daily.length" class="empty small">暂无数据</p>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.metrics-panel { padding: 22px; display: grid; gap: 18px; }
.metrics-head h2 { margin: 0 0 6px; font-family: var(--font-display); font-size: 20px; }
.metrics-head p { margin: 0; color: var(--text-2); font-size: 12.5px; }
.cards { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.card { padding: 14px 16px; border: 1px solid var(--line); border-radius: 12px; display: grid; gap: 6px; }
.card strong { font-size: 22px; font-weight: 700; }
.card span { color: var(--text-2); font-size: 11.5px; }
.card.warn { border-color: #d9a7a1; background: rgba(180, 58, 42, .04); }
.card.warn strong { color: #a4342a; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
.split h3 { margin: 0 0 10px; font-size: 13px; color: var(--text-2); font-weight: 600; }
.bars { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.bars li { display: grid; grid-template-columns: 52px 1fr 36px; align-items: center; gap: 10px; font-size: 12px; }
.bars i { height: 4px; background: var(--track); border-radius: 999px; position: relative; overflow: hidden; }
.bars i b { position: absolute; inset: 0 auto 0 0; background: var(--accent); border-radius: 999px; }
.daily { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.daily li { display: grid; gap: 2px; place-items: center; padding: 6px 8px; border: 1px solid var(--line); border-radius: 8px; font-size: 11px; }
.daily .count { font-size: 13px; color: var(--text); }
.empty { margin: 0; padding: 18px 0; text-align: center; color: var(--text-3); font-size: 13px; }
.empty.small { padding: 6px 0; font-size: 12px; }
@media (max-width: 1080px) { .cards { grid-template-columns: repeat(2, 1fr); } .split { grid-template-columns: 1fr; } }
</style>
