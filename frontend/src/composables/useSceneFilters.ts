import { computed, shallowRef, watch, type ShallowRef } from 'vue'
import { useRoute } from 'vue-router'

import type { Scene } from '@/lib/types'
import { DIFFICULTY_LEVELS, normalizeSceneCategory, SCENE_CATEGORIES, isFoundationScene } from '@/lib/sceneTaxonomy'

export function useSceneFilters(scenes: ShallowRef<Scene[]>) {
  const route = useRoute()
  const activeCategory = shallowRef(normalizeSceneCategory(String(route.query.category ?? '全部')))
  const activeIndustry = shallowRef('全部行业')
  const activePosition = shallowRef('全部岗位')
  const activeDifficulty = shallowRef('全部难度')
  const query = shallowRef('')

  const planId = computed(() => String(route.query.planId ?? ''))
  const taskKey = computed(() => String(route.query.taskKey ?? ''))
  const recommendedSceneId = computed(() => String(route.query.sceneId ?? ''))
  const foundationFocus = computed(() => isFoundationScene(recommendedSceneId.value))
  const catalogScenes = computed(() => scenes.value.filter((scene) =>
    !isFoundationScene(scene.id) || (foundationFocus.value && scene.id === recommendedSceneId.value)))
  const industries = computed(() => ['全部行业', ...new Set(catalogScenes.value
    .filter((scene) => !isFoundationScene(scene.id)).map((scene) => scene.industry))])
  const industryScenes = computed(() => catalogScenes.value.filter((scene) =>
    activeIndustry.value === '全部行业' || scene.industry === activeIndustry.value || scene.industry === '综合行业'))
  const positions = computed(() => ['全部岗位', ...new Set(catalogScenes.value
    .filter((scene) => activeIndustry.value === '全部行业' || scene.industry === activeIndustry.value)
    .map((scene) => scene.position))])
  const positionScenes = computed(() => industryScenes.value.filter((scene) =>
    activePosition.value === '全部岗位' || scene.position === activePosition.value || scene.position === '应届毕业生'))
  const categories = computed(() => {
    const available = new Set(positionScenes.value.map((scene) => scene.category))
    return SCENE_CATEGORIES.filter((category) => category === '全部' || available.has(category))
  })
  const categoryScenes = computed(() => positionScenes.value.filter((scene) =>
    activeCategory.value === '全部' || scene.category === activeCategory.value))
  const difficulties = computed(() => {
    const available = new Set(categoryScenes.value.map((scene) => scene.difficulty))
    return ['全部难度', ...DIFFICULTY_LEVELS.map((level) => level.name).filter((name) => available.has(name))]
  })
  const visibleScenes = computed(() => categoryScenes.value
    .filter((scene) => {
      if (recommendedSceneId.value && scene.id !== recommendedSceneId.value) return false
      if (activeDifficulty.value !== '全部难度' && scene.difficulty !== activeDifficulty.value) return false
      const text = `${scene.title}${scene.background}${scene.tags.join('')}${scene.industry}${scene.position}${scene.roleName}`.toLowerCase()
      return text.includes(query.value.trim().toLowerCase())
    })
    .sort((a, b) => SCENE_CATEGORIES.indexOf(a.category as (typeof SCENE_CATEGORIES)[number])
      - SCENE_CATEGORIES.indexOf(b.category as (typeof SCENE_CATEGORIES)[number])
      || DIFFICULTY_LEVELS.findIndex((level) => level.name === a.difficulty)
      - DIFFICULTY_LEVELS.findIndex((level) => level.name === b.difficulty)))

  watch(() => route.query.category, (category) => {
    activeCategory.value = normalizeSceneCategory(String(category ?? '全部'))
  })
  watch(() => route.query.sceneId, () => {
    activeCategory.value = '全部'
    activeIndustry.value = '全部行业'
    activePosition.value = '全部岗位'
    activeDifficulty.value = '全部难度'
    query.value = ''
  })
  watch(categories, () => {
    if (!categories.value.includes(activeCategory.value as (typeof SCENE_CATEGORIES)[number])) activeCategory.value = '全部'
  })
  watch(activeIndustry, () => {
    activePosition.value = '全部岗位'
    activeDifficulty.value = '全部难度'
  })
  watch(activePosition, () => { activeDifficulty.value = '全部难度' })
  watch(activeCategory, () => { activeDifficulty.value = '全部难度' })

  return {
    activeCategory, activeIndustry, activePosition, activeDifficulty, query,
    categories, industries, positions, difficulties, visibleScenes, catalogScenes, foundationFocus,
    planId, taskKey, recommendedSceneId,
  }
}
