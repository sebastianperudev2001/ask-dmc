import { describe, it, expect } from "vitest"
import {
  buildUserMsg,
  initialBotMsg,
  applyDelta,
  applyRecommendations,
  applyProfileRequest,
  clearProfileRequest,
  applyPaymentLink,
  markTurnDone,
  messagesFromHistory,
  extractPaymentLink,
} from "./useChat"
import type { CourseRecommendation, ProfileDataPrefill } from "@/types/chat"
import type { PersistedMessage } from "@/lib/WsChatService"

describe("buildUserMsg", () => {
  it("creates a user message with the given text", () => {
    const msg = buildUserMsg("hola")
    expect(msg.role).toBe("user")
    expect(msg.text).toBe("hola")
    expect(msg.id).toBeTruthy()
  })
})

describe("initialBotMsg", () => {
  it("creates a bot message in streaming phase with empty state", () => {
    const msg = initialBotMsg()
    expect(msg.role).toBe("bot")
    expect(msg.phase).toBe("streaming")
    expect(msg.answer).toBe("")
    expect(msg.answerDone).toBe(false)
    expect(msg.recommendations).toEqual([])
    expect(msg.toolCalls).toEqual([])
    expect(msg.profileRequest).toBeNull()
    expect(msg.id).toBeTruthy()
  })
})

describe("applyDelta", () => {
  it("appends text to answer", () => {
    const msg = initialBotMsg()
    const updated = applyDelta(msg, "Hola")
    expect(updated.answer).toBe("Hola")
  })

  it("accumulates deltas", () => {
    const msg = initialBotMsg()
    const updated = applyDelta(applyDelta(msg, "Hola"), " mundo")
    expect(updated.answer).toBe("Hola mundo")
  })
})

describe("applyRecommendations", () => {
  it("sets the recommendations list", () => {
    const candidates: CourseRecommendation[] = [
      { courseId: "diploma-data-analyst", name: "Diploma en Data Analyst", similarityScore: 0.87 },
    ]
    const updated = applyRecommendations(initialBotMsg(), candidates)
    expect(updated.recommendations).toEqual(candidates)
  })
})

describe("applyProfileRequest / clearProfileRequest", () => {
  it("sets phase to awaitingProfileData with the prefill", () => {
    const prefill: ProfileDataPrefill = {
      budget: 500,
      maxDurationWeeks: 8,
      professionalBackground: "analista",
      desiredStack: "azure",
    }
    const updated = applyProfileRequest(initialBotMsg(), "call_1", prefill)
    expect(updated.phase).toBe("awaitingProfileData")
    expect(updated.profileRequest).toEqual({ callId: "call_1", prefill })
  })

  it("clearing returns phase to streaming and nulls profileRequest", () => {
    const prefill: ProfileDataPrefill = {
      budget: null,
      maxDurationWeeks: null,
      professionalBackground: null,
      desiredStack: null,
    }
    const requested = applyProfileRequest(initialBotMsg(), "call_1", prefill)
    const cleared = clearProfileRequest(requested)
    expect(cleared.phase).toBe("streaming")
    expect(cleared.profileRequest).toBeNull()
  })
})

describe("applyPaymentLink", () => {
  it("appends a done create_payment_link tool call with the checkout url as result", () => {
    const updated = applyPaymentLink(initialBotMsg(), "https://www.mercadopago.com/checkout/abc")
    expect(updated.toolCalls).toEqual([
      {
        name: "create_payment_link",
        argsText: "",
        resultText: "https://www.mercadopago.com/checkout/abc",
        status: "done",
      },
    ])
  })
})

describe("markTurnDone", () => {
  it("sets answerDone=true and phase=done", () => {
    const updated = markTurnDone(applyDelta(initialBotMsg(), "respuesta"))
    expect(updated.answerDone).toBe(true)
    expect(updated.phase).toBe("done")
  })
})

describe("messagesFromHistory", () => {
  it("reconstructs alternating user/bot messages from the persisted transcript", () => {
    const history: PersistedMessage[] = [
      { role: "user", content: "hola" },
      { role: "bot", content: "hola, en que te ayudo?" },
    ]
    const messages = messagesFromHistory(history)

    expect(messages).toHaveLength(2)
    expect(messages[0]).toMatchObject({ role: "user", text: "hola" })
    expect(messages[1]).toMatchObject({
      role: "bot",
      answer: "hola, en que te ayudo?",
      answerDone: true,
      phase: "done",
    })
  })

  it("returns an empty array for an empty history", () => {
    expect(messagesFromHistory([])).toEqual([])
  })

  it("reconstructs a create_payment_link tool call when the bot text contains a checkout URL", () => {
    const history: PersistedMessage[] = [
      { role: "user", content: "quiero comprarlo" },
      {
        role: "bot",
        content:
          "Listo, aqui tienes el link de pago: https://sandbox.mercadopago.com.pe/checkout/v1/redirect?pref_id=abc-123",
      },
    ]
    const messages = messagesFromHistory(history)

    expect(messages[1]).toMatchObject({
      role: "bot",
      toolCalls: [
        {
          name: "create_payment_link",
          argsText: "",
          resultText: "https://sandbox.mercadopago.com.pe/checkout/v1/redirect?pref_id=abc-123",
          status: "done",
        },
      ],
    })
  })
})

describe("extractPaymentLink", () => {
  it("finds a sandbox Mercado Pago checkout URL inside free text", () => {
    const text = "Aqui tienes tu link: https://sandbox.mercadopago.com.pe/checkout/v1/redirect?pref_id=abc-123 saludos"
    expect(extractPaymentLink(text)).toBe(
      "https://sandbox.mercadopago.com.pe/checkout/v1/redirect?pref_id=abc-123"
    )
  })

  it("finds a production Mercado Pago checkout URL without the sandbox prefix", () => {
    const text = "link: https://www.mercadopago.com/checkout/v1/redirect?pref_id=xyz"
    expect(extractPaymentLink(text)).toBe("https://www.mercadopago.com/checkout/v1/redirect?pref_id=xyz")
  })

  it("returns null when there is no checkout URL", () => {
    expect(extractPaymentLink("hola, en que te ayudo?")).toBeNull()
  })
})
