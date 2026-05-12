export type Source = {
  course: string
  section: string
  distance: number
}

export type ChatPhase = 'searching' | 'streaming' | 'done'

export type UserMsg = {
  id: string
  role: 'user'
  text: string
}

export type BotMsg = {
  id: string
  role: 'bot'
  phase: ChatPhase
  question: string      // the user's original question — shown in ToolCallBlock args
  answer: string
  answerDone: boolean
  sources: Source[]
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

export type Suggestion = {
  title: string
  sub: string
}
