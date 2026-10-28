<script setup lang="ts">
import { computed } from 'vue'

import type { Scores } from '@/lib/types'

const props = withDefaults(defineProps<{ scores: Scores; quiet?: boolean }>(), { quiet: false })

const AXES: Array<{ key: keyof Scores; label: string }> = [
  { key: 'logic', label: '逻辑性' },
  { key: 'appropriateness', label: '得体性' },
  { key: 'impact', label: '感染力' },
  { key: 'relevance', label: '针对性' },
  { key: 'concision', label: '简洁度' },
]

const CX = 140
const CY = 116
const RADIUS = props.quiet ? 72 : 80
const LABEL_RADIUS = props.quiet ? 92 : 100

function point(index: number, radius: number): { x: number; y: number } {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / AXES.length
  return { x: CX + Math.cos(angle) * radius, y: CY + Math.sin(angle) * radius }
}

function polygon(radius: number): string {
  return AXES.map((_, index) => {
    const { x, y } = point(index, radius)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

const rings = computed(() => [1, 2, 3, 4].map((step) => ({ radius: (RADIUS * step) / 4, points: polygon((RADIUS * step) / 4) })))
const spokes = computed(() => AXES.map((_, index) => point(index, RADIUS)))

const shape = computed(() => {
  return AXES.map((axis, index) => {
    const value = Math.max(0, Math.min(5, Number(props.scores[axis.key]) || 0))
    const { x, y } = point(index, (RADIUS * value) / 5)
    return { x: Number(x.toFixed(1)), y: Number(y.toFixed(1)) }
  })
})
const shapePoints = computed(() => shape.value.map((p) => `${p.x},${p.y}`).join(' '))

const labels = computed(() => AXES.map((axis, index) => {
  const { x, y } = point(index, LABEL_RADIUS)
  const anchor = index === 0 ? 'middle' : index < 3 ? 'start' : 'end'
  const dx = anchor === 'start' ? 6 : anchor === 'end' ? -6 : 0
  const dy = index === 0 ? -2 : 4
  return { label: axis.label, x: Number((x + dx).toFixed(1)), y: Number((y + dy).toFixed(1)), anchor }
}))
</script>

<template>
  <svg
    class="radar"
    :class="{ quiet }"
    viewBox="0 0 280 244"
    role="img"
    aria-label="五维沟通能力雷达图"
  >
    <g class="grid">
      <polygon
        v-for="(ring, index) in rings"
        :key="`ring-${index}`"
        :points="ring.points"
        :class="[`ring-${index + 1}`, { outer: index === rings.length - 1 }]"
      />
      <line
        v-for="(spoke, index) in spokes"
        :key="`spoke-${index}`"
        :x1="CX"
        :y1="CY"
        :x2="spoke.x.toFixed(1)"
        :y2="spoke.y.toFixed(1)"
      />
    </g>

    <polygon class="shape" :points="shapePoints" />
    <circle
      v-for="(vertex, index) in shape"
      :key="`vertex-${index}`"
      class="vertex"
      :cx="vertex.x"
      :cy="vertex.y"
      r="2.6"
    />
    <circle class="core" :cx="CX" :cy="CY" r="1.6" />

    <g class="labels">
      <text
        v-for="item in labels"
        :key="item.label"
        :x="item.x"
        :y="item.y"
        :text-anchor="item.anchor"
      >{{ item.label }}</text>
    </g>
  </svg>
</template>

<style scoped>
.radar { display: block; width: 100%; height: auto; max-width: 340px; margin: 0 auto; overflow: visible; }
.grid polygon { fill: none; stroke: var(--radar-grid); stroke-width: 1; }
.grid polygon.outer { stroke: var(--radar-grid-outer); }
.grid line { stroke: var(--radar-grid); stroke-width: 1; }
.shape {
  fill: var(--radar-fill);
  stroke: var(--radar-stroke);
  stroke-width: 1.2;
  stroke-linejoin: round;
  transition: all .5s var(--ease);
}
.vertex { fill: var(--chart-dot); }
.core { fill: var(--text-3); }
.labels text {
  fill: var(--text-3);
  font-family: var(--font-ui);
  font-size: 11px;
  letter-spacing: .12em;
}
.quiet .labels text { fill: var(--text-3); }
@media (prefers-reduced-motion: reduce) { .shape { transition: none; } }
</style>
