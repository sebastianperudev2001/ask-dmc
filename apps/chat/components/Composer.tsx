'use client'
import { useState, useRef, useCallback, useEffect } from 'react'
import { Icon } from './icons'

type ComposerProps = {
  onSend: (text: string) => void
  disabled: boolean
}

const Composer = ({ onSend, disabled }: ComposerProps) => {
  const [val, setVal] = useState('')
  const taRef = useRef<HTMLTextAreaElement>(null)

  const grow = useCallback(() => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = '24px'
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }, [])

  useEffect(() => { grow() }, [val, grow])

  const submit = () => {
    const v = val.trim()
    if (!v || disabled) return
    onSend(v)
    setVal('')
  }

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 272,
        right: 0,
        padding: '14px 28px 22px',
        background: 'linear-gradient(to bottom, transparent 0%, var(--color-bg) 30%)',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          pointerEvents: 'auto',
          maxWidth: 760,
          margin: '0 auto',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-strong)',
          borderRadius: 18,
          padding: '10px 10px 10px 16px',
          display: 'flex',
          alignItems: 'flex-end',
          gap: 8,
          boxShadow: 'var(--shadow)',
        }}
      >
        <textarea
          ref={taRef}
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder="Escribe tu consulta sobre cursos, especializaciones o tu ruta de aprendizaje…"
          rows={1}
          style={{
            flex: 1,
            border: 0,
            outline: 0,
            resize: 'none',
            background: 'transparent',
            fontFamily: 'inherit',
            fontSize: 14.5,
            color: 'var(--color-text)',
            lineHeight: 1.5,
            padding: '8px 0',
            maxHeight: 200,
            minHeight: 24,
          }}
        />
        <button
          disabled={!val.trim() || disabled}
          onClick={submit}
          style={{
            width: 36,
            height: 36,
            borderRadius: 12,
            background: !val.trim() || disabled ? 'var(--color-surface-3)' : 'var(--color-brand)',
            color: !val.trim() || disabled ? 'var(--color-text-faint)' : 'var(--color-brand-ink)',
            border: 0,
            display: 'grid',
            placeItems: 'center',
            cursor: !val.trim() || disabled ? 'not-allowed' : 'pointer',
            flexShrink: 0,
          }}
        >
          <Icon name="send" size={16} />
        </button>
      </div>
      <p
        style={{
          textAlign: 'center',
          fontSize: 11,
          color: 'var(--color-text-faint)',
          margin: '8px 0 0',
          pointerEvents: 'none',
        }}
      >
        El asesor puede equivocarse. Verifica detalles con el área académica.
        {' '}<kbd style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderBottomWidth: 2, borderRadius: 4, padding: '1px 5px' }}>Enter</kbd> para enviar ·{' '}
        <kbd style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderBottomWidth: 2, borderRadius: 4, padding: '1px 5px' }}>Shift</kbd>+<kbd style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderBottomWidth: 2, borderRadius: 4, padding: '1px 5px' }}>Enter</kbd> nueva línea
      </p>
    </div>
  )
}

export default Composer
