import { useEffect, useRef, useState } from 'react'
import { datasheetsApi, downloadBlob } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'

function WinnerBadge({ winner }) {
  if (winner === 'a') return <Badge tone="emerald">Seu produto</Badge>
  if (winner === 'b') return <Badge tone="red">Concorrente</Badge>
  if (winner === 'tie') return <Badge tone="slate">Empate</Badge>
  return <Badge tone="slate">Sem dado</Badge>
}

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'boolean') return value ? 'Sim' : 'Não'
  return String(value)
}

export default function DatasheetCompare() {
  const { toast } = useToast()
  const inputRef = useRef(null)
  const torInputRef = useRef(null)

  const [dragging, setDragging] = useState(false)
  const [torDragging, setTorDragging] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [generatingTor, setGeneratingTor] = useState(false)
  const [exportingTor, setExportingTor] = useState(false)
  const [torMeta, setTorMeta] = useState({ pn_tor: '', category: '' })
  const [torPreview, setTorPreview] = useState(null)
  const [preview, setPreview] = useState(null) // { model, manufacturer, category, specs }
  const [saving, setSaving] = useState(false)
  const [competitorProduct, setCompetitorProduct] = useState(null)

  const [ourProducts, setOurProducts] = useState([])
  const [ourProductId, setOurProductId] = useState('')
  const [comparing, setComparing] = useState(false)
  const [comparison, setComparison] = useState(null)

  const [gaps, setGaps] = useState(null)
  const [gapsLoading, setGapsLoading] = useState(true)

  const loadGaps = () => {
    setGapsLoading(true)
    datasheetsApi.gaps()
      .then((res) => setGaps(res.data))
      .catch(() => toast({ type: 'error', message: 'Erro ao carregar panorama competitivo.' }))
      .finally(() => setGapsLoading(false))
  }

  useEffect(() => {
    datasheetsApi.products({ is_competitor: false })
      .then((res) => setOurProducts(res.data))
      .catch(() => toast({ type: 'error', message: 'Erro ao carregar seu catalogo.' }))
    loadGaps()
  }, [])

  const handleFile = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      toast({ type: 'error', message: 'Envie um PDF do datasheet.' })
      return
    }
    setExtracting(true)
    setPreview(null)
    setCompetitorProduct(null)
    setComparison(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await datasheetsApi.extract(formData)
      setPreview({
        model: res.data.model || '',
        manufacturer: res.data.manufacturer || '',
        category: res.data.category || '',
        specs: res.data.specs || {},
      })
    } catch (err) {
      toast({
        type: 'error',
        title: 'Erro na extracao',
        message: err.response?.data?.detail || 'Nao foi possivel extrair specs do datasheet.',
      })
    } finally {
      setExtracting(false)
    }
  }

  const handleTorFile = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      toast({ type: 'error', message: 'Envie um PDF do datasheet do fabricante.' })
      return
    }
    setGeneratingTor(true)
    setTorPreview(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      if (torMeta.pn_tor.trim()) formData.append('pn_tor', torMeta.pn_tor.trim())
      if (torMeta.category.trim()) formData.append('category', torMeta.category.trim())
      const res = await datasheetsApi.torPreview(formData)
      setTorPreview(res.data.preview)
      toast({ type: 'success', message: 'Previa TOR gerada. Revise antes de exportar.' })
    } catch (err) {
      toast({
        type: 'error',
        title: 'Erro ao gerar datasheet TOR',
        message: err.response?.data?.detail || 'Nao foi possivel montar a previa TOR.',
      })
    } finally {
      setGeneratingTor(false)
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  const onTorDrop = (e) => {
    e.preventDefault()
    setTorDragging(false)
    handleTorFile(e.dataTransfer.files[0])
  }

  const updateSpecValue = (key, value) => {
    setPreview((prev) => ({ ...prev, specs: { ...prev.specs, [key]: value } }))
  }

  const updateTorField = (key, value) => {
    setTorPreview((prev) => ({ ...prev, [key]: value }))
  }

  const updateTorArray = (key, index, value) => {
    setTorPreview((prev) => {
      const rows = [...(prev?.[key] || [])]
      rows[index] = value
      return { ...prev, [key]: rows }
    })
  }

  const addTorArrayItem = (key) => {
    setTorPreview((prev) => ({ ...prev, [key]: [...(prev?.[key] || []), ''] }))
  }

  const updateTorTable = (key, value) => {
    setTorPreview((prev) => ({
      ...prev,
      tabela_tecnica: { ...(prev?.tabela_tecnica || {}), [key]: value },
    }))
  }

  const exportTorPdf = async () => {
    if (!torPreview?.pn_tor?.trim()) {
      toast({ type: 'error', message: 'Informe o PN TOR antes de exportar.' })
      return
    }
    setExportingTor(true)
    try {
      const res = await datasheetsApi.torExportPdf({ preview: torPreview })
      downloadBlob(res.data, `datasheet_tor_${torPreview.pn_tor}.pdf`)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Nao foi possivel exportar o PDF TOR.' })
    } finally {
      setExportingTor(false)
    }
  }

  const saveCompetitor = async () => {
    if (!preview?.model?.trim()) {
      toast({ type: 'error', message: 'Informe o modelo do produto concorrente.' })
      return
    }
    setSaving(true)
    try {
      const res = await datasheetsApi.import({
        model: preview.model,
        manufacturer: preview.manufacturer,
        category: preview.category,
        specs: preview.specs,
        is_competitor: true,
      })
      setCompetitorProduct(res.data)
      toast({ type: 'success', message: `${res.data.model} salvo como concorrente.` })
      loadGaps()
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao salvar produto concorrente.' })
    } finally {
      setSaving(false)
    }
  }

  const runComparison = async () => {
    if (!ourProductId || !competitorProduct) return
    setComparing(true)
    setComparison(null)
    try {
      const res = await datasheetsApi.compare(ourProductId, competitorProduct.id)
      setComparison(res.data)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Erro ao comparar produtos.' })
    } finally {
      setComparing(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface p-6 text-slate-950 dark:bg-surface-dark dark:text-white lg:p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <Card className="p-6">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Inteligencia comercial</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">Datasheets</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600 dark:text-slate-300">
            Gere datasheets no padrao TOR a partir do PDF do fabricante ou compare produtos concorrentes
            com o seu catalogo.
          </p>
        </Card>

        <Card className="space-y-6 p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Gerador de datasheet TOR</h2>
              <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">
                Envie o datasheet original do fabricante. O sistema traduz, consolida os dados tecnicos e monta uma previa editavel antes do PDF final.
              </p>
            </div>
            {torPreview && (
              <button
                type="button"
                onClick={exportTorPdf}
                disabled={exportingTor}
                className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-40 dark:bg-brand-light dark:hover:bg-brand"
              >
                {exportingTor ? 'Exportando...' : 'Exportar PDF TOR'}
              </button>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-[1fr_1fr_220px]">
            <label className="block">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">PN TOR desejado</span>
              <input
                className="input mt-1"
                value={torMeta.pn_tor}
                placeholder="Ex.: SFPX10GD1310NM10KM"
                onChange={(e) => setTorMeta((prev) => ({ ...prev, pn_tor: e.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Categoria</span>
              <select
                className="input mt-1"
                value={torMeta.category}
                onChange={(e) => setTorMeta((prev) => ({ ...prev, category: e.target.value }))}
              >
                <option value="">Detectar automaticamente</option>
                <option value="Transceiver">Transceiver</option>
                <option value="Modulo optico">Modulo optico</option>
                <option value="Switch">Switch</option>
                <option value="Access Point">Access Point</option>
                <option value="Outro">Outro</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => torInputRef.current?.click()}
              disabled={generatingTor}
              className="mt-5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              {generatingTor ? 'Gerando...' : 'Selecionar PDF'}
            </button>
          </div>

          <div
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
              torDragging
                ? 'border-brand bg-blue-50 dark:border-brand-light dark:bg-brand/10'
                : 'border-slate-300 bg-slate-50 hover:border-brand dark:border-slate-700 dark:bg-slate-900 dark:hover:border-brand-light'
            }`}
            onClick={() => torInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setTorDragging(true) }}
            onDragLeave={() => setTorDragging(false)}
            onDrop={onTorDrop}
          >
            <input
              ref={torInputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => handleTorFile(e.target.files[0])}
            />
            {generatingTor ? (
              <div className="flex flex-col items-center">
                <span className="h-8 w-8 animate-spin rounded-full border-2 border-brand/30 border-t-brand dark:border-brand-light/30 dark:border-t-brand-light" />
                <p className="mt-3 text-sm font-medium text-slate-600 dark:text-slate-300">Montando previa TOR...</p>
              </div>
            ) : (
              <>
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-lg border border-slate-200 bg-white text-sm font-semibold text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
                  PDF
                </div>
                <p className="font-semibold text-slate-950 dark:text-white">{torDragging ? 'Solte o datasheet do fabricante' : 'Arraste o datasheet do fabricante aqui'}</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">ou clique para selecionar</p>
              </>
            )}
          </div>

          {torPreview && (
            <div className="space-y-5 border-t border-slate-200 pt-5 dark:border-slate-700">
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  ['pn_tor', 'PN TOR'],
                  ['categoria', 'Categoria'],
                  ['titulo', 'Titulo'],
                  ['resumo', 'Resumo tecnico'],
                ].map(([key, label]) => (
                  <label key={key} className="block">
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
                    <input
                      className="input mt-1"
                      value={torPreview[key] || ''}
                      onChange={(e) => updateTorField(key, e.target.value)}
                    />
                  </label>
                ))}
              </div>

              <label className="block">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Descricao do produto</span>
                <textarea
                  className="input mt-1 min-h-28"
                  value={torPreview.descricao || ''}
                  onChange={(e) => updateTorField('descricao', e.target.value)}
                />
              </label>

              <div className="grid gap-5 lg:grid-cols-3">
                {[
                  ['tags', 'Tags'],
                  ['caracteristicas', 'Caracteristicas'],
                  ['aplicacoes', 'Aplicacoes'],
                ].map(([key, label]) => (
                  <div key={key} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-slate-950 dark:text-white">{label}</p>
                      <button
                        type="button"
                        onClick={() => addTorArrayItem(key)}
                        className="rounded border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                      >
                        Adicionar
                      </button>
                    </div>
                    {(torPreview[key] || []).map((value, index) => (
                      <input
                        key={`${key}-${index}`}
                        className="input"
                        value={value}
                        onChange={(e) => updateTorArray(key, index, e.target.value)}
                      />
                    ))}
                  </div>
                ))}
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Tabela tecnica</h3>
                <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
                  <table className="w-full text-left">
                    <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                      <tr>
                        <th className="px-4 py-2 font-semibold">Parametro</th>
                        <th className="px-4 py-2 font-semibold">Valor</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                      {Object.entries(torPreview.tabela_tecnica || {}).map(([key, value]) => (
                        <tr key={key}>
                          <td className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300">{key}</td>
                          <td className="px-4 py-2">
                            <input
                              className="w-full rounded border border-slate-200 bg-white px-2 py-1 text-sm text-slate-950 focus:border-brand focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                              value={value || ''}
                              onChange={(e) => updateTorTable(key, e.target.value)}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <label className="block">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Observacao de origem</span>
                <input
                  className="input mt-1"
                  value={torPreview.observacao_origem || ''}
                  onChange={(e) => updateTorField('observacao_origem', e.target.value)}
                />
              </label>
            </div>
          )}
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Panorama competitivo</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Onde perdemos mais — agregado de todo o catalogo proprio contra {gaps?.competitor_count ?? 0} concorrente(s) ja importado(s).
              </p>
            </div>
            <button
              type="button"
              onClick={loadGaps}
              disabled={gapsLoading}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              {gapsLoading ? 'Atualizando...' : 'Atualizar'}
            </button>
          </div>

          <div className="mt-5">
            {gapsLoading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-8 animate-pulse rounded bg-slate-100 dark:bg-slate-700" />
                ))}
              </div>
            ) : !gaps?.competitor_count ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Importe pelo menos um datasheet de concorrente pra ver onde seu catalogo perde mais atributos.
              </p>
            ) : !gaps.gaps.length ? (
              <p className="text-sm text-emerald-700 dark:text-emerald-400">
                Nenhum atributo perdendo pro concorrente ate agora — seu catalogo esta cobrindo bem.
              </p>
            ) : (
              <div className="space-y-3">
                {gaps.gaps.map((gap) => {
                  const max = gaps.gaps[0].perdas
                  const width = Math.max(4, (gap.perdas / max) * 100)
                  return (
                    <div key={gap.field} className="grid grid-cols-[180px_1fr_60px] items-center gap-3">
                      <span className="truncate text-sm text-slate-700 dark:text-slate-300" title={gap.field}>{gap.field}</span>
                      <div className="h-2 rounded bg-slate-100 dark:bg-slate-700">
                        <div className="h-2 rounded bg-red-500" style={{ width: `${width}%` }} />
                      </div>
                      <span className="text-right text-sm font-medium text-red-700 dark:text-red-400">{gap.perdas}x</span>
                    </div>
                  )
                })}
                <p className="pt-1 text-xs text-slate-400 dark:text-slate-500">
                  {gaps.comparisons_run} combinacao(oes) produto proprio x concorrente comparadas.
                </p>
              </div>
            )}
          </div>
        </Card>

        <Card className="p-6">
          <div
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
              dragging
                ? 'border-brand bg-blue-50 dark:border-brand-light dark:bg-brand/10'
                : 'border-slate-300 bg-slate-50 hover:border-brand dark:border-slate-700 dark:bg-slate-900 dark:hover:border-brand-light'
            }`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => handleFile(e.target.files[0])}
            />
            {extracting ? (
              <div className="flex flex-col items-center">
                <span className="h-8 w-8 animate-spin rounded-full border-2 border-brand/30 border-t-brand dark:border-brand-light/30 dark:border-t-brand-light" />
                <p className="mt-3 text-sm font-medium text-slate-600 dark:text-slate-300">Extraindo especificacoes...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
                  PDF
                </div>
                <p className="font-semibold text-slate-950 dark:text-white">{dragging ? 'Solte o datasheet' : 'Arraste o datasheet do concorrente aqui'}</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">ou clique para selecionar no computador</p>
              </div>
            )}
          </div>
        </Card>

        {preview && (
          <Card className="space-y-5 p-6">
            <div>
              <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Confira antes de salvar</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Extraido automaticamente — corrija o que precisar antes de salvar como produto concorrente.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <label className="block">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Modelo</span>
                <input
                  className="input mt-1"
                  value={preview.model}
                  onChange={(e) => setPreview((p) => ({ ...p, model: e.target.value }))}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Fabricante</span>
                <input
                  className="input mt-1"
                  value={preview.manufacturer}
                  onChange={(e) => setPreview((p) => ({ ...p, manufacturer: e.target.value }))}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Categoria</span>
                <input
                  className="input mt-1"
                  value={preview.category}
                  onChange={(e) => setPreview((p) => ({ ...p, category: e.target.value }))}
                />
              </label>
            </div>

            <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
              <table className="w-full text-left">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-2 font-semibold">Atributo</th>
                    <th className="px-4 py-2 font-semibold">Valor extraido</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {Object.entries(preview.specs).length === 0 ? (
                    <tr><td colSpan={2} className="px-4 py-6 text-center text-sm text-slate-500 dark:text-slate-400">Nenhuma especificacao extraida.</td></tr>
                  ) : (
                    Object.entries(preview.specs).map(([key, value]) => (
                      <tr key={key}>
                        <td className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300">{key}</td>
                        <td className="px-4 py-2">
                          <input
                            className="w-full rounded border border-slate-200 bg-white px-2 py-1 text-sm text-slate-950 focus:border-brand focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                            value={typeof value === 'boolean' ? (value ? 'true' : 'false') : value ?? ''}
                            onChange={(e) => updateSpecValue(key, e.target.value)}
                          />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <button
              type="button"
              onClick={saveCompetitor}
              disabled={saving}
              className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-40 dark:bg-brand-light dark:hover:bg-brand"
            >
              {saving ? 'Salvando...' : 'Salvar como concorrente'}
            </button>
          </Card>
        )}

        {competitorProduct && (
          <Card className="space-y-4 p-6">
            <div>
              <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Comparar com seu produto</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {competitorProduct.model} ({competitorProduct.manufacturer || 'fabricante nao informado'}) salvo. Escolha o produto do seu catalogo pra comparar.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <select
                className="input max-w-xs"
                value={ourProductId}
                onChange={(e) => setOurProductId(e.target.value)}
              >
                <option value="">Selecione um produto seu</option>
                {ourProducts.map((product) => (
                  <option key={product.id} value={product.id}>{product.model}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={runComparison}
                disabled={!ourProductId || comparing}
                className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-40 dark:bg-brand-light dark:hover:bg-brand"
              >
                {comparing ? 'Comparando...' : 'Comparar'}
              </button>
            </div>
          </Card>
        )}

        {comparison && (
          <Card className="overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-slate-200 px-6 py-5 dark:border-slate-700 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-950 dark:text-white">
                  {comparison.product_a.model} <span className="text-slate-400 dark:text-slate-500">vs</span> {comparison.product_b.model}
                </h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {comparison.summary.vantagem_a} atributo(s) a seu favor · {comparison.summary.vantagem_b} a favor do concorrente · {comparison.summary.empates_ou_sem_dado} empate(s)/sem dado
                </p>
              </div>
              <div className="flex gap-4 text-sm">
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Seu produto</span>
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-red-500" /> Concorrente</span>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Atributo</th>
                    <th className="px-5 py-3 font-semibold">Seu produto</th>
                    <th className="px-5 py-3 font-semibold">Concorrente</th>
                    <th className="px-5 py-3 font-semibold">Vantagem</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {comparison.fields.map((field) => (
                    <tr key={field.field} className={field.winner === 'b' ? 'bg-red-50/50 dark:bg-red-950/10' : ''}>
                      <td className="px-5 py-3 text-sm font-medium text-slate-950 dark:text-white">{field.field}</td>
                      <td className="px-5 py-3 text-sm text-slate-700 dark:text-slate-300">{displayValue(field.value_a)}</td>
                      <td className="px-5 py-3 text-sm text-slate-700 dark:text-slate-300">{displayValue(field.value_b)}</td>
                      <td className="px-5 py-3"><WinnerBadge winner={field.winner} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
