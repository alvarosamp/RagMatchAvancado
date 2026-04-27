/**
 * contexts/ToastContext.jsx
 * ──────────────────────────
 * Sistema global de notificações (toasts) e diálogos de confirmação.
 * Substitui alert() e confirm() nativos por UI própria.
 *
 * Uso:
 *   const { toast, confirm } = useToast()
 *   toast({ type: 'success', message: 'Salvo!' })
 *   const ok = await confirm('Excluir este item?', { title: 'Confirmar exclusão' })
 */

import { createContext, useContext, useState, useCallback } from 'react'

const ToastCtx = createContext(null)

// ── Estilos por tipo ─────────────────────────────────────────────────────────

const STYLES = {
  success: { border: 'border-green-match/40', bg: 'bg-green-match/10', icon: '✓', color: 'text-green-match' },
  error:   { border: 'border-red-fail/40',    bg: 'bg-red-fail/10',    icon: '✕', color: 'text-red-fail'    },
  warning: { border: 'border-amber/40',       bg: 'bg-amber/10',       icon: '⚠', color: 'text-amber'       },
  info:    { border: 'border-azure/40',       bg: 'bg-azure/10',       icon: 'ℹ', color: 'text-azure-glow'  },
}

// ── Toast list ────────────────────────────────────────────────────────────────

function ToastList({ items, onRemove }) {
  return (
    <div className="fixed top-4 right-4 z-[200] flex flex-col gap-2 pointer-events-none max-w-sm w-full">
      {items.map(t => {
        const s = STYLES[t.type] || STYLES.info
        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border
                        shadow-2xl backdrop-blur-sm animate-fade-up ${s.border} ${s.bg}`}
          >
            <span className={`font-mono text-sm flex-shrink-0 mt-0.5 ${s.color}`}>{s.icon}</span>
            <div className="flex-1 min-w-0">
              {t.title && (
                <p className="text-sm font-display font-bold text-white leading-snug">{t.title}</p>
              )}
              <p className={`text-xs font-body leading-relaxed ${t.title ? 'text-gray-300 mt-0.5' : 'text-white'}`}>
                {t.message}
              </p>
            </div>
            <button
              onClick={() => onRemove(t.id)}
              className="flex-shrink-0 text-gray-500 hover:text-white transition-colors text-xl leading-none mt-0.5"
            >
              ×
            </button>
          </div>
        )
      })}
    </div>
  )
}

// ── Confirm dialog ────────────────────────────────────────────────────────────

function ConfirmDialog({ dialog, onResolve }) {
  if (!dialog) return null
  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={() => onResolve(false)}
    >
      <div
        className="card w-full max-w-sm mx-4 shadow-2xl border-slate-border animate-fade-up"
        onClick={e => e.stopPropagation()}
      >
        {dialog.title && (
          <p className="font-display font-bold text-white text-base mb-2">{dialog.title}</p>
        )}
        <p className="text-sm text-gray-300 font-body leading-relaxed mb-6">{dialog.message}</p>
        <div className="flex gap-2 justify-end">
          <button
            onClick={() => onResolve(false)}
            className="btn-ghost text-sm px-4 py-2"
          >
            Cancelar
          </button>
          <button
            onClick={() => onResolve(true)}
            className="btn-primary text-sm px-4 py-2"
          >
            Confirmar
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function ToastProvider({ children }) {
  const [toasts,  setToasts]  = useState([])
  const [dialog,  setDialog]  = useState(null)

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  /**
   * Exibe uma notificação.
   * @param {{ type?: 'success'|'error'|'warning'|'info', title?: string, message: string, duration?: number }} opts
   */
  const toast = useCallback(({ type = 'info', title, message, duration = 4000 }) => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev.slice(-5), { id, type, title, message }])
    if (duration > 0) setTimeout(() => removeToast(id), duration)
  }, [removeToast])

  /**
   * Abre um diálogo de confirmação. Retorna Promise<boolean>.
   * @param {string} message
   * @param {{ title?: string }} opts
   */
  const confirm = useCallback((message, { title = 'Confirmar ação' } = {}) => {
    return new Promise(resolve => {
      setDialog({ message, title, resolve })
    })
  }, [])

  const handleResolve = (result) => {
    dialog?.resolve(result)
    setDialog(null)
  }

  return (
    <ToastCtx.Provider value={{ toast, confirm }}>
      {children}
      <ToastList items={toasts} onRemove={removeToast} />
      <ConfirmDialog dialog={dialog} onResolve={handleResolve} />
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
