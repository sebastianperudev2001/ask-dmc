import { Effect, Layer, Stream } from "effect"
import { ChatService, type ChatEvent } from "./ChatService"
import { NetworkError, ParseError } from "@/types/errors"
import type { ConversationSummary, ProfileData } from "@/types/chat"

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/chat"
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

// RF-I05: persisted client-side so a page refresh can resume the same Foundry Memory
// conversation (business-logic-model.md Section 9, session_created).
const SESSION_STORAGE_KEY = "dmc-chat-service-session-id"
// Stable id (unlike service_session_id, which rotates every turn) used to fetch the
// persisted transcript for rehydration after a reload — added after Build and Test
// (user feedback: a reload showed a blank chat even though Foundry itself resumed).
const CONVERSATION_ID_STORAGE_KEY = "dmc-chat-conversation-id"

const getStoredSessionId = (): string | null =>
  typeof window === "undefined" ? null : window.localStorage.getItem(SESSION_STORAGE_KEY)

const storeSessionId = (serviceSessionId: string): void => {
  if (typeof window !== "undefined") window.localStorage.setItem(SESSION_STORAGE_KEY, serviceSessionId)
}

export const getStoredConversationId = (): string | null =>
  typeof window === "undefined" ? null : window.localStorage.getItem(CONVERSATION_ID_STORAGE_KEY)

const storeConversationId = (conversationId: string): void => {
  if (typeof window !== "undefined") window.localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, conversationId)
}

// Found via real Build and Test verification: "Nueva conversación" only cleared the
// frontend's message list — the WS connection (and Foundry thread) kept going, and any
// later message on a fresh page load would still resume the OLD conversation via this
// stored id. Exported so useChat's clearMessages can actually start a new one.
export const clearStoredSessionId = (): void => {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(SESSION_STORAGE_KEY)
    window.localStorage.removeItem(CONVERSATION_ID_STORAGE_KEY)
  }
}

export type PersistedMessage = { role: "user" | "bot"; content: string }

// Rehydration after a page reload — fetches the transcript persisted by the backend
// (conversation_messages, see migrations/003) since React state doesn't survive a
// reload on its own and Foundry's SDK has no history-retrieval API we could use instead.
export const fetchConversationHistory = async (conversationId: string): Promise<PersistedMessage[]> => {
  const response = await fetch(`${API_URL}/conversations/${conversationId}/messages`)
  if (!response.ok) return []
  return (await response.json()) as PersistedMessage[]
}

// Real conversation history list (replaces the hardcoded mock Sidebar data — added
// after user feedback: "el historial... no jala las sesiones creadas?").
export const fetchConversations = async (): Promise<ConversationSummary[]> => {
  const response = await fetch(`${API_URL}/conversations`)
  if (!response.ok) return []
  const raw = (await response.json()) as {
    conversation_id: string
    preview: string
    last_activity_at: string
  }[]
  return raw.map((c) => ({
    conversationId: c.conversation_id,
    preview: c.preview,
    lastActivityAt: c.last_activity_at,
  }))
}

// Switches the "current" conversation without a full "Nueva conversación" reset: keeps
// the conversation_id (so the reload after this can rehydrate it and the backend can
// resume its Foundry thread via ConversationSessionStore) but clears service_session_id
// — the browser only ever holds the MOST RECENT one, which would be wrong for an older
// conversation; the backend looks up the right one by conversation_id instead.
export const selectConversation = (conversationId: string): void => {
  if (typeof window === "undefined") return
  window.localStorage.removeItem(SESSION_STORAGE_KEY)
  window.localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, conversationId)
}

// Snake_case wire shape from agent-service (business-logic-model.md Section 9) —
// translated to the camelCase ChatEvent union at the boundary.
type ServerMessage = { type: string; [key: string]: unknown }

