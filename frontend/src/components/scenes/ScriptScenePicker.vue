<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'

import { sceneRelation } from '@/lib/scriptPresentation'
import type { Scene } from '@/lib/types'

const props = defineProps<{ scenes: Scene[] }>()
const sceneId = defineModel<string>({ required: true })
const relationship = shallowRef('')
const relations = computed(() => [...new Set(props.scenes.map(sceneRelation))])
const matchingScenes = computed(() => props.scenes.filter((scene) => sceneRelation(scene) === relationship.value))

watch([() => props.scenes, sceneId], () => {
  const selected = props.scenes.find((scene) => scene.id === sceneId.value)
  if (selected) relationship.value = sceneRelation(selected)
  else if (props.scenes.length) {
    relationship.value = relations.value[0] ?? ''
    sceneId.value = matchingScenes.value[0]?.id ?? ''
  }
}, { immediate: true })

function selectRelationship(value: string): void {
  relationship.value = value
  sceneId.value = matchingScenes.value[0]?.id ?? ''
}
</script>

<template>
  <div class="scene-picker">
    <label for="script-relationship">先选沟通对象
      <select id="script-relationship" class="field" :value="relationship" @change="selectRelationship(($event.target as HTMLSelectElement).value)">
        <option v-for="item in relations" :key="item" :value="item">{{ item }}</option>
      </select>
    </label>
    <label for="script-scene">再选具体场景
      <select id="script-scene" v-model="sceneId" class="field">
        <option v-for="scene in matchingScenes" :key="scene.id" :value="scene.id">{{ scene.title }}</option>
      </select>
    </label>
    <p class="picker-hint">场景与“场景训练”共用同一份资料，共 {{ matchingScenes.length }} 个可选。</p>
  </div>
</template>

<style scoped>
.scene-picker { display: grid; grid-template-columns: minmax(0, .7fr) minmax(0, 1.3fr); gap: 12px 16px; }
.scene-picker label { display: grid; gap: 8px; font-size: 13px; font-weight: 750; }
.picker-hint { grid-column: 1 / -1; margin: 0; color: var(--text-2); font-size: 12px; }
@media (max-width: 680px) { .scene-picker { grid-template-columns: 1fr; } }
</style>
