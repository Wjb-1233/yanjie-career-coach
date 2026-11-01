<script setup lang="ts">
import { Check, ChevronDown } from 'lucide-vue-next'
import {
  SelectContent,
  SelectItem,
  SelectItemIndicator,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { computed } from 'vue'

interface Option { value: string; label: string; hint?: string }

const props = withDefaults(defineProps<{
  modelValue: string
  options: Option[]
  placeholder?: string
  ariaLabel?: string
  disabled?: boolean
  compact?: boolean
}>(), { placeholder: '请选择', ariaLabel: '', disabled: false, compact: false })

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const selectedLabel = computed(() => props.options.find((item) => item.value === props.modelValue)?.label ?? '')
</script>

<template>
  <SelectRoot
    :model-value="modelValue"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', String($event))"
  >
    <SelectTrigger class="select-trigger" :class="{ compact }" :aria-label="ariaLabel || placeholder">
      <SelectValue :placeholder="placeholder">{{ selectedLabel || placeholder }}</SelectValue>
      <ChevronDown class="select-icon" :size="14" :stroke-width="1.8" aria-hidden="true" />
    </SelectTrigger>

    <SelectPortal>
      <SelectContent class="select-content" position="popper" :side-offset="6">
        <SelectViewport class="select-viewport">
          <SelectItem
            v-for="option in options"
            :key="option.value"
            :value="option.value"
            class="select-item"
          >
            <span class="select-item-text">
              {{ option.label }}
              <small v-if="option.hint">{{ option.hint }}</small>
            </span>
            <SelectItemIndicator class="select-item-check">
              <Check :size="14" :stroke-width="2" aria-hidden="true" />
            </SelectItemIndicator>
          </SelectItem>
        </SelectViewport>
      </SelectContent>
    </SelectPortal>
  </SelectRoot>
</template>

<style scoped>
.select-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--card);
  color: var(--text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: border-color .16s var(--ease), background .16s var(--ease), box-shadow .16s var(--ease);
}
.select-trigger.compact { min-height: 30px; padding: 0 10px; font-size: 12px; }
.select-trigger:hover { border-color: var(--border-bright); }
.select-trigger:focus-visible { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.select-trigger[data-disabled] { opacity: .5; cursor: not-allowed; }
.select-icon { flex: none; color: var(--text-3); transition: transform .16s var(--ease); }
.select-trigger[data-state='open'] .select-icon { transform: rotate(180deg); }
.select-trigger[data-state='open'] { border-color: var(--accent); }
</style>

<style>
/* 面板挂在 body 上，不能用 scoped */
.select-content {
  z-index: 80;
  min-width: var(--reka-select-trigger-width, 180px);
  max-height: 280px;
  padding: 5px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card-2);
  box-shadow: 0 18px 40px rgba(0, 0, 0, .38);
  backdrop-filter: blur(18px) saturate(120%);
  animation: select-in .14s var(--ease);
}
@keyframes select-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: none; }
}
.select-viewport { display: grid; gap: 2px; }
.select-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  color: var(--text-2);
  font-size: 12.5px;
  cursor: pointer;
  outline: none;
  user-select: none;
}
.select-item[data-highlighted] { background: var(--overlay-3); color: var(--text); }
.select-item[data-state='checked'] { color: var(--text); }
.select-item-text { display: grid; gap: 2px; }
.select-item-text small { color: var(--text-3); font-size: 10.5px; }
.select-item-check { color: var(--accent-strong); display: inline-flex; }
</style>
