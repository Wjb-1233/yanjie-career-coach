<script setup lang="ts">
import { computed } from 'vue'

import AnimatedNumber from '@/components/report/AnimatedNumber.vue'

const props = defineProps<{
  trainingCount: number
  latestScore: number
  latestDegraded?: boolean
  focus: string
  styleTags: string[]
  lastTrainedAt?: string | null
  trends?: Array<{ date: string; score: number }>
}>()

const spark = computed(() => {
  const points = (props.trends ?? []).slice(-10)
  if (points.length < 2) return null
  const width = 168
  const height = 34
  const scores = points.map((item) => item.score)
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const span = max - min || 1
  const coords = scores.map((score, index) => {
    const x = (index / (scores.length - 1)) * width
    const y = height - ((score - min) / span) * (height - 6) - 3
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return { width, height, path: coords.join(' '), last: coords[coords.length - 1].split(',') }
})

const caption = computed(() => {
  if (!props.trainingCount) return '完成一次场景训练后，这里会显示综合评分'
  const date = props.lastTrainedAt ? formatDate(props.lastTrainedAt) : ''
  return date ? `来自最近一次已完成的场景训练 · ${date}` : '来自最近一次已完成的场景训练'
})


function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`
}
</script>

<template>
  <section class="hero panel" aria-labelledby="latest-score-title">
    <div class="hero-main">
      <p id="latest-score-title" class="label">综合评分</p>

      <div v-if="trainingCount" class="figure">
        <span class="num"><AnimatedNumber :value="latestScore" /></span>
        <span v-if="latestDegraded" class="degraded-tag">规则兜底</span>
        <span class="den">/ 100</span>
        <div v-if="spark" class="spark" aria-hidden="true">
          <svg :viewBox="`0 0 ${spark.width} ${spark.height}`" preserveAspectRatio="none">
            <polyline :points="spark.path" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
            <circle :cx="spark.last[0]" :cy="spark.last[1]" r="2.4" fill="currentColor" />
          </svg>
          <span>最近 {{ (trends ?? []).slice(-10).length }} 次</span>
        </div>
      </div>
      <p v-else class="empty-score">还没有评分<span>完成一次对练后生成</span></p>

      <p v-if="trainingCount" class="caption">{{ caption }}</p>


      <RouterLink class="cta" to="/scenes">
        <span>{{ trainingCount ? '开始一次训练' : '开始第一次训练' }}</span>
        <svg width="15" height="10" viewBox="0 0 15 10" fill="none" aria-hidden="true">
          <path d="M0 5h13M9.4 1.4 13 5l-3.6 3.6" stroke="currentColor" stroke-width="1.1" />
        </svg>
      </RouterLink>
    </div>

    <dl class="hero-facts">
      <div class="fact">
        <dt>累计训练</dt>
        <dd><span class="num value">{{ trainingCount }}</span><em>次</em></dd>
      </div>
      <div class="fact">
        <dt>当前提升重点</dt>
        <dd class="focus"><i class="dot" aria-hidden="true" /><span class="focus-name">{{ trainingCount ? focus : '尚未生成' }}</span></dd>
      </div>
      <div class="fact">
        <dt>表达风格</dt>
        <dd class="soft tags"><span v-for="tag in styleTags.slice(0, 3)" :key="tag">{{ tag }}</span><em v-if="!styleTags.length">待首次训练</em></dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 328px;
  border-radius: var(--radius);
}
.hero-main { display: flex; flex-direction: column; padding: 36px 40px 34px; }

.label { margin: 0; color: var(--text-3); font-size: 11px; letter-spacing: .2em; }

.figure { display: flex; align-items: flex-end; gap: 12px; margin: 26px 0 0; }
.figure .num {
  color: var(--text);
  font-family: var(--font-num);
  font-size: clamp(104px, 11.4vw, 156px);
  font-weight: 200;
  font-variant-numeric: tabular-nums;
  letter-spacing: -.055em;
  line-height: .8;
}
.figure .num.dash { color: var(--text-3); letter-spacing: 0; }
.empty-score { margin: 10px 0 0; display: grid; gap: 6px; font-size: 22px; font-weight: 600; letter-spacing: -.01em; }
.empty-score span { color: var(--text-3); font-size: 12.5px; font-weight: 400; letter-spacing: .02em; }
.figure .den { padding-bottom: 12px; color: var(--text-3); font-family: var(--font-num); font-size: 13px; letter-spacing: .06em; }

.caption { margin: 22px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.7; letter-spacing: .02em; }

.cta {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 14px;
  margin-top: auto;
  padding: 12px 18px 12px 20px;
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .04em;
  transition: background var(--ease), border-color var(--ease), gap var(--ease);
}
.cta svg { transition: transform var(--ease); }
.cta:hover { background: var(--accent-strong); border-color: var(--accent-strong); color: #fff; gap: 18px; }
.cta:hover svg { transform: translateX(2px); }

.hero-facts { display: flex; flex-direction: column; margin: 0; border-left: 1px solid var(--divider); }
.fact {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: center;
  gap: 9px;
  padding: 18px 26px;
  border-bottom: 1px solid var(--divider);
}
.fact:last-child { border-bottom: 0; }
.fact dt { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.fact dd { display: flex; align-items: baseline; gap: 7px; margin: 0; }
.fact dd.tags { flex-wrap: wrap; gap: 6px; align-items: center; }
.fact dd.tags span { padding: 2px 8px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-2); font-size: 10.5px; letter-spacing: .02em; }
.fact dd.tags em { color: var(--text-3); font-style: normal; font-size: 12px; }
.fact .value { color: var(--text); font-family: var(--font-num); font-size: 26px; font-weight: 300; letter-spacing: -.01em; }
.fact em { color: var(--text-3); font-size: 12px; font-style: normal; }
.fact .focus-name { color: var(--text); font-size: 20px; font-weight: 400; letter-spacing: .02em; }
.fact .dot { display: inline-block; width: 5px; height: 5px; margin-right: 8px; transform: translateY(-3px); background: var(--accent); }
.fact .soft { color: var(--text-2); font-size: 13px; line-height: 1.6; letter-spacing: .02em; }

@media (max-width: 900px) {
  .hero { grid-template-columns: 1fr; }
  .hero-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-top: 1px solid var(--divider); border-left: 0; }
  .fact { border-right: 1px solid var(--divider); border-bottom: 0; padding: 16px 20px; }
  .fact:last-child { border-right: 0; }
}
@media (max-width: 760px) {
  .hero-main { padding: 30px 24px 26px; }
  .figure .num { font-size: clamp(88px, 26vw, 132px); }
  .cta { margin-top: 28px; }
  .hero-facts { grid-template-columns: 1fr 1fr; }
  .fact:nth-child(2) { border-right: 0; }
  .fact:nth-child(3) { grid-column: 1 / -1; border-top: 1px solid var(--divider); border-right: 0; }
}

:root[data-theme='dark'] .hero {
  background: rgba(12, 10, 26, .66);
  border-color: rgba(255, 255, 255, .12);
  backdrop-filter: blur(20px) saturate(120%);
  -webkit-backdrop-filter: blur(20px) saturate(120%);
}
:root[data-theme='dark'] .cta {
  border-color: var(--accent);
  background: var(--accent);
  color: #0b0b0e;
}
:root[data-theme='dark'] .cta:hover {
  background: var(--accent-strong);
  border-color: var(--accent-strong);
  color: #0b0b0e;
}
.degraded-tag { margin-left: 10px; padding: 3px 10px; border: 1px solid var(--accent); border-radius: 999px; color: var(--accent-strong); font-size: 11px; }

.spark { margin-left: auto; align-self: flex-end; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; color: var(--accent); }
.spark svg { width: 168px; height: 40px; }
@media (max-width: 720px) { .spark { display: none; } }
.spark span { color: var(--text-3); font-size: 11px; letter-spacing: .04em; }
.hero .figure .num { font-size: clamp(64px, 7vw, 86px); font-weight: 600; letter-spacing: -.045em; }
</style>
