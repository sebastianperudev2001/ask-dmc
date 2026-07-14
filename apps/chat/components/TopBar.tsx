import BotAvatar from './BotAvatar'
import { Icon } from './icons'

type TopBarProps = { busy: boolean; sidebarOpen: boolean; onToggleSidebar: () => void }

const TopBar = ({ busy, sidebarOpen, onToggleSidebar }: TopBarProps) => (
  <div
    style={{
      height: 56,
      padding: '0 20px 0 24px',
      borderBottom: '1px solid var(--color-border)',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      background: 'var(--color-surface)',
      flexShrink: 0,
    }}
  >
    <button
      onClick={onToggleSidebar}
      title={sidebarOpen ? 'Ocultar historial' : 'Mostrar historial'}
      style={{ width: 32, height: 32, borderRadius: 8, border: '1px solid transparent', background: 'transparent', color: 'var(--color-text-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer', flexShrink: 0 }}
    >
      <Icon name="sidebar" size={16} />
    </button>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
      <BotAvatar size={26} state={busy ? 'thinking' : 'idle'} />
      <h1 style={{ margin: 0, fontSize: 14.5, fontWeight: 500, letterSpacing: '-0.005em', color: 'var(--color-text)', whiteSpace: 'nowrap' }}>
        Asesor Académico DMC
      </h1>
      <span style={{ color: 'var(--color-text-faint)', fontSize: 13 }}>· Recomendación de cursos</span>
    </div>
  </div>
)

export default TopBar
