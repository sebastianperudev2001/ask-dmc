'use client'
import { useState, useCallback, useEffect, useRef } from 'react'
import { Effect, Fiber, Stream } from 'effect'
import type { Message, BotMsg, UserMsg, CourseRecommendation, ProfileData, ProfileDataPrefill } from '@/types/chat'
import { ChatService } from '@/lib/ChatService'
import {
  clearStoredSessionId,
  fetchConversationHistory,
  getStoredConversationId,
  selectConversation as selectConversationInStorage,
  type PersistedMessage,
} from '@/lib/WsChatService'
import { useRuntime } from '@/lib/RuntimeProvider'

// ── Pure state helpers (exported for testing) ──────────────────────────────

export const buildUserMsg = (text: string): UserMsg => ({
  id: crypto.randomUUID(),
  role: 'user',
  text,
})

export const initialBotMsg = (): BotMsg => ({
  id: crypto.randomUUID(),
  role: 'bot',
  phase: 'streaming',
  answer: '',
  answerDone: false,
  recommendations: [],
  toolCalls: [],
  profileRequest: null,
})

export const applyDelta = (msg: BotMsg, text: string): BotMsg => ({
  ...msg,
  answer: msg.answer + text,
})

export const applyRecommendations = (msg: BotMsg, candidates: CourseRecommendation[]): BotMsg => ({
  ...msg,
  recommendations: candidates,
})

export const applyProfileRequest = (msg: BotMsg, callId: string, prefill: ProfileDataPrefill): BotMsg => ({
  ...msg,
  phase: 'awaitingProfileData',
  profileRequest: { callId, prefill },
})

export const clearProfileRequest = (msg: BotMsg): BotMsg => ({
  ...msg,
  phase: 'streaming',
  profileRequest: null,
})

export const applyPaymentLink = (msg: BotMsg, checkoutUrl: string): BotMsg => ({
  ...msg,
  toolCalls: [
    ...msg.toolCalls,
    { name: 'create_payment_link', argsText: '', resultText: checkoutUrl, status: 'done' as const },
  ],
})

export const markTurnDone = (msg: BotMsg): BotMsg => ({
  ...msg,
  phase: 'done',
  answerDone: true,
})

// The persisted transcript only stores the agent's final text, not the structured
// payment_link_created event — after a reload, applyPaymentLink never runs, so the
// checkout URL the agent wrote inline in its own text would otherwise show up raw
// instead of as a PaymentLinkButton. Recovers it by matching Mercado Pago's checkout
// URL shape (sandbox or production, any country TLD).
const PAYMENT_LINK_PATTERN = /https?:\/\/(?:sandbox\.)?(?:www\.)?mercadopago\.[a-z.]+\/checkout\/\S+/i

export const extractPaymentLink = (text: string): string | null =>
  text.match(PAYMENT_LINK_PATTERN)?.[0] ?? null

// Rehydration after a page reload (found via real Build and Test / user feedback: the
// Foundry thread resumes correctly, but the visible chat was blank). Reconstructs
// Message[] from the persisted transcript — bot messages have no recommendations/
// profileRequest (that structured data isn't persisted, only the final text); toolCalls
// is reconstructed from a payment link found in the text, if any (see extractPaymentLink).
export const messagesFromHistory = (history: PersistedMessage[]): Message[] =>
  history.map((m) => {
    if (m.role === 'user') return buildUserMsg(m.content)

    const paymentLink = extractPaymentLink(m.content)
    return {
      ...initialBotMsg(),
      answer: m.content,
      answerDone: true,
      phase: 'done' as const,
      toolCalls: paymentLink
        ? [{ name: 'create_payment_link', argsText: '', resultText: paymentLink, status: 'done' as const }]
        : [],
    }
  })

// ── Hook ───────────────────────────────────────────────────────────────────

type UseChatReturn = {
  messages: Message[]
  busy: boolean
  sendMessage: (text: string) => void
  submitProfileData: (callId: string, data: ProfileData) => void
  clearMessages: () => void
  switchConversation: (conversationId: string) => void
}

