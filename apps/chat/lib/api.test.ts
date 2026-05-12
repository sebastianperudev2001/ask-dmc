import { describe, it, expect, vi, beforeEach } from 'vitest'
import { streamAsk } from './api'
import type { Source } from '@/types/chat'

const encoder = new TextEncoder()

const makeStream = (chunks: string[]) => {
  let i = 0
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]))
      } else {
        controller.close()
      }
    },
  })
}

const makeFetch = (chunks: string[], xSources: Source[] = []) =>
  vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: {
      get: (h: string) =>
        h.toLowerCase() === 'x-sources' ? JSON.stringify(xSources) : null,
    },
    body: makeStream(chunks),
  } as unknown as Response)

beforeEach(() => {
  vi.stubGlobal('fetch', makeFetch(['Hola', ' mundo']))
})

describe('streamAsk', () => {
  it('yields text chunks from the stream', async () => {
    const chunks: string[] = []
    const sources: Source[] = []

    for await (const chunk of streamAsk('test question', (s) => sources.push(...s))) {
      chunks.push(chunk)
    }

    expect(chunks.join('')).toContain('Hola')
  })

  it('calls onSources with parsed X-Sources after stream ends', async () => {
    const xSources: Source[] = [{ course: 'Power BI', section: 'precios', distance: 0.12 }]
    vi.stubGlobal('fetch', makeFetch(['respuesta'], xSources))

    const received: Source[] = []
    for await (const _ of streamAsk('pregunta', (s) => received.push(...s))) { /* consume */ }

    expect(received).toEqual(xSources)
  })

  it('calls /api/ask with POST and question body', async () => {
    const mockFetch = makeFetch(['ok'])
    vi.stubGlobal('fetch', mockFetch)

    for await (const _ of streamAsk('¿cuánto cuesta?', () => {})) { /* consume */ }

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/ask',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ question: '¿cuánto cuesta?' }),
      })
    )
  })

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    const gen = streamAsk('q', () => {})
    await expect(gen.next()).rejects.toThrow('API error: 500')
  })
})
