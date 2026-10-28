<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef, useTemplateRef } from 'vue'

import type { Scores } from '@/lib/types'

const props = withDefaults(defineProps<{
  points: Array<{ date: string; score: number; dimensions: Scores }>
  compact?: boolean
}>(), { compact: false })

const host = useTemplateRef<HTMLDivElement>('host')
const width = shallowRef(420)

const height = computed(() => (props.compact ? 152 : 216))
const PAD_LEFT = 26
const PAD_RIGHT = 10
const PAD_TOP = 14
const PAD_BOTTOM = 26

const gradientId = `trend-fill-${Math.random().toString(36).slice(2, 8)}`

const coords = computed(() => {
  const list = props.points
  if (!list.length) return []
  const innerW = Math.max(40, width.value - PAD_LEFT - PAD_RIGHT)
  const innerH = Math.max(30, height.value - PAD_TOP - PAD_BOTTOM)
  const step = list.length > 1 ? innerW / (list.length - 1) : 0
  return list.map((point, index) => {
    const value = Math.max(0, Math.min(100, Number(point.score) || 0))
    return {
      x: PAD_LEFT + (list.length > 1 ? step * index : innerW / 2),
      y: PAD_TOP + innerH - (value / 100) * innerH,
      value,
      date: point.date,
    }
  })
})

const linePath = computed(() => coords.value.map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' '))

const areaPath = computed(() => {
  const list = coords.value
  if (!list.length) return ''
  const baseline = height.value - PAD_BOTTOM
  return `${linePath.value} L${list[list.length - 1].x.toFixed(1)} ${baseline} L${list[0].x.toFixed(1)} ${baseline} Z`
})

const gridLines = computed(() => [0, 50, 100].map((value) => ({
  value,
  y: PAD_TOP + (height.value - PAD_TOP - PAD_BOTTOM) * (1 - value / 100),
})))

const dateLabels = computed(() => {
  const list = coords.value
  if (!list.length) return []
  const stride = Math.max(1, Math.ceil(list.length / 5))
  return list
    .map((point, index) => ({ point, index }))
    .filter((item) => item.index % stride === 0 || item.index === list.length - 1)
    .map((item) => ({
      x: Math.min(width.value - PAD_RIGHT, Math.max(PAD_LEFT, item.point.x)),
      y: height.value - 9,
      text: new Date(item.point.date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }),
    }))
})

let observer: ResizeObserver | null = null

onMounted(() => {
  if (!host.value) return
  width.value = Math.max(220, host.value.clientWidth || 420)
  observer = new ResizeObserver((entries) => {
    const next = entries[0]?.contentRect.width
    if (next && Math.abs(next - width.value) > 1) width.value = next
  })
  observer.observe(host.value)
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div ref="host" class="trend-host" :class="{ compact }">
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      :width="width"
      :height="height"
      preserveAspectRatio="none"
      role="img"
      aria-label="历史训练综合评分趋势"
    >
      <defs>
        <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
          <stop class="stop-top" offset="0%" />
          <stop class="stop-bottom" offset="100%" />
        </linearGradient>
      </defs>

      <g class="grid">
        <line v-for="line in gridLines" :key="line.value" :x1="PAD_LEFT" :x2="width - PAD_RIGHT" :y1="line.y" :y2="line.y" />
        <text v-for="line in gridLines" :key="`t-${line.value}`" class="axis" :x="PAD_LEFT - 8" :y="line.y + 3.5" text-anchor="end">{{ line.value }}</text>
      </g>

      <path class="area" :d="areaPath" :fill="`url(#${gradientId})`" />
      <path class="line" :d="linePath" />
      <circle v-for="(point, index) in coords" :key="`p-${index}`" class="dot" :cx="point.x" :cy="point.y" r="2.4" />

      <g class="dates">
        <text v-for="label in dateLabels" :key="label.text" class="axis" :x="label.x" :y="label.y" text-anchor="middle">{{ label.text }}</text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.trend-host { width: 100%; overflow: hidden; padding-top: 14px; }
.trend-host svg { display: block; }
.grid line { stroke: var(--radar-grid); stroke-width: 1; }
.stop-top { stop-color: var(--radar-fill); }
.stop-bottom { stop-color: transparent; }
.axis { fill: var(--text-3); font-family: var(--font-num); font-size: 10px; letter-spacing: .02em; }
.line { fill: none; stroke: var(--chart-line); stroke-width: 1.3; stroke-linejoin: round; stroke-linecap: round; }
.dot { fill: var(--chart-dot); stroke: var(--bg); stroke-width: 1; }
</style>
