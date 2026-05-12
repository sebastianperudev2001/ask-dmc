import { NextRequest } from 'next/server'

export const POST = async (req: NextRequest): Promise<Response> => {
  const body = await req.json()

  const upstream = await fetch(`${process.env.API_URL}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!upstream.ok) {
    return new Response(JSON.stringify({ error: 'Upstream error' }), {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const xSources = upstream.headers.get('x-sources')

  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      ...(xSources ? { 'X-Sources': xSources } : {}),
    },
  })
}