export const toChatEvent = (msg: ServerMessage): ChatEvent | null => {
  switch (msg.type) {
    case "recommendation_delta":
      return { _tag: "delta", text: msg.delta as string }
    case "profile_data_requested": {
      const prefill = msg.prefill as {
        budget: number | null
        max_duration_weeks: number | null
        professional_background: string | null
        desired_stack: string | null
      }
      return {
        _tag: "profileDataRequested",
        callId: msg.call_id as string,
        prefill: {
          budget: prefill.budget,
          maxDurationWeeks: prefill.max_duration_weeks,
          professionalBackground: prefill.professional_background,
          desiredStack: prefill.desired_stack,
        },
      }
    }
    case "recommendation_done": {
      const candidates = msg.candidates as { course_id: string; name: string; similarity_score: number }[]
      return {
        _tag: "recommendationsReady",
        candidates: candidates.map((c) => ({
          courseId: c.course_id,
          name: c.name,
          similarityScore: c.similarity_score,
        })),
      }
    }
    case "payment_link_created":
      return { _tag: "paymentLinkCreated", checkoutUrl: msg.checkout_url as string }
    case "turn_done":
      return { _tag: "turnDone" }
    case "session_created": {
      const serviceSessionId = msg.service_session_id as string
      storeSessionId(serviceSessionId)
      storeConversationId(msg.conversation_id as string)
      return { _tag: "sessionCreated", serviceSessionId }
    }
    default:
      // relax_filters_offer/no_exact_match_showing_all/no_recommendation now arrive as
      // part of the agent's own text (Clarification 4 = A) — not distinct UI events.
      return null
  }
}

export const WsChatServiceLive: Layer.Layer<ChatService, NetworkError> = Layer.effect(
  ChatService,
  Effect.gen(function* () {
    const ws = new WebSocket(WS_URL)

    // Block layer construction until the socket is actually open, so sendMessage/
    // submitProfileData (called right after `yield* ChatService`) never race a
    // CONNECTING socket.
    yield* Effect.async<void, NetworkError>((resume) => {
      ws.addEventListener("open", () => resume(Effect.void), { once: true })
      ws.addEventListener("error", () => resume(Effect.fail(new NetworkError({ status: 0 }))), { once: true })
    })

    const events: Stream.Stream<ChatEvent, NetworkError | ParseError> = Stream.asyncPush<
      ChatEvent,
      NetworkError | ParseError
    >((emit) =>
      Effect.acquireRelease(
        Effect.sync(() => {
          const onMessage = (event: MessageEvent) => {
            try {
              const parsed = JSON.parse(event.data) as ServerMessage
              const chatEvent = toChatEvent(parsed)
              if (chatEvent) emit.single(chatEvent)
            } catch (cause) {
              console.error("ParseError on message:", event.data, cause)
              emit.fail(new ParseError({ cause }))
            }
          }
          const onClose = () => emit.end()
          const onError = () => emit.fail(new NetworkError({ status: 0 }))

          ws.addEventListener("message", onMessage)
          ws.addEventListener("close", onClose)
          ws.addEventListener("error", onError)
          return { onMessage, onClose, onError }
        }),
        (handlers) =>
          Effect.sync(() => {
            ws.removeEventListener("message", handlers.onMessage)
            ws.removeEventListener("close", handlers.onClose)
            ws.removeEventListener("error", handlers.onError)
          })
      )
    )

    const send = (payload: Record<string, unknown>) => Effect.sync(() => ws.send(JSON.stringify(payload)))

    return {
      events,
      sendMessage: (text: string) => {
        const resumeSessionId = getStoredSessionId()
        const resumeConversationId = getStoredConversationId()
        return send({
          type: "user_message",
          text,
          ...(resumeSessionId ? { service_session_id: resumeSessionId } : {}),
          ...(resumeConversationId ? { conversation_id: resumeConversationId } : {}),
        })
      },
      submitProfileData: (callId: string, data: ProfileData) =>
        send({
          type: "profile_data_submitted",
          call_id: callId,
          budget: data.budget,
          max_duration_weeks: data.maxDurationWeeks,
          professional_background: data.professionalBackground,
          desired_stack: data.desiredStack,
        }),
    }
  })
)
