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

const INK = '#1c1b18'
const SOFT = '#5c574f'
const MUTED = '#8a8578'
const ACCENT = '#c98a56'
const LINE = '#e5dfd2'
const PAPER = '#f6f3ec'

const clamp = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const }

function buildStarts(durations: number[], fps: number) {
  const starts: number[] = []
  let acc = 0
  for (const seconds of durations) {
    starts.push(acc)
    acc += Math.max(1, Math.round(seconds * fps))
  }
  return starts
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
  const isCover = index === 0
  const step = steps[index - 1]
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], clamp)

  const appear = spring({ frame: local, fps, config: { damping: 200 }, durationInFrames: 18 })
  const rise = interpolate(appear, [0, 1], [26, 0])

  return (
    <AbsoluteFill style={{ backgroundColor: PAPER, fontFamily: '"Microsoft YaHei", sans-serif' }}>
      <AbsoluteFill
        style={{
          background: 'radial-gradient(120% 90% at 15% 0%, #fffdf8 0%, rgba(246,243,236,0) 62%)',
        }}
      />

      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}

      <AbsoluteFill style={{ padding: '96px 120px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 26, letterSpacing: 4, color: MUTED }}>言阶 · 微课</div>
          <div
            style={{
              fontSize: 24,
              color: ACCENT,
              border: `2px solid ${ACCENT}`,
              borderRadius: 999,
              padding: '8px 22px',
            }}
          >
            {dimension}
          </div>
        </div>
        <div style={{ height: 2, background: LINE, marginTop: 28 }} />

        {isCover ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div
              style={{
                fontSize: title.length > 26 ? 58 : title.length > 18 ? 70 : 84,
                fontWeight: 700,
                color: INK,
                lineHeight: 1.25,
                opacity: appear,
                transform: `translateY(${rise}px)`,
                maxWidth: 1560,
              }}
            >
              {title}
            </div>
            <div
              style={{
                fontSize: intro.length > 90 ? 28 : 34,
                color: SOFT,
                marginTop: 40,
                lineHeight: 1.7,
                maxWidth: 1380,
                opacity: interpolate(local, [12, 32], [0, 1], clamp),
              }}
            >
              {intro}
            </div>
            <div style={{ display: 'flex', gap: 28, marginTop: 56 }}>
              {steps.map((item, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: 26,
                    color: MUTED,
                    opacity: interpolate(local, [30 + i * 8, 44 + i * 8], [0, 1], clamp),
                  }}
                >
                  0{i + 1} {item.title}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 32 }}>
              <div
                style={{
                  fontSize: 150,
                  fontWeight: 700,
                  color: '#efe8db',
                  lineHeight: 0.85,
                  transform: `translateY(${interpolate(appear, [0, 1], [40, 0])}px)`,
                }}
              >
                0{index}
              </div>
              <div
                style={{
                  fontSize: 62,
                  fontWeight: 700,
                  color: INK,
                  paddingBottom: 12,
                  opacity: appear,
                  transform: `translateY(${rise}px)`,
                }}
              >
                {step?.title}
              </div>
            </div>

            <div
              style={{
                fontSize: 34,
                color: SOFT,
                lineHeight: 1.75,
                marginTop: 44,
                maxWidth: 1500,
                opacity: interpolate(local, [10, 28], [0, 1], clamp),
              }}
            >
              {step?.detail}
            </div>

            {step?.example ? (
              <div
                style={{
                  marginTop: 44,
                  padding: '30px 38px',
                  background: '#fffdf8',
                  border: `2px solid ${LINE}`,
                  borderLeft: `6px solid ${ACCENT}`,
                  borderRadius: 14,
                  fontSize: 32,
                  color: SOFT,
                  lineHeight: 1.7,
                  maxWidth: 1560,
                  opacity: interpolate(local, [22, 40], [0, 1], clamp),
                  transform: `translateY(${interpolate(local, [22, 40], [18, 0], clamp)}px)`,
                }}
              >
                {step.example}
              </div>
            ) : null}
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ flex: 1, height: 3, background: LINE, borderRadius: 99 }}>
            <div
              style={{
                width: `${progress * 100}%`,
                height: '100%',
                background: ACCENT,
                borderRadius: 99,
              }}
            />
          </div>
          <div style={{ fontSize: 22, color: MUTED }}>
            {Math.min(index + 1, segments.length)} / {segments.length}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  )
}
