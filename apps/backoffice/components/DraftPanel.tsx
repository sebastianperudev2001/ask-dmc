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
      <div data-testid="draft-panel-loading" style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>
        Cargando…
      </div>
    )
  }

  return (
    <div data-testid="draft-panel" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {error && <div style={{ color: '#b3261e', fontSize: 12.5 }}>{error}</div>}

      {!draft && (
        <button type="button" data-testid="draft-panel-generate" onClick={generateDraft}>
          Generar draft
        </button>
      )}

      {draft && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>{draft.subject}</div>
          <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: 'var(--color-text)' }}>{draft.body}</div>
          <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
            {draft.status}
          </div>

          {draft.status === 'pending' && (
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                data-testid="draft-panel-send"
                onClick={sendDraft}
                disabled={sending || !leadEmail}
              >
                {sending ? 'Enviando…' : 'Send'}
              </button>
              <button type="button" data-testid="draft-panel-discard" onClick={discardDraft}>
                Discard
              </button>
            </div>
          )}
          {!leadEmail && draft.status === 'pending' && (
            <div style={{ fontSize: 11.5, color: '#b3261e' }}>
              Este lead no tiene email — no se puede enviar.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DraftPanel
