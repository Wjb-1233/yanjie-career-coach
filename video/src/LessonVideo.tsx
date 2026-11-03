import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion'

export type LessonStep = { title: string; detail: string; example?: string }

export type LessonProps = {
  title: string
  dimension: string
  intro: string
  steps: LessonStep[]
  slideDurations: number[]
  audioSrc: string | null
}

const BG = '#0b0b0e'
const PANEL = '#131318'
const INK = '#f3f2ef'
const SOFT = '#b3b2b8'
const DIM = '#9c9ba3'
const MUTED = '#82828c'
const ACCENT = '#d08a5e'
const HAIR = 'rgba(255,255,255,0.10)'

const clamp = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const }
const SERIF = '"Songti SC", "Noto Serif CJK SC", SimSun, Georgia, serif'
const SANS = '"Microsoft YaHei", "PingFang SC", sans-serif'

function buildStarts(durations: number[], fps: number) {
  const starts: number[] = []
  let acc = 0
  for (const seconds of durations) {
    starts.push(acc)
    acc += Math.max(1, Math.round(seconds * fps))
  }
  return starts
}

/** 切成朗读短句，用于底部字幕与逐句出现。 */
export function splitSentences(text: string): string[] {
  const cleaned = (text || '').replace(/\s+/g, ' ').trim()
  if (!cleaned) return []
  const parts = cleaned.split(/(?<=[。！？；])/).map((item) => item.trim()).filter(Boolean)
  const merged: string[] = []
  for (const part of parts) {
    if (part.length <= 6 && merged.length) {
      merged[merged.length - 1] += part
    } else {
      merged.push(part)
    }
  }
  return merged.length ? merged : [cleaned]
}

function sentenceWindow(sentences: string[], seconds: number) {
  const totalChars = sentences.reduce((sum, item) => sum + item.length, 0) || 1
  const lead = 0.35
  const usable = Math.max(0.6, seconds - lead)
  let cursor = lead
  return sentences.map((text) => {
    const span = (text.length / totalChars) * usable
    const window = { text, start: cursor, end: cursor + span }
    cursor += span
    return window
  })
}

