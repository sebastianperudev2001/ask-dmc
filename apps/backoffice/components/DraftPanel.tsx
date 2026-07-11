'use client'
import { useEffect, useState, useCallback } from 'react'
import type { OutreachDraftOut } from '@/types/leads'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// Snake_case wire shape from agent-service (src/api/schemas.py::OutreachDraftOut) —
// translated to camelCase here, same boundary convention as WsLeadsService.ts (Effect
// is confined to the WS layer only — this is plain fetch, matching apps/chat's
// fetchConversationHistory/fetchConversations precedent).
type RawDraft = {
  draft_id: string
  lead_id: string
  subject: string
  body: string
  status: 'pending' | 'sent' | 'discarded'
  trigger: 'auto' | 'on_demand'
  created_at: string
  sent_at: string | null
}

const toDraftOut = (raw: RawDraft): OutreachDraftOut => ({
  draftId: raw.draft_id,
  leadId: raw.lead_id,
  subject: raw.subject,
  body: raw.body,
  status: raw.status,
  trigger: raw.trigger,
  createdAt: raw.created_at,
  sentAt: raw.sent_at,
})

type DraftPanelProps = {
  leadId: string
  leadEmail: string | null
}

const DraftPanel = ({ leadId, leadEmail }: DraftPanelProps) => {
  const [draft, setDraft] = useState<OutreachDraftOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`${API_URL}/leads/${leadId}/drafts/active`)
      .then((res) => (res.ok ? res.json() : null))
      .then((raw: RawDraft | null) => setDraft(raw ? toDraftOut(raw) : null))
      .catch(() => setError('No se pudo cargar el draft.'))
      .finally(() => setLoading(false))
  }, [leadId])

  const generateDraft = useCallback(() => {
    setLoading(true)
    setError(null)
    fetch(`${API_URL}/leads/${leadId}/drafts`, { method: 'POST' })
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((raw: RawDraft) => setDraft(toDraftOut(raw)))
      .catch(() => setError('No se pudo generar el draft.'))
      .finally(() => setLoading(false))
  }, [leadId])

  // sending=true disables the Send button — the frontend half of the two-layer send
  // guard (NFR Requirements Sección 16); the backend's atomic mark_sent (PATTERN-28) is
  // the correctness backstop.
  const sendDraft = useCallback(() => {
    if (!draft) return
    setSending(true)
    setError(null)
    fetch(`${API_URL}/drafts/${draft.draftId}/send`, { method: 'POST' })
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((raw: RawDraft) => setDraft(toDraftOut(raw)))
      .catch(() => setError('No se pudo enviar el email.'))
      .finally(() => setSending(false))
  }, [draft])

  const discardDraft = useCallback(() => {
    if (!draft) return
    setLoading(true)
    fetch(`${API_URL}/drafts/${draft.draftId}/discard`, { method: 'POST' })
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((raw: RawDraft) => setDraft(toDraftOut(raw)))
      .catch(() => setError('No se pudo descartar el draft.'))
      .finally(() => setLoading(false))
  }, [draft])

  if (loading) {
    return (
      <div
        data-testid="draft-panel-loading"
        style={{ color: 'var(--color-text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' }}
      >
        Cargando…
      </div>
    )
  }

  const statusColor: Record<string, string> = {
    pending: 'var(--color-warm)',
    sent: 'var(--color-success)',
    discarded: 'var(--color-text-faint)',
  }
  const statusBg: Record<string, string> = {
    pending: 'var(--color-warm-bg)',
    sent: 'color-mix(in oklab, var(--color-success) 16%, transparent)',
    discarded: 'var(--color-surface-2)',
  }

  const primaryButtonStyle = {
    background: 'var(--color-accent)',
    color: '#ffffff',
    border: 'none',
    borderRadius: 6,
    padding: '7px 14px',
    fontSize: 13,
    fontWeight: 500,
  }
  const secondaryButtonStyle = {
    background: 'transparent',
    color: 'var(--color-text-muted)',
    border: '1px solid var(--color-border-strong)',
    borderRadius: 6,
    padding: '7px 14px',
    fontSize: 13,
  }

  return (
    <div data-testid="draft-panel" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {error && <div style={{ color: 'var(--color-danger)', fontSize: 12.5 }}>{error}</div>}

      {!draft && (
        <button type="button" data-testid="draft-panel-generate" onClick={generateDraft} style={primaryButtonStyle}>
          Generar draft
        </button>
      )}

      {draft && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            padding: 14,
            borderRadius: 8,
            border: '1px solid var(--color-border)',
            background: 'var(--color-surface-2)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
            <div style={{ fontWeight: 600, fontSize: 13.5 }}>{draft.subject}</div>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10.5,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                padding: '2px 8px',
                borderRadius: 4,
                flexShrink: 0,
                color: statusColor[draft.status],
                background: statusBg[draft.status],
              }}
            >
              {draft.status}
            </span>
          </div>
          <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.55, color: 'var(--color-text)' }}>
            {draft.body}
          </div>

          {draft.status === 'pending' && (
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <button
                type="button"
                data-testid="draft-panel-send"
                onClick={sendDraft}
                disabled={sending || !leadEmail}
                style={primaryButtonStyle}
              >
                {sending ? 'Enviando…' : 'Send'}
              </button>
              <button
                type="button"
                data-testid="draft-panel-discard"
                onClick={discardDraft}
                style={secondaryButtonStyle}
              >
                Discard
              </button>
            </div>
          )}
          {!leadEmail && draft.status === 'pending' && (
            <div style={{ fontSize: 11.5, color: 'var(--color-danger)' }}>
              Este lead no tiene email — no se puede enviar.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DraftPanel
