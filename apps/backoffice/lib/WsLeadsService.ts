import { Effect, Layer, Stream } from "effect"
import { LeadsService, type LeadWireEvent } from "./LeadsService"
import { NetworkError, ParseError } from "@/types/errors"
import type { LeadOut } from "@/types/leads"

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/leads"

// Snake_case wire shape from agent-service (src/api/schemas.py::LeadOut) — translated
// to the camelCase LeadOut at the boundary, same convention as apps/chat's toChatEvent.
type RawLead = {
  id: string
  created_at: string
  name: string | null
  email: string | null
  profile_summary: string
  motivation: string
  motivation_detail: string
  recommended_programs: string[]
  payment_link_sent: boolean
  payment_confirmed: boolean
  payment_confirmed_at: string | null
  score: "hot" | "warm" | "cold"
  score_justification: string
}

const toLeadOut = (raw: RawLead): LeadOut => ({
  id: raw.id,
  createdAt: raw.created_at,
  name: raw.name,
  email: raw.email,
  profileSummary: raw.profile_summary,
  motivation: raw.motivation,
  motivationDetail: raw.motivation_detail,
  recommendedPrograms: raw.recommended_programs,
  paymentLinkSent: raw.payment_link_sent,
  paymentConfirmed: raw.payment_confirmed,
  paymentConfirmedAt: raw.payment_confirmed_at,
  score: raw.score,
  scoreJustification: raw.score_justification,
})

type ServerMessage = { type: string; [key: string]: unknown }

export const toLeadWireEvent = (msg: ServerMessage): LeadWireEvent | null => {
  switch (msg.type) {
    case "snapshot": {
      const leads = msg.leads as RawLead[]
      return { _tag: "snapshot", leads: leads.map(toLeadOut) }
    }
    case "lead_event": {
      const eventType = msg.event_type as "created" | "score_changed" | "motivation_set"
      return { _tag: "leadEvent", eventType, lead: toLeadOut(msg.lead as RawLead) }
    }
    default:
      return null
  }
}

export const WsLeadsServiceLive: Layer.Layer<LeadsService, NetworkError> = Layer.effect(
  LeadsService,
  Effect.gen(function* () {
    const ws = new WebSocket(WS_URL)

    yield* Effect.async<void, NetworkError>((resume) => {
      ws.addEventListener("open", () => resume(Effect.void), { once: true })
      ws.addEventListener("error", () => resume(Effect.fail(new NetworkError({ status: 0 }))), { once: true })
    })

    const events: Stream.Stream<LeadWireEvent, NetworkError | ParseError> = Stream.asyncPush<
      LeadWireEvent,
      NetworkError | ParseError
    >((emit) =>
      Effect.acquireRelease(
        Effect.sync(() => {
          const onMessage = (event: MessageEvent) => {
            try {
              const parsed = JSON.parse(event.data) as ServerMessage
              const wireEvent = toLeadWireEvent(parsed)
              if (wireEvent) emit.single(wireEvent)
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

    return { events }
  })
)
