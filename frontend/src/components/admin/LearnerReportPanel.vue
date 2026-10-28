<script setup lang="ts">
defineProps<{ report: { learner: { name: string; email: string; active: boolean }; trainingCount: number; evaluationCount: number; averageScore: number; dimensions: Record<string, number>; weakestDimension: string | null; styleTags: string[]; trends: Array<{ date: string; score: number }> } }>()
const emit = defineEmits<{ close: []; export: [] }>()
</script>

<template>
  <div class="backdrop" role="presentation" @click.self="emit('close')"><section class="report panel" role="dialog" aria-modal="true" aria-label="学员能力报告">
    <header><div><p class="eyebrow">学员能力报告</p><h2>{{ report.learner.name }}</h2><p>{{ report.learner.email }} · {{ report.learner.active ? '账号启用' : '账号停用' }}</p></div><button class="button secondary" @click="emit('close')">关闭</button></header>
    <div class="metrics"><div><b>{{ report.trainingCount }}</b><span>训练次数</span></div><div><b>{{ report.evaluationCount }}</b><span>有效评分</span></div><div><b>{{ report.averageScore }}</b><span>平均综合分</span></div></div>
    <h3>五维能力平均分</h3><div class="dimensions"><div v-for="(score, key) in report.dimensions" :key="key"><span>{{ key }}</span><meter min="1" max="5" :value="score" /> <b>{{ score }}/5</b></div></div>
    <p>主要提升点：<strong>{{ report.weakestDimension || '暂无评分数据' }}</strong></p>
    <p>表达风格标签：{{ [...new Set(report.styleTags)].join('、') || '暂无' }}</p>
    <h3>近期评分</h3><ol class="trend"><li v-for="point in report.trends.slice(-8)" :key="`${point.date}-${point.score}`">{{ point.date }}：{{ point.score }} 分</li></ol>
    <button class="button" @click="emit('export')">导出该学员报告</button>
  </section></div>
</template>

<style scoped>
.backdrop{position:fixed;z-index:50;inset:0;padding:20px;display:grid;place-items:center;background:rgba(28,26,22,.55)}.report{width:min(720px,100%);max-height:90vh;overflow:auto;padding:24px}header{display:flex;justify-content:space-between;gap:12px;align-items:start}h2{margin:0;font:700 26px var(--font-ui)}header p:last-child{color:var(--ink-soft)}h3{margin:22px 0 10px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metrics div{padding:14px;background:var(--sky);border-radius:var(--radius)}.metrics b,.metrics span{display:block}.metrics b{font-size:24px}.metrics span{font-size:12px;color:var(--ink-soft)}.dimensions{display:grid;grid-template-columns:1fr 1fr;gap:10px}.dimensions div{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;align-items:center;font-size:13px}.trend{display:flex;flex-wrap:wrap;gap:8px 24px;padding-left:20px;color:var(--ink-soft);font-size:13px}@media(max-width:600px){.dimensions{grid-template-columns:1fr}}
</style>
