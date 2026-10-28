export interface ApiEnvelope<T> {
  data: T
  meta: { timestamp: string }
}

export interface User {
  id: string
  email: string
  displayName: string
  role: 'STUDENT' | 'ADMIN'
  bio: string | null
}

export interface Scene {
  id: string
  category: string
  title: string
  industry: string
  position: string
  roleName: string
  difficulty: string
  background: string
  goal: string
  tags: string[]
  openingLine: string
  favorite: boolean
}

export interface TrainingMessage {
  id: string
  roundNo: number
  speaker: 'USER' | 'AI'
  content: string
  flagged: boolean
  flags: readonly string[]
  createdAt: string
}

export interface TrainingSession {
  id: string
  sceneId: string
  sceneTitle: string
  status: string
  stage: string
  currentRound: number
  maxRounds: number
  startedAt: string
  finishedAt: string | null
  resumeFilename: string | null
  resumeOpeningDegraded: boolean
  messages: TrainingMessage[]
}

export interface Scores {
  logic: number
  appropriateness: number
  impact: number
  relevance: number
  concision: number
}

export type ScoreDimension = keyof Scores

export interface AbilityAttempt {
  id: string
  answer: string
  score: number
  answerQuote: string
  strength: string
  gap: string
  nextAction: string
  createdAt: string
}

export interface AbilityPractice {
  evaluationId: string
  sessionId: string
  sceneId: string
  sceneTitle: string
  roundCount: number
  overallScore: number
  reportSummary: string
  dimension: ScoreDimension
  dimensionLabel: string
  baselineScore: number
  reportDegraded: boolean
  question: string
  originalAnswer: string
  evidenceQuote: string | null
  evidenceReason: string | null
  targetAction: string
  reviewTurns: Array<{
    roundNo: number
    question: string
    answer: string
    flags: string[]
    isFocusEvidence: boolean
  }>
  reportSuggestions: Array<{ roundNo: number; problem: string; original: string; rewrite: string }>
  attempts: AbilityAttempt[]
}

export interface ScriptVersion {
  id: string
  sceneId: string | null
  createdAt: string | null
  style: string
  content: string
  highlights: string[]
  favorite: boolean
}

export interface Evaluation {
  id: string
  sessionId: string
  scores: Scores
  overallScore: number
  summary: string
  suggestions: Array<{ roundNo: number; problem: string; original: string; rewrite: string }>
  styleTags: string[]
  createdAt: string
  degraded: boolean
  evidence: ScoreEvidence[]
  planId: string | null
}

export interface ScoreEvidence {
  dimension: keyof Scores
  roundNo: number
  questionMessageId: string
  answerMessageId: string
  question: string
  answer: string
  quote: string
  reason: string
  nextAction: string
  resumeQuote: string | null
}

export interface Course {
  id: string
  title: string
  dimension: string
  minutes: number
  description: string
  content: string
  progress: number
  completed: boolean
}

export interface AdminUserRecord {
  id: string
  email: string
  displayName: string
  role: 'STUDENT' | 'ADMIN'
  active: boolean
  bio: string | null
  createdAt: string
}

export interface AdminSceneRecord extends Omit<Scene, 'favorite'> { active: boolean }

export interface AdminCourseRecord extends Course { active: boolean }

export interface AdminSessionRecord {
  id: string
  userId: string
  sceneTitle: string
  userName: string
  email: string
  status: string
  rounds: number
  startedAt: string
  overallScore: number | null
}

export type PlanTaskAction = 'COURSE' | 'TRAINING' | 'REWRITE' | 'RETEST'

export interface PersonalizedLesson {
  title: string
  intro: string
  steps: ReadonlyArray<{ title: string; explanation: string; example: string }>
  exercise: string
  aiGenerated: boolean
}

export interface TrainingPlanTask {
  key: string
  day: number
  task: string
  actionType: PlanTaskAction
  completed: boolean
  completedAt: string | null
  evidence: string | null
  courseId: string | null
  sceneId: string | null
  sourceSessionId: string | null
  lesson: PersonalizedLesson | null
  completedSteps: readonly number[]
  learningProgress: number
  practiceAnswer: string | null
  practiceFeedback: string | null
  practicePassed: boolean
  practiceDegraded: boolean
  rewriteFeedback: string | null
  rewritePassed: boolean
  rewriteDegraded: boolean
}

export interface ScoreComparison {
  baselineSessionId: string
  retestSessionId: string
  sceneId: string
  baselineScores: Scores
  retestScores: Scores
  scoreDeltas: Record<keyof Scores, number>
  baselineOverall: number
  retestOverall: number
  overallDelta: number
  focusDelta: number
  status: 'IMPROVED' | 'NEEDS_PRACTICE' | 'PROVISIONAL'
  recommendation: string
}

export interface TrainingPlan {
  id: string
  title: string
  focusDimension: string
  status: 'ACTIVE' | 'COMPLETED'
  progress: number
  tasks: readonly TrainingPlanTask[]
  comparison: ScoreComparison | null
  createdAt: string
}

