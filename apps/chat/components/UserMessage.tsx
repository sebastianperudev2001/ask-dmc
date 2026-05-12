type UserMessageProps = { text: string }

const UserMessage = ({ text }: UserMessageProps) => (
  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 24 }}>
    <div
      style={{
        background: 'var(--color-brand)',
        color: 'var(--color-brand-ink)',
        padding: '10px 14px',
        borderRadius: '16px 16px 4px 16px',
        maxWidth: '80%',
        fontSize: 14.5,
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
      }}
    >
      {text}
    </div>
  </div>
)

export default UserMessage
