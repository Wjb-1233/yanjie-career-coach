import { Composition } from 'remotion'
import { LessonVideo, type LessonProps } from './LessonVideo'

const fps = 30

const fallback: LessonProps = {
  title: '把信息说准确',
  dimension: '正确性',
  intro: '这一课讲怎么让每个数字和结论都经得起追问。',
  steps: [
    { title: '先确认信息口径', detail: '说清数据统计的范围、时间和计算方法。', example: '这组数据来自最近三个月的线上订单。' },
    { title: '说明数据来源', detail: '给出可核查的出处，而不是只说结论。', example: '口径按公司统一报表，每天九点同步。' },
    { title: '与简历保持一致', detail: '简历里写过的内容，口头表达要能对上。', example: '简历写的 96.7%，就是这套测评算出来的。' },
  ],
  slideDurations: [6, 8, 8, 8],
  audioSrc: null,
}

const framesOf = (durations: number[]) =>
  Math.max(fps, Math.round(durations.reduce((sum, item) => sum + item, 0) * fps))

export const RemotionRoot: React.FC = () => (
  <Composition
    id="LessonVideo"
    component={LessonVideo}
    durationInFrames={framesOf(fallback.slideDurations)}
    fps={fps}
    width={1920}
    height={1080}
    defaultProps={fallback}
    calculateMetadata={({ props }) => ({
      durationInFrames: framesOf(props.slideDurations ?? fallback.slideDurations),
    })}
  />
)
