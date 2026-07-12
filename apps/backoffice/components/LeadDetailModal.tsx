import type { LeadOut } from '@/types/leads'
import DraftPanel from './DraftPanel'

// ── Pure (exported for testing) ─────────────────────────────────────────────
export const motivationLabel = (motivation: string): string => {
  const labels: Record<string, string> = {
    growth: 'Crecimiento profesional',
    salary: 'Aumento salarial',
    company_requirement: 'Requisito de la empresa',
    academic: 'Fines académicos',
    undefined: 'Sin definir aún',
  }
  return labels[motivation] ?? motivation
}

type LeadDetailModalProps = {
  lead: LeadOut | null
  onClose: () => void
}

// FR-4/FR-5: read-only — no input bound to any Lead field anywhere in this component.
// No conversation transcript rendered (LeadOut doesn't carry one — unreachable by
// construction, not just by convention).
const LeadDetailModal = ({ lead, onClose }: LeadDetailModalProps) => {
  if (!lead) return null

  return (
    <div
      data-testid="lead-detail-modal-backdrop"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
      }}
    >
      <div
        data-testid="lead-detail-modal"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 10,
          boxShadow: 'var(--shadow-lg)',
          width: 520,
          maxWidth: '90vw',
          maxHeight: '85vh',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '18px 22px',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 17 }}>
            {lead.name ?? 'Sin nombre'}
          </h2>
          <button
            type="button"
            data-testid="lead-detail-modal-close"
            onClick={onClose}
            style={{ background: 'none', border: 'none', fontSize: 16, color: 'var(--color-text-muted)' }}
          >
            ✕
          </button>
        </div>

        <div style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          <dl style={{ display: 'grid', gridTemplateColumns: '128px 1fr', rowGap: 9, fontSize: 13 }}>
            <dt style={{ color: 'var(--color-text-muted)' }}>Email</dt>
            <dd style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 12.5 }}>{lead.email ?? '—'}</dd>

            <dt style={{ color: 'var(--color-text-muted)' }}>Creado</dt>
            <dd style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 12.5 }}>
              {new Date(lead.createdAt).toLocaleString('es-PE')}
            </dd>

            <dt style={{ color: 'var(--color-text-muted)' }}>Score</dt>
            <dd style={{ margin: 0 }}>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  padding: '2px 8px',
                  borderRadius: 4,
                  color: `var(--color-${lead.score})`,
                  background: `var(--color-${lead.score}-bg)`,
                }}
              >
                {lead.score}
              </span>
            </dd>

            <dt style={{ color: 'var(--color-text-muted)' }}>Justificación</dt>
            <dd style={{ margin: 0 }}>{lead.scoreJustification || '—'}</dd>

            <dt style={{ color: 'var(--color-text-muted)' }}>Perfil</dt>
            <dd style={{ margin: 0 }}>{lead.profileSummary || '—'}</dd>

            <dt style={{ color: 'var(--color-text-muted)' }}>Motivación</dt>
            <dd style={{ margin: 0 }}>
              {motivationLabel(lead.motivation)}
              {lead.motivationDetail ? ` — ${lead.motivationDetail}` : ''}
            </dd>

            <dt style={{ color: 'var(--color-text-muted)' }}>Programas</dt>
            <dd style={{ margin: 0 }}>{lead.recommendedPrograms.join(', ') || '—'}</dd>

            <dt style={{ color: 'var(--color-text-muted)' }}>Pago</dt>
            <dd style={{ margin: 0 }}>
              {lead.paymentConfirmed
                ? `Confirmado (${lead.paymentConfirmedAt ? new Date(lead.paymentConfirmedAt).toLocaleString('es-PE') : ''})`
                : lead.paymentLinkSent
                  ? 'Link enviado, sin confirmar'
                  : 'Sin acción de pago'}
            </dd>
          </dl>

          <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 16 }}>
            <div
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 12,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                color: 'var(--color-text-muted)',
                marginBottom: 10,
              }}
            >
              Outreach
            </div>
            <DraftPanel leadId={lead.id} leadEmail={lead.email} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default LeadDetailModal
