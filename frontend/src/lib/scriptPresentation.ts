import type { Scene } from './types'

export type ScriptTone = 'professional' | 'concise' | 'warm' | 'review'

export function scriptPresentation(style: string): { label: string; tone: ScriptTone; purpose: string } {
  if (style === '正式' || style === '专业') {
    return { label: '专业', tone: 'professional', purpose: '结构完整、措辞稳妥，适合正式面试回答。' }
  }
  if (style === '简洁') {
    return { label: '简洁', tone: 'concise', purpose: '先交代结论，保留最重要的事实和下一步。' }
  }
  if (style === '亲和') {
    return { label: '亲和', tone: 'warm', purpose: '先回应对方关切，再表达自己的考虑。' }
  }
  return { label: style || '复盘优化', tone: 'review', purpose: '来自训练报告的针对性改写。' }
}

export function sceneRelation(scene: Scene): string {
  const role = scene.roleName
  if (/HR|招聘经理|人力/.test(role)) return '招聘方'
  if (/主管|负责人|总监|直属/.test(role)) return '团队管理者'
  if (role.includes('面试官')) return '面试官'
  return role || '其他沟通对象'
}