export const useChat = (): UseChatReturn => {
  const runtime = useRuntime()
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)

  // Runs once on mount — rehydrates visible messages from the persisted transcript if
  // a previous conversation_id is stored (see messagesFromHistory docstring above).
  useEffect(() => {
    const conversationId = getStoredConversationId()
    if (!conversationId) return
    fetchConversationHistory(conversationId).then((history) => {
      if (history.length > 0) setMessages(messagesFromHistory(history))
    })
  }, [])

  const patchLastBot = useCallback((patch: (prev: BotMsg) => BotMsg) => {
    setMessages((prev) => {
      const idx = prev.findLastIndex((m) => m.role === 'bot')
      if (idx === -1) return prev
      const next = [...prev]
      next[idx] = patch(next[idx] as BotMsg)
      return next
    })
  }, [])

  // Subscribe once to the persistent WS event stream for the whole component
  // lifetime — unlike incremento 1 (one Stream per question), the connection and its
  // event stream now span the entire conversation (business-logic-model.md Section 9).
  useEffect(() => {
    const fiber = runtime.runFork(
      Effect.gen(function* () {
        const svc = yield* ChatService
        yield* svc.events.pipe(
          Stream.tap((event) =>
            Effect.sync(() => {
              switch (event._tag) {
                case 'delta':
                  patchLastBot((b) => applyDelta(b, event.text))
                  break
                case 'profileDataRequested':
                  patchLastBot((b) => applyProfileRequest(b, event.callId, event.prefill))
                  break
                case 'recommendationsReady':
                  patchLastBot((b) => applyRecommendations(b, event.candidates))
                  break
                case 'paymentLinkCreated':
                  patchLastBot((b) => applyPaymentLink(b, event.checkoutUrl))
                  break
                case 'turnDone':
                  patchLastBot((b) => markTurnDone(b))
                  setBusy(false)
                  break
                case 'sessionCreated':
                  break // WsChatService already persists service_session_id itself
              }
            })
          ),
          Stream.catchAll((err) =>
            Stream.fromEffect(
              Effect.sync(() => {
                console.error('Chat error:', err)
                patchLastBot((b) => markTurnDone(b))
                setBusy(false)
              })
            )
          ),
          Stream.runDrain
        )
      })
    )
    return () => {
      runtime.runFork(Fiber.interrupt(fiber))
    }
  }, [runtime, patchLastBot])

  const sendMessage = useCallback(
    (text: string) => {
      if (busy) return
      const userMsg = buildUserMsg(text)
      const botMsg = initialBotMsg()
      setMessages((prev) => [...prev, userMsg, botMsg])
      setBusy(true)

      runtime.runFork(
        Effect.gen(function* () {
          const svc = yield* ChatService
          yield* svc.sendMessage(text)
        })
      )
    },
    [runtime, busy]
  )

  const submitProfileData = useCallback(
    (callId: string, data: ProfileData) => {
      console.log('[useChat] submitProfileData called', { callId, data })
      patchLastBot((b) => clearProfileRequest(b))
      runtime.runFork(
        Effect.gen(function* () {
          const svc = yield* ChatService
          console.log('[useChat] sending profile_data_submitted over WS')
          yield* svc.submitProfileData(callId, data)
          console.log('[useChat] profile_data_submitted sent successfully')
        })
      )
    },
    [runtime, patchLastBot]
  )

  const clearMessages = useCallback(() => {
    // No `busy` guard (unlike incremento 1): "Nueva conversación" must work even while
    // busy=true, since it's the only recovery path when a collect_profile_data widget
    // was abandoned without submitting — busy never clears on its own in that case
    // (found via real Build and Test verification; see the profile_data_timeout_seconds
    // fix in ChatAgentClient for the backend side of this same bug).
    //
    // A full reload, not just resetting local state: the WS connection and the Foundry
    // thread it resumed live for the connection's whole lifetime (session is resolved
    // once, never re-resolved per message) — clearing only `messages` left the backend
    // chatting on the same old thread. Clearing the stored session id first ensures the
    // fresh connection after reload doesn't immediately resume it either.
    clearStoredSessionId()
    window.location.reload()
  }, [])

  // Switches to a past conversation picked from the Sidebar's real history list. Unlike
  // clearMessages, this keeps conversation_id (so the reload rehydrates its transcript)
  // but drops the stored service_session_id, since the browser only ever holds the MOST
  // RECENT one — the backend resolves the right Foundry thread via ConversationSessionStore
  // keyed on conversation_id instead (business-logic-model.md Section 13).
  const switchConversation = useCallback((conversationId: string) => {
    selectConversationInStorage(conversationId)
    window.location.reload()
  }, [])

  return { messages, busy, sendMessage, submitProfileData, clearMessages, switchConversation }
}
