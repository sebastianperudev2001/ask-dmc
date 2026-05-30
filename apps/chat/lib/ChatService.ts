import { Context, Stream } from "effect"
import type { ChatError } from "@/types/errors"
import type { Source } from "@/types/chat"

export type ChatChunk =
  | { _tag: "text"; chunk: string }
  | { _tag: "sources"; sources: Source[] }

export class ChatService extends Context.Tag("ChatService")<
  ChatService,
  {
    readonly stream: (question: string) => Stream.Stream<ChatChunk, ChatError>
  }
>() {}
