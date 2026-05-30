import { Data } from "effect"

export class NetworkError extends Data.TaggedError("NetworkError")<{
  status: number
}> {}

export class ParseError extends Data.TaggedError("ParseError")<{
  cause: unknown
}> {}

export type ChatError = NetworkError | ParseError
