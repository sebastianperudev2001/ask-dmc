import type { Source } from '@/types/chat'

type SourceChipsProps = {
  sources: Source[]
}

const SourceChips = ({ sources }: SourceChipsProps) => {
  const unique = Array.from(new Set(sources.map((s) => s.course)))
  if (!unique.length) return null

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 6,
        marginTop: 10,
      }}
    >
      {unique.map((course) => (
        <span
          key={course}
          style={{
            fontSize: 11,
            fontWeight: 500,
            padding: '3px 8px',
            borderRadius: 999,
            background: 'var(--color-tool-bg)',
            color: 'var(--color-tool)',
            border: '1px solid color-mix(in oklab, var(--color-tool) 25%, transparent)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {course}
        </span>
      ))}
    </div>
  )
}

export default SourceChips
