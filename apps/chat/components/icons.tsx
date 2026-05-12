type IconProps = {
  size?: number
  strokeWidth?: number
  className?: string
}

const iconPath = (name: string) => {
  switch (name) {
    case 'plus':     return <path d="M12 5v14M5 12h14" />
    case 'send':     return <path d="M5 12l14-7-5 16-3-7-6-2z" />
    case 'sun':      return (<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>)
    case 'moon':     return <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    case 'search':   return (<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>)
    case 'chev':     return <path d="M9 6l6 6-6 6" />
    case 'settings': return (<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 1 1 7 4.9l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>)
    case 'check':    return <path d="M5 12l4 4 10-10" />
    case 'brain':    return (<><path d="M9 4a3 3 0 0 0-3 3v1a3 3 0 0 0-2 5 3 3 0 0 0 2 5v1a3 3 0 0 0 6 0V4a3 3 0 0 0-3 0z" /><path d="M15 4a3 3 0 0 1 3 3v1a3 3 0 0 1 2 5 3 3 0 0 1-2 5v1a3 3 0 0 1-6 0" /></>)
    case 'tool':     return <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6 6 2.4 2.4 6-6a4 4 0 0 0 5.4-5.4l-2.7 2.7-2-2 2.7-2.7z" />
    default:         return null
  }
}

export const Icon = ({ name, size = 16, strokeWidth = 1.75, className }: IconProps & { name: string }) => (
  <svg
    width={size} height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    {iconPath(name)}
  </svg>
)
