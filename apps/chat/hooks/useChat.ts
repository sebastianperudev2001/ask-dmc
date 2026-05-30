'use client'
import { useState, useCallback } from 'react'
import { Effect, Stream } from 'effect'
import type { Message, BotMsg, UserMsg, Source } from '@/types/chat'
import { ChatService } from '@/lib/ChatService'
import { useRuntime } from '@/lib/RuntimeProvider'

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
  sendMessage: (text: string) => void
  clearMessages: () => void
}

export const useChat = (): UseChatReturn => {
  const runtime = useRuntime()
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

  const sendMessage = useCallback((text: string) => {
    if (busy) return

    const userMsg = buildUserMsg(text)
    const botMsg = initialBotMsg(text)
    setMessages((prev) => [...prev, userMsg, botMsg])
    setBusy(true)

    runtime.runFork(
      Effect.gen(function* () {
        const svc = yield* ChatService
        yield* svc.stream(text).pipe(
          Stream.tap((chunk) =>
            Effect.sync(() => {
              if (chunk._tag === 'text') patchLast((b) => applyChunk(b, chunk.chunk))
              if (chunk._tag === 'sources') patchLast((b) => applyDone(b, chunk.sources))
            })
          ),
          Stream.catchAll(() =>
            Stream.fromEffect(Effect.sync(() => patchLast((b) => applyDone(b, []))))
          ),
          Stream.ensuring(Effect.sync(() => setBusy(false))),
          Stream.runDrain,
        )
      })
    )
  }, [runtime, busy])

  const clearMessages = useCallback(() => {
    if (!busy) setMessages([])
  }, [busy])

  return { messages, busy, sendMessage, clearMessages }
}
