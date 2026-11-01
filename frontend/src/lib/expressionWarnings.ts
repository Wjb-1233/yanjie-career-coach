export interface ExpressionWarning {
  label: string
  phrase: string
  start: number
  end: number
}

const patterns: Record<string, string[]> = {
  命令式表达: ['你必须', '少废话', '照我说的做'],
  推卸责任: ['不关我的事', '都是他们的问题', '我没办法'],
  绝对化表达: ['绝对不可能', '你总是', '你从来不'],
}

export function findExpressionWarnings(text: string): ExpressionWarning[] {
  const matches: ExpressionWarning[] = []
  for (const [label, phrases] of Object.entries(patterns)) {
    for (const phrase of phrases) {
      let index = text.indexOf(phrase)
      while (index !== -1) {
        matches.push({ label, phrase, start: index, end: index + phrase.length })
        index = text.indexOf(phrase, index + phrase.length)
      }
    }
  }
  return matches.sort((left, right) => left.start - right.start || right.end - left.end)
}