const Backdrop: React.FC = () => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(120% 80% at 12% 0%, rgba(208,138,94,0.10) 0%, rgba(11,11,14,0) 55%),
                   radial-gradient(90% 70% at 95% 100%, rgba(120,120,180,0.08) 0%, rgba(11,11,14,0) 60%)`,
    }}
  />
)

const Grid: React.FC = () => (
  <AbsoluteFill
    style={{
      backgroundImage:
        'linear-gradient(rgba(255,255,255,0.028) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.028) 1px, transparent 1px)',
      backgroundSize: '120px 120px',
      maskImage: 'radial-gradient(120% 90% at 50% 40%, #000 25%, transparent 78%)',
      WebkitMaskImage: 'radial-gradient(120% 90% at 50% 40%, #000 25%, transparent 78%)',
    }}
  />
)

const Chrome: React.FC<{ progress: number; index: number; total: number; dimension: string }> = ({
  progress,
  index,
  total,
  dimension,
}) => (
  <>
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: 'rgba(255,255,255,0.08)' }}>
      <div style={{ width: `${progress * 100}%`, height: '100%', background: ACCENT }} />
    </div>
    <div
      style={{
        position: 'absolute',
        top: 56,
        left: 96,
        right: 96,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontFamily: SANS,
        fontSize: 22,
        letterSpacing: 6,
        color: MUTED,
      }}
    >
      <span>言阶 · 微课</span>
      <span
        style={{
          color: ACCENT,
          border: '1px solid rgba(208,138,94,0.5)',
          borderRadius: 999,
          padding: '6px 20px',
          letterSpacing: 3,
          fontSize: 19,
        }}
      >
        {dimension}
      </span>
    </div>
    <div
      style={{
        position: 'absolute',
        bottom: 54,
        left: 96,
        right: 96,
        display: 'flex',
        alignItems: 'center',
        gap: 18,
        fontFamily: SANS,
        fontSize: 20,
        color: MUTED,
        letterSpacing: 2,
      }}
    >
      <span style={{ color: INK }}>{String(Math.min(index + 1, total)).padStart(2, '0')}</span>
      <span>/ {String(total).padStart(2, '0')}</span>
      <span style={{ flex: 1, height: 1, background: HAIR, marginLeft: 10 }} />
      <span>言阶 · 面试沟通训练</span>
    </div>
  </>
)

const Captions: React.FC<{ sentences: { text: string; start: number; end: number }[]; time: number }> = ({
  sentences,
  time,
}) => {
  if (!sentences.length) return null
  const activeIndex = sentences.findIndex((item) => time >= item.start && time < item.end)
  const current = sentences[activeIndex === -1 ? sentences.length - 1 : activeIndex]
  return (
    <div
      style={{
        position: 'absolute',
        left: 96,
        right: 96,
        bottom: 104,
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          maxWidth: 1500,
          padding: '16px 30px',
          borderRadius: 12,
          background: 'rgba(10,10,13,0.72)',
          border: `1px solid ${HAIR}`,
          fontFamily: SANS,
          fontSize: 34,
          lineHeight: 1.5,
          color: INK,
          textAlign: 'center',
        }}
      >
        {current?.text}
      </div>
    </div>
  )
}

export const LessonVideo: React.FC<LessonProps> = ({
  title,
  dimension,
  intro,
  steps,
  slideDurations,
  audioSrc,
}) => {
  const frame = useCurrentFrame()
  const { fps, durationInFrames } = useVideoConfig()

  const segments = slideDurations.length ? slideDurations : [6]
  const starts = buildStarts(segments, fps)

  let index = 0
  for (let i = 0; i < starts.length; i += 1) {
    if (frame >= starts[i]) index = i
  }
  const local = frame - starts[index]
  const localSeconds = local / fps
  const slideSeconds = segments[index] ?? 6
  const isCover = index === 0
  const step = steps[index - 1]
  const progress = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, 1], clamp)

  const enter = spring({ frame: local, fps, config: { damping: 200, mass: 0.6 }, durationInFrames: 22 })
  const fade = interpolate(enter, [0, 1], [0, 1])

  const coverSentences = sentenceWindow(splitSentences(intro), slideSeconds)
  const stepSentences = sentenceWindow(splitSentences(step?.detail ?? ''), slideSeconds)

  return (
    <AbsoluteFill style={{ backgroundColor: BG, fontFamily: SANS }}>
      <Backdrop />
      <Grid />

      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}

      <Chrome progress={progress} index={index} total={segments.length} dimension={dimension || '微课'} />

      {isCover ? (
        <AbsoluteFill style={{ padding: '170px 96px', justifyContent: 'center' }}>
          <div style={{ fontFamily: SANS, fontSize: 22, letterSpacing: 8, color: ACCENT, opacity: fade }}>
            学习路径 · {dimension || '表达训练'}
          </div>

          <div style={{ overflow: 'hidden', marginTop: 34 }}>
            <div
              style={{
                fontFamily: SERIF,
                fontSize: title.length > 26 ? 76 : title.length > 18 ? 88 : 104,
                lineHeight: 1.24,
                color: INK,
                transform: `translateY(${interpolate(enter, [0, 1], [70, 0])}px)`,
                letterSpacing: 1,
              }}
            >
              {title}
            </div>
          </div>

          <div
            style={{
              height: 3,
              width: interpolate(enter, [0, 1], [0, 260]),
              background: ACCENT,
              marginTop: 30,
              borderRadius: 4,
            }}
          />

          <div
            style={{
              marginTop: 34,
              maxWidth: 1420,
              fontFamily: SANS,
              fontSize: intro.length > 90 ? 30 : 36,
              lineHeight: 1.72,
              color: SOFT,
              opacity: interpolate(local, [14, 34], [0, 1], clamp),
              transform: `translateY(${interpolate(local, [14, 34], [18, 0], clamp)}px)`,
            }}
          >
            {intro}
          </div>

          <div style={{ display: 'flex', gap: 56, marginTop: 66 }}>
            {steps.map((item, i) => {
              const at = 34 + i * 10
              return (
                <div
                  key={i}
                  style={{
                    opacity: interpolate(local, [at, at + 16], [0, 1], clamp),
                    transform: `translateY(${interpolate(local, [at, at + 16], [16, 0], clamp)}px)`,
                    maxWidth: 520,
                  }}
                >
                  <div style={{ fontFamily: SANS, fontSize: 20, color: ACCENT, letterSpacing: 3 }}>0{i + 1}</div>
                  <div style={{ marginTop: 10, fontFamily: SANS, fontSize: 25, color: SOFT, lineHeight: 1.6 }}>
                    {item.title}
                  </div>
                </div>
              )
            })}
          </div>

          <Captions sentences={coverSentences} time={localSeconds} />
        </AbsoluteFill>
      ) : (
        <AbsoluteFill style={{ padding: '200px 96px 210px', justifyContent: 'center' }}>
          <div style={{ display: 'flex', gap: 44, alignItems: 'flex-start' }}>
            <div
              style={{
                fontFamily: SANS,
                fontSize: 132,
                fontWeight: 200,
                color: 'transparent',
                WebkitTextStroke: `1px ${ACCENT}`,
                lineHeight: 0.9,
                opacity: interpolate(enter, [0, 1], [0, 0.9]),
                transform: `translateY(${interpolate(enter, [0, 1], [24, 0])}px)`,
              }}
            >
              {String(index).padStart(2, '0')}
            </div>

            <div style={{ flex: 1 }}>
              <div style={{ overflow: 'hidden' }}>
                <div
                  style={{
                    fontFamily: SERIF,
                    fontSize: 66,
                    lineHeight: 1.3,
                    color: INK,
                    transform: `translateY(${interpolate(enter, [0, 1], [46, 0])}px)`,
                  }}
                >
                  {step?.title}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 34, maxWidth: 1480 }}>
                {splitSentences(step?.detail ?? '').map((sentence, i) => {
                  const at = 10 + i * 10
                  return (
                    <div
                      key={i}
                      style={{
                        fontFamily: SANS,
                        fontSize: 32,
                        lineHeight: 1.72,
                        color: i === 0 ? SOFT : DIM,
                        opacity: interpolate(local, [at, at + 18], [0, 1], clamp),
                        transform: `translateY(${interpolate(local, [at, at + 18], [14, 0], clamp)}px)`,
                      }}
                    >
                      {sentence}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {step?.example ? (
            <div
              style={{
                marginTop: 44,
                maxWidth: 1580,
                padding: '26px 34px 26px 30px',
                background: PANEL,
                border: `1px solid ${HAIR}`,
                borderLeft: `3px solid ${ACCENT}`,
                borderRadius: 10,
                opacity: interpolate(local, [30, 52], [0, 1], clamp),
                transform: `translateY(${interpolate(local, [30, 52], [22, 0], clamp)}px)`,
              }}
            >
              <div style={{ fontFamily: SANS, fontSize: 19, letterSpacing: 4, color: ACCENT }}>示范</div>
              <div style={{ marginTop: 12, fontFamily: SANS, fontSize: 29, lineHeight: 1.7, color: SOFT }}>
                {step.example}
              </div>
            </div>
          ) : null}

          <Captions sentences={stepSentences} time={localSeconds} />
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  )
}
