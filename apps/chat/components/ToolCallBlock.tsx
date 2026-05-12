'use client'
import { useState, useEffect } from 'react'
import { Icon } from './icons'

export type ToolCallStatus = 'calling' | 'running' | 'done'

type ToolCallBlockProps = {
  name: string
  args: string
  result: string | null
  status: ToolCallStatus
}

const STATUS_LABEL: Record<ToolCallStatus, string> = {
  calling: 'Llamando',
  running: 'Ejecutando',
  done:    'Completado',
}

const ToolCallBlock = ({ name, args, result, status }: ToolCallBlockProps) => {
  const [open, setOpen] = useState(status !== 'done')

  useEffect(() => {
    if (status === 'done') setOpen(false)
  }, [status])

  return (
    <div className={`toolcall${open ? ' open' : ''} ${status}`}>
      <div className="toolcall-head" onClick={() => setOpen((o) => !o)}>
        <Icon name="tool" size={14} />
        <span className="name">{name}()</span>
        <span className="status">
          {status === 'done'
            ? <Icon name="check" size={12} />
            : <span className="dot" />}
          {STATUS_LABEL[status]}
        </span>
        <Icon name="chev" size={14} className="chev" />
      </div>
      {open && (
        <div className="toolcall-body">
          <div style={{ opacity: 0.7, marginBottom: 6 }}>// argumentos</div>
          {args}
          {status === 'done' && result && (
            <>
              <div style={{ opacity: 0.7, margin: '10px 0 6px' }}>// resultado</div>
              {result}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default ToolCallBlock
