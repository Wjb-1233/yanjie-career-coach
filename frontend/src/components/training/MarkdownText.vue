<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const props = defineProps<{ text: string }>()
const renderer = new MarkdownIt({ html: false, linkify: false, breaks: true })
const html = computed(() => DOMPurify.sanitize(renderer.render(props.text)))
</script>

<template>
  <div class="markdown-body" v-html="html" />
</template>

<style scoped>
.markdown-body { overflow-wrap: anywhere; line-height: 1.75; }
.markdown-body :deep(> :first-child) { margin-top: 0; }
.markdown-body :deep(> :last-child) { margin-bottom: 0; }
.markdown-body :deep(p) { margin: 0 0 10px; }
.markdown-body :deep(h1),.markdown-body :deep(h2),.markdown-body :deep(h3) { margin: 16px 0 8px; font-size: 1.05em; line-height: 1.4; }
.markdown-body :deep(ul),.markdown-body :deep(ol) { margin: 8px 0; padding-left: 22px; }
.markdown-body :deep(li) { margin: 4px 0; }
.markdown-body :deep(pre) { margin: 12px 0; padding: 14px; overflow-x: auto; border-radius:var(--radius-sm); background: var(--card-2); color: var(--text); font: 12px/1.6 ui-monospace, SFMono-Regular, Consolas, monospace; }
.markdown-body :deep(code) { padding: 2px 4px; border-radius: 4px; background: #e8edf5; font: .9em ui-monospace, SFMono-Regular, Consolas, monospace; }
.markdown-body :deep(pre code) { padding: 0; background: transparent; color: inherit; }
.markdown-body :deep(blockquote) { margin: 10px 0; padding-left: 12px; border-left: 2px solid var(--border-bright); color: var(--text-2); }
.markdown-body :deep(pre) { border:1px solid var(--border);background:var(--bg);box-shadow:none;color:var(--text); }
.markdown-body :deep(code) { background:var(--bg-2);color:var(--text); }
.markdown-body :deep(pre code) { background:transparent;color:var(--text); }
.markdown-body :deep(strong) { color:var(--text);font-weight:700; }
.markdown-body :deep(blockquote) { border-color:var(--divider); }
</style>
