<script setup lang="ts">
import { onUnmounted, shallowRef, watch } from 'vue'

const props = withDefaults(defineProps<{ value: number; duration?: number }>(), { duration: 900 })
const display = shallowRef(0)
let frame = 0

watch(() => props.value, (value) => {
  cancelAnimationFrame(frame)
  const target = Math.max(0, Number.isFinite(value) ? value : 0)
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    display.value = Math.round(target)
    return
  }
  const started = performance.now()
  const from = display.value
  const tick = (now: number) => {
    const progress = Math.min(1, (now - started) / props.duration)
    const eased = 1 - Math.pow(1 - progress, 3)
    display.value = Math.round(from + (target - from) * eased)
    if (progress < 1) frame = requestAnimationFrame(tick)
  }
  frame = requestAnimationFrame(tick)
}, { immediate: true })

onUnmounted(() => cancelAnimationFrame(frame))
</script>

<template>{{ display }}</template>
