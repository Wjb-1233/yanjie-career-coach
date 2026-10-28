<script setup lang="ts">
import { computed } from 'vue'

import type { ExpressionWarning } from '@/lib/expressionWarnings'

const props = defineProps<{ text: string; warnings: ExpressionWarning[] }>()

const parts = computed(() => {
  const result: { text: string; flagged: boolean }[] = []
  let cursor = 0
  for (const warning of props.warnings) {
    if (warning.start < cursor) continue
    if (warning.start > cursor) result.push({ text: props.text.slice(cursor, warning.start), flagged: false })
    result.push({ text: props.text.slice(warning.start, warning.end), flagged: true })
    cursor = warning.end
  }
  if (cursor < props.text.length) result.push({ text: props.text.slice(cursor), flagged: false })
  return result
})
const labels = computed(() => [...new Set(props.warnings.map((warning) => warning.label))])
</script>

<template>
  <div class="expression-preview" role="status">
    <strong>表达提示：{{ labels.join('、') }}</strong>
    <p><span v-for="(part, index) in parts" :key="index" :class="{ flagged: part.flagged }">{{ part.text }}</span></p>
    <small>试着先说事实，再说明影响与自己的行动，最后提出具体请求。修改后再发送。</small>
  </div>
</template>

<style scoped>
.expression-preview { margin-top:10px; padding:11px 13px; border:1px solid rgba(251,191,36,.3); border-radius:var(--radius); background:rgba(251,191,36,.08); color:#fde68a; font-size:12px; }
.expression-preview p { margin:6px 0; white-space:pre-wrap; line-height:1.6; }
.expression-preview .flagged { border-radius:3px; background:rgba(251,191,36,.28); color:#fff3c4; }
.expression-preview small { color:#e6c984; }
</style>
