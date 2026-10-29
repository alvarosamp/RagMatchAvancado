import { useEffect, useState } from 'react'
import { whatsappApi } from '../api/client'

export default function WhatsAppSettings() {
  const [status, setStatus] = useState(null)
  const [link, setLink] = useState(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    whatsappApi.status().then(({ data }) => { if (active) setStatus(data) })
      .catch(() => { if (active) setError('Não foi possível consultar o WhatsApp.') })
    return () => { active = false }
  }, [])

  async function action(task, message) {
    setBusy(true)
    setError('')
    setFeedback('')
    try {
      await task()
      const { data } = await whatsappApi.status()
      setStatus(data)
      if (data.linked) setLink(null)
      setFeedback(message)
    } catch (err) {
      setError(err.response?.data?.detail || 'Não foi possível concluir. Tente novamente.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card space-y-4">
      <div>
        <h2 className="font-display font-bold text-white text-sm">WhatsApp da sua empresa</h2>
        <p className="text-xs text-gray-400 mt-1">Consulte editais e próximas sessões e receba um resumo diário opcional.</p>
      </div>
      {!status && !error && <p role="status">Consultando WhatsApp...</p>}
      {status && !status.configured && <p className="text-sm text-gray-400">O atendimento por WhatsApp ainda não foi ativado pelo administrador.</p>}
      {(status?.configured || status?.linked) && (
        <div className="space-y-3 text-sm">
          <p>{status.linked ? `Vinculado ao número com final ${status.phone_suffix}.` : 'Seu WhatsApp ainda não está vinculado.'}</p>
          {status.linked ? (
            <>
              <label className="flex items-start gap-2">
                <input type="checkbox" checked={status.notifications_enabled} disabled={busy || !status.configured}
                  onChange={(event) => {
                    const checked = event.target.checked
                    action(() => whatsappApi.preferences({ notifications_enabled: checked }), 'Preferência atualizada.')
                  }} />
                Receber resumo diário da minha empresa pelo WhatsApp
              </label>
              <p className="text-xs text-gray-400">Você também pode enviar PARAR no WhatsApp para desativar os resumos.</p>
              <div className="flex flex-wrap gap-3">
                <button type="button" className="btn-secondary" disabled={busy || !status.configured}
                  onClick={() => action(() => whatsappApi.test(), 'Resumo enviado para o seu WhatsApp.')}>Enviar resumo de teste</button>
                <button type="button" className="btn-secondary" disabled={busy}
                  onClick={() => action(async () => { await whatsappApi.unlink(); setLink(null) }, 'WhatsApp desvinculado.')}>Desvincular</button>
              </div>
              <p className="text-xs text-gray-400">Comandos: RESUMO, EDITAIS, PRAZOS e AJUDA.</p>
            </>
          ) : (
            <>
              <button type="button" className="btn-secondary" disabled={busy}
                onClick={() => action(async () => { const { data } = await whatsappApi.link(); setLink(data) }, 'Envie a mensagem pelo seu WhatsApp para confirmar o vínculo.')}>Vincular meu WhatsApp</button>
              {link && <div className="space-y-2">
                <p>Abra o WhatsApp e envie a mensagem pronta em até 10 minutos. O código é pessoal.</p>
                <a className="text-amber underline" href={link.url} target="_blank" rel="noreferrer">Abrir WhatsApp para confirmar</a>
                <p className="break-all font-mono text-xs select-all">{link.message}</p>
                <button type="button" className="btn-secondary" disabled={busy}
                  onClick={() => action(async () => {}, 'Situação atualizada.')}>Já enviei, verificar vínculo</button>
                <button type="button" className="btn-secondary" disabled={busy}
                  onClick={() => action(async () => { await whatsappApi.unlink(); setLink(null) }, 'Vínculo cancelado.')}>Cancelar</button>
              </div>}
            </>
          )}
        </div>
      )}
      {feedback && <p role="status" className="text-sm text-emerald-400">{feedback}</p>}
      {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
      <p className="text-xs text-gray-500">Integração fornecida pela Evolution API.</p>
    </div>
  )
}
