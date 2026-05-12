import type { Source } from '@/types/chat'

export async function* streamAsk(
  question: string,
  onSources: (sources: Source[]) => void,
): AsyncGenerator<string> {
  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  const xSourcesRaw = response.headers.get('x-sources')

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      yield decoder.decode(value, { stream: true })
    }
  } finally {
    reader.releaseLock()
  }

  if (xSourcesRaw) {
    try {
      onSources(JSON.parse(xSourcesRaw) as Source[])
    } catch {
      // malformed header — ignore
    }
  }
}
