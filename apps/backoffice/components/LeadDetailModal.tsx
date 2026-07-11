import type { LeadOut } from '@/types/leads'
import DraftPanel from './DraftPanel'

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
          borderRadius: 12,
          padding: 24,
          width: 480,
          maxWidth: '90vw',
          maxHeight: '85vh',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>{lead.name ?? 'Sin nombre'}</h2>
          <button type="button" data-testid="lead-detail-modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <dl style={{ display: 'grid', gridTemplateColumns: '140px 1fr', rowGap: 6, fontSize: 13 }}>
          <dt style={{ color: 'var(--color-text-muted)' }}>Email</dt>
          <dd style={{ margin: 0 }}>{lead.email ?? '—'}</dd>

          <dt style={{ color: 'var(--color-text-muted)' }}>Creado</dt>
          <dd style={{ margin: 0 }}>{new Date(lead.createdAt).toLocaleString('es-PE')}</dd>

          <dt style={{ color: 'var(--color-text-muted)' }}>Score</dt>
          <dd style={{ margin: 0, textTransform: 'uppercase' }}>{lead.score}</dd>

          <dt style={{ color: 'var(--color-text-muted)' }}>Justificación</dt>
          <dd style={{ margin: 0 }}>{lead.scoreJustification || '—'}</dd>

          <dt style={{ color: 'var(--color-text-muted)' }}>Perfil</dt>
          <dd style={{ margin: 0 }}>{lead.profileSummary || '—'}</dd>

          <dt style={{ color: 'var(--color-text-muted)' }}>Motivación</dt>
          <dd style={{ margin: 0 }}>
            {lead.motivation}
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

        <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '4px 0' }} />

        <DraftPanel leadId={lead.id} leadEmail={lead.email} />
      </div>
    </div>
  )
}

export default LeadDetailModal
