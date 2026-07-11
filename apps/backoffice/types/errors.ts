import { Data } from "effect"

// Same shape as apps/chat/types/errors.ts
export class NetworkError extends Data.TaggedError("NetworkError")<{
  status: number
}> {}

export class ParseError extends Data.TaggedError("ParseError")<{
  cause: unknown
}> {}

export type LeadsError = NetworkError | ParseError
