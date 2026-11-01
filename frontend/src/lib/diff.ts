export interface DiffSegment {
  type: 'same' | 'add' | 'del'
  text: string
}

const MAX_CHARS = 900

/**
 * 字符级 LCS 差异。用于话术版本与用户原话的逐字对比。
 * 超过 MAX_CHARS 时退化为整段标记，避免 O(n²) 卡顿。
 */
export function diffChars(base: string, next: string): DiffSegment[] {
  const a = Array.from(base)
  const b = Array.from(next)
  if (!a.length) return b.length ? [{ type: 'add', text: next }] : []
  if (!b.length) return [{ type: 'del', text: base }]
  if (a.length * b.length > MAX_CHARS * MAX_CHARS / 4) {
    return [{ type: 'del', text: base }, { type: 'add', text: next }]
  }

  const m = a.length
  const n = b.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const out: DiffSegment[] = []
  const push = (type: DiffSegment['type'], text: string) => {
    if (!text) return
    const last = out[out.length - 1]
    if (last && last.type === type) last.text += text
    else out.push({ type, text })
  }

  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      push('same', a[i])
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push('del', a[i])
      i += 1
    } else {
      push('add', b[j])
      j += 1
    }
  }
  while (i < m) {
    push('del', a[i])
    i += 1
  }
  while (j < n) {
    push('add', b[j])
    j += 1
  }
  return out
}

export function diffStats(segments: DiffSegment[]): { added: number; removed: number } {
  let added = 0
  let removed = 0
  for (const segment of segments) {
    const length = Array.from(segment.text).length
    if (segment.type === 'add') added += length
    if (segment.type === 'del') removed += length
  }
  return { added, removed }
}
