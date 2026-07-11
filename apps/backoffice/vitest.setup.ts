/**
 * Vitest global setup: unwrap Effect FiberFailure errors so that
 * `expect(...).rejects.toMatchObject({ _tag: "...", ... })` works with
 * Data.TaggedError instances propagated through Effect.runPromise.
 *
 * Same setup as apps/chat/vitest.setup.ts — Effect.runPromise wraps typed errors in a
 * FiberFailure object; this registers a custom equality tester that squashes the cause
 * and compares the underlying error instead, using subset matching.
 */
import { Cause } from "effect"
import { isFiberFailure, FiberFailureCauseId } from "effect/Runtime"
import { expect } from "vitest"
import { subsetEquality, iterableEquality } from "@vitest/expect"

expect.addEqualityTesters([
  function fiberFailureUnwrapper(received, expected, customTesters): boolean | undefined {
    if (
      received !== null &&
      typeof received === "object" &&
      isFiberFailure(received) &&
      expected !== null &&
      typeof expected === "object" &&
      !isFiberFailure(expected)
    ) {
      const cause = (received as any)[FiberFailureCauseId]
      const squashed = Cause.squash(cause)
      return subsetEquality(squashed, expected, [
        ...customTesters,
        iterableEquality,
      ])
    }
    return undefined
  },
])
