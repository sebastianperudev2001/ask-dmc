/**
 * Vitest global setup: unwrap Effect FiberFailure errors so that
 * `expect(...).rejects.toMatchObject({ _tag: "...", ... })` works with
 * Data.TaggedError instances propagated through Effect.runPromise.
 *
 * Effect.runPromise wraps typed errors in a FiberFailure object. We register a
 * custom equality tester that, when comparing a FiberFailure against a plain
 * object, squashes the cause and compares the underlying error instead —
 * using subset matching so extra properties on the error are ignored.
 */
import { Cause } from "effect"
import { isFiberFailure, FiberFailureCauseId } from "effect/Runtime"
import { expect } from "vitest"
import { subsetEquality, iterableEquality } from "@vitest/expect"

expect.addEqualityTesters([
  function fiberFailureUnwrapper(received, expected, customTesters): boolean | undefined {
    // Only intercept when received is a FiberFailure and expected is a plain object
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
      // Use subset equality: squashed must contain all keys from expected
      return subsetEquality(squashed, expected, [
        ...customTesters,
        iterableEquality,
      ])
    }
    return undefined
  },
])
