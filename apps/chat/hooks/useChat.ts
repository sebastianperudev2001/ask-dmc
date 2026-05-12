'use client'
import { useState, useCallback } from 'react'
import type { Message, BotMsg, UserMsg, Source } from '@/types/chat'
import { streamAsk } from '@/lib/api'

// ── Pure state helpers (exported for testing) ──────────────────────────────

export const buildUserMsg = (text: string): UserMsg => ({
  id: crypto.randomUUID(),
  role: 'user',
  text,
})

export const initialBotMsg = (question: string): BotMsg => ({
  id: crypto.randomUUID(),
  role: 'bot',
  phase: 'searching',
  question,
  answer: '',
  answerDone: false,
  sources: [],
})

export const applyChunk = (msg: BotMsg, chunk: string): BotMsg => ({
  ...msg,
  phase: 'streaming',
  answer: msg.answer + chunk,
})

export const applyDone = (msg: BotMsg, sources: Source[]): BotMsg => ({
  ...msg,
  phase: 'done',
  answerDone: true,
  sources,
})

// ── Hook ───────────────────────────────────────────────────────────────────

type UseChatReturn = {
  messages: Message[]
  busy: boolean
  sendMessage: (text: string) => Promise<void>
  clearMessages: () => void
}

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)

  const patchLast = (patch: (prev: BotMsg) => BotMsg) => {
    setMessages((prev) => {
      const idx = prev.findLastIndex((m) => m.role === 'bot')
      if (idx === -1) return prev
      const next = [...prev]
      next[idx] = patch(next[idx] as BotMsg)
      return next
    })
  }

  const sendMessage = useCallback(async (text: string) => {
    if (busy) return

    const userMsg = buildUserMsg(text)
    const botMsg  = initialBotMsg(text)

    setMessages((prev) => [...prev, userMsg, botMsg])
    setBusy(true)

    try {
      for await (const chunk of streamAsk(text, (sources) => {
        patchLast((b) => applyDone(b, sources))
      })) {
        patchLast((b) => applyChunk(b, chunk))
      }
    } catch (err) {
      patchLast((b) => applyDone(b, []))
      console.error('Chat error:', err)
    } finally {
      setBusy(false)
    }
  }, [busy])

  const clearMessages = useCallback(() => {
    if (!busy) setMessages([])
  }, [busy])

  return { messages, busy, sendMessage, clearMessages }
}
