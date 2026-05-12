type BotAvatarProps = {
  size?: number
  state?: 'idle' | 'thinking'
}

const BotAvatar = ({ size = 32, state = 'idle' }: BotAvatarProps) => {
  const r1 = size * 0.18
  const r2 = size * 0.32
  return (
    <div
      className={`bot-avatar${state === 'thinking' ? ' thinking' : ''}`}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2} cy={size / 2} r={r2}
          fill="none"
          stroke="var(--color-accent)"
          strokeOpacity="0.5"
          strokeWidth="1"
        />
        <circle
          className="core"
          cx={size / 2} cy={size / 2} r={r1}
          fill="var(--color-accent)"
          style={{ transformOrigin: 'center' }}
        />
      </svg>
      <span className="ring" />
      <span className="ring r2" />
    </div>
  )
}

export default BotAvatar
