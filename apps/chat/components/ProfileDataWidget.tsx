'use client'
import { useState } from 'react'
import type { ProfileData, ProfileDataPrefill } from '@/types/chat'

type ProfileDataWidgetProps = {
  callId: string
  prefill: ProfileDataPrefill
  onSubmit: (callId: string, data: ProfileData) => void
}

const fieldStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--color-text-muted)',
}

const inputStyle: React.CSSProperties = {
  border: '1px solid var(--color-border-strong)',
  borderRadius: 8,
  padding: '8px 10px',
  fontSize: 14,
  fontFamily: 'inherit',
  background: 'var(--color-bg)',
  color: 'var(--color-text)',
}

const ProfileDataWidget = ({ callId, prefill, onSubmit }: ProfileDataWidgetProps) => {
  const [budget, setBudget] = useState(prefill.budget != null ? String(prefill.budget) : '')
  const [maxDurationWeeks, setMaxDurationWeeks] = useState(
    prefill.maxDurationWeeks != null ? String(prefill.maxDurationWeeks) : ''
  )
  const [professionalBackground, setProfessionalBackground] = useState(prefill.professionalBackground ?? '')
  const [desiredStack, setDesiredStack] = useState(prefill.desiredStack ?? '')
  const [name, setName] = useState(prefill.name ?? '')
  const [email, setEmail] = useState(prefill.email ?? '')

  const isValidEmail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())

  const isValid =
    budget.trim() !== '' &&
    Number(budget) > 0 &&
    maxDurationWeeks.trim() !== '' &&
    Number(maxDurationWeeks) > 0 &&
    professionalBackground.trim() !== '' &&
    desiredStack.trim() !== '' &&
    name.trim() !== '' &&
    isValidEmail

  const submit = () => {
    console.log('[ProfileDataWidget] submit clicked', { isValid, callId, budget, maxDurationWeeks, professionalBackground, desiredStack, name, email })
    if (!isValid) {
      console.log('[ProfileDataWidget] BLOCKED — isValid is false')
      return
    }
    onSubmit(callId, {
      budget: Number(budget),
      maxDurationWeeks: Number(maxDurationWeeks),
      professionalBackground: professionalBackground.trim(),
      desiredStack: desiredStack.trim(),
      name: name.trim(),
      email: email.trim(),
    })
  }

  return (
    <div
      data-testid="profile-data-widget"
      style={{
        marginTop: 10,
        marginBottom: 10,
        padding: 14,
        borderRadius: 12,
        border: '1px solid var(--color-border-strong)',
        background: 'var(--color-surface-2)',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        maxWidth: 420,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>
        Confirma tus datos para buscar el programa ideal
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle} htmlFor={`name-${callId}`}>Nombre completo</label>
        <input
          id={`name-${callId}`}
          data-testid="profile-data-widget-name-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={inputStyle}
        />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle} htmlFor={`email-${callId}`}>Email</label>
        <input
          id={`email-${callId}`}
          data-testid="profile-data-widget-email-input"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={inputStyle}
        />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle} htmlFor={`budget-${callId}`}>Presupuesto (S/)</label>
        <input
          id={`budget-${callId}`}
          data-testid="profile-data-widget-budget-input"
          type="number"
          min={1}
          value={budget}
          onChange={(e) => setBudget(e.target.value)}
          style={inputStyle}
        />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle} htmlFor={`duration-${callId}`}>Duración máxima (semanas)</label>
        <input
          id={`duration-${callId}`}
          data-testid="profile-data-widget-duration-input"
          type="number"
          min={1}
          value={maxDurationWeeks}
          onChange={(e) => setMaxDurationWeeks(e.target.value)}
          style={inputStyle}
        />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle} htmlFor={`background-${callId}`}>Background profesional</label>
        <input
          id={`background-${callId}`}
          data-testid="profile-data-widget-background-input"
          type="text"
          value={professionalBackground}
          onChange={(e) => setProfessionalBackground(e.target.value)}
          style={inputStyle}
        />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle} htmlFor={`stack-${callId}`}>Stack / tema deseado</label>
        <input
          id={`stack-${callId}`}
          data-testid="profile-data-widget-stack-input"
          type="text"
          value={desiredStack}
          onChange={(e) => setDesiredStack(e.target.value)}
          style={inputStyle}
        />
      </div>

      <button
        data-testid="profile-data-widget-submit-button"
        disabled={!isValid}
        onClick={submit}
        style={{
          alignSelf: 'flex-start',
          padding: '8px 16px',
          borderRadius: 8,
          border: 0,
          background: isValid ? 'var(--color-brand)' : 'var(--color-surface-3)',
          color: isValid ? 'var(--color-brand-ink)' : 'var(--color-text-faint)',
          fontSize: 13,
          fontWeight: 600,
          cursor: isValid ? 'pointer' : 'not-allowed',
        }}
      >
        Confirmar
      </button>
    </div>
  )
}

export default ProfileDataWidget
