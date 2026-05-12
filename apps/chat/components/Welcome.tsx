import BotAvatar from './BotAvatar'
import { SUGGESTIONS } from '@/data/mock'

type WelcomeProps = {
  onPick: (text: string) => void
}

const Welcome = ({ onPick }: WelcomeProps) => (
  <div
    style={{
      minHeight: 'calc(100vh - 56px - 160px)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      textAlign: 'center',
      padding: '24px 0',
    }}
  >
    <div style={{ marginBottom: 22 }}>
      <BotAvatar size={56} />
    </div>
    <h2
      style={{
        margin: '0 0 8px',
        fontSize: 28,
        fontWeight: 500,
        letterSpacing: '-0.02em',
        color: 'var(--color-text)',
      }}
    >
      Hola, soy tu asesor académico DMC
    </h2>
    <p
      style={{
        margin: '0 0 28px',
        color: 'var(--color-text-muted)',
        fontSize: 15,
        maxWidth: 460,
      }}
    >
      Te oriento para elegir el curso, especialización o diploma que mejor se ajuste a tu perfil
      profesional y objetivos de carrera.
    </p>
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 10,
        width: '100%',
        maxWidth: 620,
      }}
    >
      {SUGGESTIONS.map((s, i) => (
        <button
          key={i}
          onClick={() => onPick(s.title)}
          style={{
            textAlign: 'left',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 12,
            padding: '14px 16px',
            cursor: 'pointer',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            transition: 'border-color .15s, transform .15s, box-shadow .15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-brand)'
            e.currentTarget.style.boxShadow = 'var(--shadow)'
            e.currentTarget.style.transform = 'translateY(-1px)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-border)'
            e.currentTarget.style.boxShadow = 'none'
            e.currentTarget.style.transform = 'none'
          }}
        >
          <span style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-text)', lineHeight: 1.35 }}>
            {s.title}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-faint)' }}>
            {s.sub}
          </span>
        </button>
      ))}
    </div>
  </div>
)

export default Welcome
