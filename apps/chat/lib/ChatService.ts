import { Context, Effect, Stream } from "effect"
import type { ChatError } from "@/types/errors"
import type { CourseRecommendation, ProfileData, ProfileDataPrefill } from "@/types/chat"

// Incremento 2 — RF-I01: el transporte pasa de HTTP-una-pregunta a un WebSocket
// persistente de chat libre con tool-calling (business-logic-model.md Sección 9).
// A diferencia de `stream(question)` (incremento 1), la conexión vive durante toda la
// sesión: `events` es un stream continuo compartido, `sendMessage`/`submitProfileData`
// son efectos que escriben al mismo socket.
export type ChatEvent =
  | { _tag: "delta"; text: string }
  | { _tag: "profileDataRequested"; callId: string; prefill: ProfileDataPrefill }
  | { _tag: "recommendationsReady"; candidates: CourseRecommendation[] }
  | { _tag: "paymentLinkCreated"; checkoutUrl: string }
  | { _tag: "turnDone" }
  | { _tag: "sessionCreated"; serviceSessionId: string }

export class ChatService extends Context.Tag("ChatService")<
  ChatService,
  {
    readonly events: Stream.Stream<ChatEvent, ChatError>
    readonly sendMessage: (text: string) => Effect.Effect<void>
    readonly submitProfileData: (callId: string, data: ProfileData) => Effect.Effect<void>
  }
>() {}
