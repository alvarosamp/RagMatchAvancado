import React, { useMemo } from 'react'

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

/**
 * PasswordRequirements
 * - Mostra uma checklist dos requisitos de senha em tempo real.
 * - As regras aqui refletem a política do backend.
 *   Fonte: backend/app/auth/password_policy.py
 *
 * Props:
 * - value: string (senha atual)
 * - showStrength?: boolean (default true)
 * - title?: string
 */
export default function PasswordRequirements({ value, showStrength = true, title = 'Requisitos de senha' }) {
  const password = value || ''

  const checks = useMemo(() => {
    const hasLower = /[a-z]/.test(password)
    const hasUpper = /[A-Z]/.test(password)
    const hasNumber = /\d/.test(password)
    const hasSymbol = /[^A-Za-z0-9]/.test(password)

    const items = [
      {
        id: 'minLen8',
        label: 'Pelo menos 8 caracteres',
        ok: password.length >= 8,
      },
      {
        id: 'lower',
        label: 'Pelo menos 1 letra minúscula',
        ok: hasLower,
      },
      {
        id: 'upper',
        label: 'Pelo menos 1 letra maiúscula',
        ok: hasUpper,
      },
      {
        id: 'number',
        label: 'Pelo menos 1 número',
        ok: hasNumber,
      },
      {
        id: 'symbol',
        label: 'Pelo menos 1 símbolo (ex: !@#$%&*)',
        ok: hasSymbol,
      },
    ]

    const okCount = items.filter(i => i.ok).length
    return { items, okCount }
  }, [password])

  const strength = useMemo(() => {
    const ratio = checks.items.length === 0 ? 0 : checks.okCount / checks.items.length
    const pct = Math.round(ratio * 100)

    const level =
      pct === 100 ? 'strong' :
      pct >= 50 ? 'medium' :
      password.length > 0 ? 'weak' :
      'empty'

    return { pct: clamp(pct, 0, 100), level }
  }, [checks.items.length, checks.okCount, password.length])

  const barCls =
    strength.level === 'strong' ? 'bg-green-match' :
    strength.level === 'medium' ? 'bg-yellow-400' :
    strength.level === 'weak' ? 'bg-red-fail' :
    'bg-slate-border'

  const dotCls = (ok) => (
    ok
      ? 'bg-green-match border-green-match/30'
      : 'bg-transparent border-slate-border'
  )

  const textCls = (ok) => (
    ok ? 'text-gray-200' : 'text-gray-500'
  )

  return (
    <div className="mt-2">
      {showStrength && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-mono text-gray-500">{title}</p>
            <p className="text-xs font-mono text-gray-600">{strength.pct}%</p>
          </div>
          <div className="h-2 rounded-full bg-ink-50 border border-slate-border overflow-hidden">
            <div
              className={`h-full ${barCls} transition-all duration-200`}
              style={{ width: `${strength.pct}%` }}
            />
          </div>
        </div>
      )}

      <ul className="space-y-2">
        {checks.items.map(item => (
          <li key={item.id} className="flex items-center gap-2">
            <span className={`w-3.5 h-3.5 rounded-full border ${dotCls(item.ok)} transition-colors`} />
            <span className={`text-xs font-mono ${textCls(item.ok)}`}>{item.label}</span>
          </li>
        ))}
      </ul>

      <p className="text-[11px] text-gray-600 mt-2 font-mono">
        Dica: use uma senha única e não reutilize senhas de outros serviços.
      </p>
    </div>
  )
}
