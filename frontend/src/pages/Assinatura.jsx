import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { documentsApi, downloadBlob } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

function fmtDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtSize(value) {
  const size = Number(value || 0)
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function statusLabel(status) {
  return {
    active: 'Disponivel',
    signature_pending: 'Aguardando assinatura',
    signed: 'Assinado',
    signed_result: 'Arquivo assinado',
    pending: 'Pendente',
    cancelled: 'Cancelado',
  }[status] || status || '-'
}

function getFileName(document) {
  return document?.original_filename || `${document?.title || 'documento'}`
}

export default function Assinatura() {
  const [documents, setDocuments] = useState([])
  const [requests, setRequests] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [signerId, setSignerId] = useState('')
  const [message, setMessage] = useState('')
  const [uploadForm, setUploadForm] = useState({ title: '', category: '', crm_notice_id: '', edital_id: '', notes: '' })
  const [file, setFile] = useState(null)
  const [versionFiles, setVersionFiles] = useState({})
  const [signedFiles, setSignedFiles] = useState({})
  const [searchParams] = useSearchParams()
  const { user, isEditor } = useAuth()
  const { toast } = useToast()

  async function load() {
    setLoading(true)
    try {
      const [docsRes, reqRes, usersRes] = await Promise.allSettled([
        documentsApi.listFiles(),
        documentsApi.listSignatureRequests(),
        documentsApi.listSigners(),
      ])
      if (docsRes.status === 'fulfilled') setDocuments(docsRes.value.data || [])
      if (reqRes.status === 'fulfilled') setRequests(reqRes.value.data || [])
      if (usersRes.status === 'fulfilled') setUsers(usersRes.value.data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    const requestId = searchParams.get('request')
    if (requestId) {
      setTimeout(() => document.getElementById(`request-${requestId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 250)
    }
  }, [searchParams])

  const pendingForMe = useMemo(
    () => requests.filter((item) => item.signer_id === user?.id && item.status === 'pending'),
    [requests, user?.id],
  )
  const requestedByMe = useMemo(
    () => requests.filter((item) => item.requester_id === user?.id),
    [requests, user?.id],
  )
  const signedRequests = useMemo(
    () => requests.filter((item) => item.status === 'signed'),
    [requests],
  )

  const uploadDocument = async (event) => {
    event.preventDefault()
    if (!file) {
      toast({ type: 'error', message: 'Selecione um arquivo para entrar em documentos.' })
      return
    }
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      Object.entries(uploadForm).forEach(([key, value]) => {
        if (String(value || '').trim()) form.append(key, value)
      })
      const response = await documentsApi.uploadFile(form)
      setDocuments((rows) => [response.data, ...rows])
      setSelectedDocumentId(response.data.id)
      setFile(null)
      setUploadForm({ title: '', category: '', crm_notice_id: '', edital_id: '', notes: '' })
      toast({ type: 'success', message: 'Documento salvo em D:\\TOR\\Documentos.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Nao foi possivel salvar o documento.' })
    } finally {
      setUploading(false)
    }
  }

  const uploadVersion = async (documentId) => {
    const nextFile = versionFiles[documentId]
    if (!nextFile) return
    const form = new FormData()
    form.append('file', nextFile)
    try {
      const response = await documentsApi.uploadVersion(documentId, form)
      setDocuments((rows) => [response.data, ...rows])
      setVersionFiles((current) => ({ ...current, [documentId]: null }))
      toast({ type: 'success', message: 'Nova versao adicionada.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Nao foi possivel adicionar a versao.' })
    }
  }

  const requestSignature = async (event) => {
    event.preventDefault()
    if (!selectedDocumentId || !signerId) {
      toast({ type: 'error', message: 'Selecione o documento e quem deve assinar.' })
      return
    }
    try {
      const response = await documentsApi.requestSignature(selectedDocumentId, {
        signer_id: Number(signerId),
        message,
      })
      setRequests((rows) => [response.data, ...rows])
      setDocuments((rows) => rows.map((doc) => doc.id === selectedDocumentId ? { ...doc, status: 'signature_pending' } : doc))
      setMessage('')
      toast({ type: 'success', message: 'Solicitacao enviada ao assinante.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Nao foi possivel solicitar assinatura.' })
    }
  }

  const uploadSigned = async (requestId) => {
    const signedFile = signedFiles[requestId]
    if (!signedFile) return
    const form = new FormData()
    form.append('file', signedFile)
    try {
      const response = await documentsApi.uploadSigned(requestId, form)
      setRequests((rows) => rows.map((item) => item.id === requestId ? response.data : item))
      if (response.data.signed_document) setDocuments((rows) => [response.data.signed_document, ...rows])
      setSignedFiles((current) => ({ ...current, [requestId]: null }))
      toast({ type: 'success', message: 'Documento assinado reenviado ao solicitante.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Nao foi possivel enviar o arquivo assinado.' })
    }
  }

  const downloadDocument = async (document) => {
    try {
      const response = await documentsApi.downloadFile(document.id)
      downloadBlob(response.data, getFileName(document))
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Nao foi possivel baixar o arquivo.' })
    }
  }

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">Documentos e assinatura</p>
            <h1 className="mt-2 text-2xl font-bold text-slate-950 dark:text-white">Entrada, versoes e assinatura de documentos</h1>
            <p className="mt-3 text-sm leading-6 text-slate-500 dark:text-slate-400">
              Salve arquivos em documentos, anexe a um edital ou processo do CRM e solicite assinatura para outro usuario do ambiente.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xl font-bold text-slate-950 dark:text-white">{documents.length}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Arquivos</p>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950/40">
              <p className="text-xl font-bold text-amber-700 dark:text-amber-300">{pendingForMe.length}</p>
              <p className="text-xs text-amber-700 dark:text-amber-300">Para assinar</p>
            </div>
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-800 dark:bg-emerald-950/40">
              <p className="text-xl font-bold text-emerald-700 dark:text-emerald-300">{signedRequests.length}</p>
              <p className="text-xs text-emerald-700 dark:text-emerald-300">Assinados</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <form onSubmit={uploadDocument} className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Entrar com documento</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <input className="input" placeholder="Nome exibido" value={uploadForm.title} onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })} />
            <input className="input" placeholder="Categoria" value={uploadForm.category} onChange={(e) => setUploadForm({ ...uploadForm, category: e.target.value })} />
            <input className="input" placeholder="ID do edital CRM" value={uploadForm.crm_notice_id} onChange={(e) => setUploadForm({ ...uploadForm, crm_notice_id: e.target.value })} />
            <input className="input" placeholder="ID do edital analisado" value={uploadForm.edital_id} onChange={(e) => setUploadForm({ ...uploadForm, edital_id: e.target.value })} />
            <input className="input md:col-span-2" placeholder="Observacoes" value={uploadForm.notes} onChange={(e) => setUploadForm({ ...uploadForm, notes: e.target.value })} />
            <input className="input md:col-span-2" type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
          <button type="submit" disabled={!isEditor || uploading} className="btn-primary mt-4 disabled:opacity-50">
            {uploading ? 'Salvando...' : 'Salvar em documentos'}
          </button>
        </form>

        <form onSubmit={requestSignature} className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Solicitar assinatura</h2>
          <div className="mt-4 space-y-3">
            <select className="input" value={selectedDocumentId} onChange={(e) => setSelectedDocumentId(e.target.value)}>
              <option value="">Selecione um documento</option>
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>{doc.title} - v{doc.version}</option>
              ))}
            </select>
            <select className="input" value={signerId} onChange={(e) => setSignerId(e.target.value)}>
              <option value="">Quem deve assinar</option>
              {users.filter((row) => row.id !== user?.id).map((row) => (
                <option key={row.id} value={row.id}>{row.full_name || row.email}</option>
              ))}
            </select>
            <textarea className="input min-h-[92px]" placeholder="Mensagem para o assinante" value={message} onChange={(e) => setMessage(e.target.value)} />
          </div>
          <button type="submit" disabled={!isEditor} className="btn-primary mt-4 disabled:opacity-50">
            Solicitar assinatura
          </button>
        </form>
      </section>

      {pendingForMe.length > 0 && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-5 dark:border-amber-800 dark:bg-amber-950/40">
          <h2 className="text-base font-semibold text-amber-900 dark:text-amber-200">Pendentes para minha assinatura</h2>
          <div className="mt-4 space-y-3">
            {pendingForMe.map((item) => (
              <div id={`request-${item.id}`} key={item.id} className="rounded-lg border border-amber-200 bg-white p-4 dark:border-amber-800 dark:bg-slate-900">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-950 dark:text-white">{item.document?.title || 'Documento'}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{item.message || 'Sem mensagem'} · solicitado em {fmtDate(item.created_at)}</p>
                  </div>
                  <button type="button" onClick={() => downloadDocument(item.document)} className="btn-ghost">Baixar</button>
                </div>
                <div className="mt-3 flex flex-col gap-2 md:flex-row">
                  <input className="input" type="file" onChange={(e) => setSignedFiles({ ...signedFiles, [item.id]: e.target.files?.[0] || null })} />
                  <button type="button" onClick={() => uploadSigned(item.id)} disabled={!signedFiles[item.id]} className="btn-primary disabled:opacity-50">
                    Enviar assinado
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
        <h2 className="text-base font-semibold text-slate-950 dark:text-white">Documentos</h2>
        {loading ? (
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">Carregando...</p>
        ) : documents.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">Nenhum documento cadastrado ainda.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-700 dark:text-slate-400">
                <tr>
                  <th className="py-3 pr-4">Documento</th>
                  <th className="py-3 pr-4">Vinculo</th>
                  <th className="py-3 pr-4">Status</th>
                  <th className="py-3 pr-4">Versao</th>
                  <th className="py-3 pr-4">Arquivo</th>
                  <th className="py-3 text-right">Acoes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td className="py-3 pr-4">
                      <p className="font-semibold text-slate-900 dark:text-white">{doc.title}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{doc.category || 'Sem categoria'} · {fmtDate(doc.created_at)}</p>
                    </td>
                    <td className="py-3 pr-4 text-xs text-slate-500 dark:text-slate-400">
                      {doc.crm_notice_id ? `CRM ${doc.crm_notice_id}` : doc.edital_id ? `Edital ${doc.edital_id}` : '-'}
                    </td>
                    <td className="py-3 pr-4 text-xs text-slate-600 dark:text-slate-300">{statusLabel(doc.status)}</td>
                    <td className="py-3 pr-4 text-xs text-slate-600 dark:text-slate-300">v{doc.version}</td>
                    <td className="py-3 pr-4 text-xs text-slate-500 dark:text-slate-400">{getFileName(doc)} · {fmtSize(doc.size_bytes)}</td>
                    <td className="py-3 text-right">
                      <div className="flex flex-wrap justify-end gap-2">
                        <button type="button" onClick={() => downloadDocument(doc)} className="btn-ghost">Baixar</button>
                        {isEditor && (
                          <>
                            <input className="input max-w-[220px]" type="file" onChange={(e) => setVersionFiles({ ...versionFiles, [doc.id]: e.target.files?.[0] || null })} />
                            <button type="button" onClick={() => uploadVersion(doc.id)} disabled={!versionFiles[doc.id]} className="btn-ghost disabled:opacity-50">Nova versao</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Solicitadas por mim</h2>
          <div className="mt-4 space-y-2">
            {requestedByMe.length === 0 ? <p className="text-sm text-slate-500 dark:text-slate-400">Nenhuma solicitacao enviada.</p> : requestedByMe.map((item) => (
              <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{item.document?.title || 'Documento'}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{statusLabel(item.status)} · {fmtDate(item.updated_at)}</p>
                  </div>
                  {item.signed_document && <button type="button" onClick={() => downloadDocument(item.signed_document)} className="btn-ghost">Baixar assinado</button>}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Concluidos</h2>
          <div className="mt-4 space-y-2">
            {signedRequests.length === 0 ? <p className="text-sm text-slate-500 dark:text-slate-400">Nenhum documento assinado ainda.</p> : signedRequests.map((item) => (
              <div key={item.id} className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-800 dark:bg-emerald-950/40">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{item.document?.title || 'Documento'}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Assinado em {fmtDate(item.signed_at)}</p>
                  </div>
                  {item.signed_document && <button type="button" onClick={() => downloadDocument(item.signed_document)} className="btn-ghost">Baixar</button>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
