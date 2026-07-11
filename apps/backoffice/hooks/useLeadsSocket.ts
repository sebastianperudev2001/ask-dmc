'use client'
import { useState, useCallback, useEffect } from 'react'
import { Effect, Fiber, Stream } from 'effect'
import type { LeadOut, Notification } from '@/types/leads'
import { LeadsService, type LeadWireEvent } from '@/lib/LeadsService'
import { useLeadsRuntime } from '@/lib/LeadsRuntimeProvider'

// ── Pure state helpers (exported for testing — same convention as apps/chat's
// applyDelta/messagesFromHistory in hooks/useChat.ts) ──────────────────────────

// Story 3 AC: a `snapshot` fully replaces state (reconnect reconciliation — no
// merge/diff, no stale/duplicate cards possible by construction). A `leadEvent`
// upserts a single entry by id.
export const applyLeadWireEvent = (
  state: Record<string, LeadOut>,
  event: LeadWireEvent
): Record<string, LeadOut> => {
  if (event._tag === 'snapshot') {
    return Object.fromEntries(event.leads.map((lead) => [lead.id, lead]))
  }
  return { ...state, [event.lead.id]: event.lead }
}

// FR-14/Story 7 — "actionable" = score reaches hot, same trigger as the backend's
// auto-draft (BR-24). This is the one place that assumption lives in code.
export const deriveNotification = (event: LeadWireEvent): Notification | null => {
  if (event._tag !== 'leadEvent') return null
  if (event.eventType !== 'score_changed') return null
  if (event.lead.score !== 'hot') return null
  return {
    id: `${event.lead.id}-${Date.now()}`,
    leadId: event.lead.id,
    leadName: event.lead.name,
    createdAt: Date.now(),
  }
}

// ── Hook ─────────────────────────────────────────────────────────────────────

type UseLeadsSocketReturn = {
  leads: LeadOut[]
  notifications: Notification[]
  dismissNotification: (id: string) => void
  connectionStatus: 'connecting' | 'open' | 'closed'
}

export const useLeadsSocket = (): UseLeadsSocketReturn => {
  const runtime = useLeadsRuntime()
  const [leadsState, setLeadsState] = useState<Record<string, LeadOut>>({})
  // Q2 = A (Functional Design): in-memory only, reset on a full page reload — no
  // localStorage/persistence layer.
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'open' | 'closed'>('connecting')

  // Subscribe once to the persistent WS event stream for the whole component
  // lifetime — same shape as useChat's WS-subscription effect.
  useEffect(() => {
    const fiber = runtime.runFork(
      Effect.gen(function* () {
        const svc = yield* LeadsService
        setConnectionStatus('open')
        yield* svc.events.pipe(
          Stream.tap((event) =>
            Effect.sync(() => {
              setLeadsState((prev) => applyLeadWireEvent(prev, event))
              const notification = deriveNotification(event)
              if (notification) setNotifications((prev) => [...prev, notification])
            })
          ),
          Stream.catchAll((err) =>
            Stream.fromEffect(
              Effect.sync(() => {
                console.error('Leads WS error:', err)
                setConnectionStatus('closed')
              })
            )
          ),
          Stream.runDrain
        )
        setConnectionStatus('closed')
      })
    )
    return () => {
      runtime.runFork(Fiber.interrupt(fiber))
    }
  }, [runtime])

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
  }, [])

  return {
    leads: Object.values(leadsState),
    notifications,
    dismissNotification,
    connectionStatus,
  }
}
