export type CourseRecommendation = {
  courseId: string
  name: string
  similarityScore: number
}

export type ProfileDataPrefill = {
  budget: number | null
  maxDurationWeeks: number | null
  professionalBackground: string | null
  desiredStack: string | null
  name: string | null
  email: string | null
}

export type ProfileData = {
  budget: number
  maxDurationWeeks: number
  professionalBackground: string
  desiredStack: string
  name: string
  email: string
}

export type ChatPhase = 'streaming' | 'awaitingProfileData' | 'done'

export type UserMsg = {
  id: string
  role: 'user'
  text: string
}

export type ToolCallInfo = {
  name: string
  argsText: string
  resultText: string | null
  status: 'calling' | 'done'
}

export type BotMsg = {
  id: string
  role: 'bot'
  phase: ChatPhase
  answer: string
  answerDone: boolean
  recommendations: CourseRecommendation[]
  toolCalls: ToolCallInfo[]
  profileRequest: { callId: string; prefill: ProfileDataPrefill } | null
}

export type Message = UserMsg | BotMsg

export type HistoryItem = {
  id: string
  title: string
  preview: string
  active?: boolean
}

export type HistoryGroup = {
  group: string
  items: HistoryItem[]
}

// Real conversation history (replaces the hardcoded mock Sidebar list — added after
// user feedback that it didn't reflect actual saved conversations).
export type ConversationSummary = {
  conversationId: string
  preview: string
  lastActivityAt: string
}

export type Suggestion = {
  title: string
  sub: string
}
