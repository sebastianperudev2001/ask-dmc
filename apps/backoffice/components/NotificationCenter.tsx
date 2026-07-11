import type { Notification } from '@/types/leads'

type NotificationCenterProps = {
  notifications: Notification[]
  onDismiss: (id: string) => void
  onNotificationClick: (leadId: string) => void
}

// Story 7: in-app banner/toast when a lead becomes actionable (score reaches hot).
// Purely presentational — list driven entirely by props, no state of its own.
const NotificationCenter = ({ notifications, onDismiss, onNotificationClick }: NotificationCenterProps) => {
  if (notifications.length === 0) return null

  return (
    <div
      data-testid="notification-center"
      style={{
        position: 'fixed',
        top: 16,
        right: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        zIndex: 100,
      }}
    >
      {notifications.map((notification) => (
        <div
          key={notification.id}
          data-testid="notification-toast"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '11px 14px',
            borderRadius: 8,
            borderLeft: '3px solid var(--color-hot)',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderLeftWidth: 3,
            borderLeftColor: 'var(--color-hot)',
            boxShadow: 'var(--shadow)',
            fontSize: 13,
            width: 300,
          }}
        >
          <span className="lead-pulse-dot" aria-hidden />
          <button
            type="button"
            data-testid="notification-toast-body"
            onClick={() => onNotificationClick(notification.leadId)}
            style={{ background: 'none', border: 'none', padding: 0, textAlign: 'left', cursor: 'pointer', flex: 1 }}
          >
            <strong>{notification.leadName ?? 'Un lead'}</strong>{' '}
            <span style={{ color: 'var(--color-text-muted)' }}>está listo para contactar</span>
          </button>
          <button
            type="button"
            data-testid="notification-toast-dismiss"
            onClick={() => onDismiss(notification.id)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-faint)' }}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

export default NotificationCenter
