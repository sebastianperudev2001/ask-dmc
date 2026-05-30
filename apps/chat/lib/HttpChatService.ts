import { Effect, Layer, Option, Stream } from "effect"
import { Headers, HttpClient, HttpClientRequest, FetchHttpClient } from "@effect/platform"
import { ChatService, type ChatChunk } from "./ChatService"
import { NetworkError, ParseError } from "@/types/errors"
import type { Source } from "@/types/chat"

const decoder = new TextDecoder()

// Requires HttpClient from context — testable by providing a mock HttpClient layer.
export const HttpChatServiceLive: Layer.Layer<ChatService, never, HttpClient.HttpClient> =
  Layer.effect(
    ChatService,
    Effect.gen(function* () {
      const client = yield* HttpClient.HttpClient

      return {
        stream: (question: string) => {
          const program = Effect.gen(function* () {
            const request = HttpClientRequest.post("/api/ask").pipe(
              HttpClientRequest.bodyUnsafeJson({ question })
            )

            const response = yield* client.execute(request)

            if (response.status < 200 || response.status >= 300) {
              return yield* Effect.fail(new NetworkError({ status: response.status }))
            }

            const xSourcesRaw: string | undefined = Option.getOrUndefined(
              Headers.get(response.headers, "x-sources")
            )

            // Decode Uint8Array chunks to strings.
            // response.stream has error type ResponseError, but we've already validated
            // the status above, so we map it into ParseError to match ChatError.
            const textStream: Stream.Stream<ChatChunk, ParseError> = response.stream.pipe(
              Stream.map((chunk) => ({
                _tag: "text" as const,
                chunk: decoder.decode(chunk, { stream: true }),
              })),
              Stream.mapError((e) => new ParseError({ cause: e }))
            )

            const sourcesStream: Stream.Stream<ChatChunk, ParseError> = xSourcesRaw
              ? Stream.fromEffect(
                  Effect.try({
                    try: () => JSON.parse(xSourcesRaw) as Source[],
                    catch: (e) => new ParseError({ cause: e }),
                  }).pipe(
                    Effect.map((sources): ChatChunk => ({ _tag: "sources", sources }))
                  )
                )
              : Stream.empty

            return Stream.concat(
              textStream,
              sourcesStream
            ) as Stream.Stream<ChatChunk, ParseError>
          })

          // Stream.unwrap handles the Effect → Stream conversion
          return Stream.unwrap(
            program as Effect.Effect<
              Stream.Stream<ChatChunk, NetworkError | ParseError>,
              NetworkError | ParseError,
              never
            >
          )
        },
      }
    })
  )

// Self-contained for production: wires in the browser's fetch-based HttpClient.
export const HttpChatService: Layer.Layer<ChatService> = Layer.provide(
  HttpChatServiceLive,
  FetchHttpClient.layer
)
