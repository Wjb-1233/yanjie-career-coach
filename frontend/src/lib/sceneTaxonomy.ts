export const SCENE_CATEGORIES = [
  '全部', 'HR 初面', '技术一面', '技术二面 / 复面',
  '交叉面 / 总监面', 'HRBP/HR 终面', '大老板 / 高管终面',
] as const
export const DIFFICULTY_LEVELS = [
  { name: '入门', cue: '低压力 · 基础问题', tone: 'easy' },
  { name: '中级', cue: '适度追问 · 具体依据', tone: 'medium' },
  { name: '进阶', cue: '高压力 · 深入边界', tone: 'hard' },
] as const

const legacyCategories: Record<string, string> = {
  行为面试: 'HR 初面',
  压力面试: '交叉面 / 总监面',
  技术面试: '技术一面',
  传统面试: '全部',
  通用沟通: '全部',
  薪资沟通: 'HRBP/HR 终面',
  基础能力提升: '全部',
}

export function normalizeSceneCategory(category: string): string {
  const normalized = legacyCategories[category] ?? category
  return SCENE_CATEGORIES.some((item) => item === normalized) ? normalized : '全部'
}

export function difficultyTone(difficulty: string): string {
  return DIFFICULTY_LEVELS.find((item) => item.name === difficulty)?.tone ?? 'medium'
}

export function difficultyCue(difficulty: string): string {
  return DIFFICULTY_LEVELS.find((item) => item.name === difficulty)?.cue ?? '适度追问'
}

export function isFoundationScene(sceneId: string): boolean {
  return sceneId.startsWith('scene-foundation-')
}
