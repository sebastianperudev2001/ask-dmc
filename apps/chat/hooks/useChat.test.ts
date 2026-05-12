import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock streamAsk before importing useChat
vi.mock('@/lib/api', () => ({
  streamAsk: vi.fn(),
}))

import { streamAsk } from '@/lib/api'
import { buildUserMsg, initialBotMsg, applyChunk, applyDone } from './useChat'
import type { Source } from '@/types/chat'

describe('buildUserMsg', () => {
  it('creates a user message with the given text', () => {
    const msg = buildUserMsg('hola')
    expect(msg.role).toBe('user')
    expect(msg.text).toBe('hola')
    expect(msg.id).toBeTruthy()
  })
})

describe('buildBotMsg / initialBotMsg', () => {
  it('creates a bot message in searching phase', () => {
    const msg = initialBotMsg('pregunta')
    expect(msg.role).toBe('bot')
    expect(msg.phase).toBe('searching')
    expect(msg.question).toBe('pregunta')
    expect(msg.answer).toBe('')
    expect(msg.answerDone).toBe(false)
    expect(msg.sources).toEqual([])
    expect(msg.id).toBeTruthy()            // UUID, not the question text
  })
})

describe('applyChunk', () => {
  it('appends chunk to answer and sets phase to streaming', () => {
    const msg = initialBotMsg('q')
    const updated = applyChunk(msg, 'Hola')
    expect(updated.answer).toBe('Hola')
    expect(updated.phase).toBe('streaming')
  })

  it('accumulates chunks', () => {
    const msg = initialBotMsg('q')
    const updated = applyChunk(applyChunk(msg, 'Hola'), ' mundo')
    expect(updated.answer).toBe('Hola mundo')
  })
})

describe('applyDone', () => {
  it('sets answerDone=true, phase=done, and attaches sources', () => {
    const msg = initialBotMsg('q')
    const sources: Source[] = [{ course: 'Power BI', section: 'precios', distance: 0.1 }]
    const updated = applyDone(msg, sources)
    expect(updated.answerDone).toBe(true)
    expect(updated.phase).toBe('done')
    expect(updated.sources).toEqual(sources)
  })
})
