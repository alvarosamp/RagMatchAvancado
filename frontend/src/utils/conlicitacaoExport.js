export async function collectConlicitacaoExport(api, onProgress = () => {}, cancelled = () => false) {
  const report = { schema_version: 1, generated_at: new Date().toISOString(), complete: true,
    scope: 'Dados disponíveis para esta assinatura: filtros, todos os boletins listados, detalhes, usuários, monitoradas e mensagens.',
    limitations: ['Não inclui bytes de documentos nem licitações fora dos filtros da assinatura. Falhas e limites ficam registrados.'],
    responses: [], errors: [] };
  const check = () => { if (cancelled()) throw new Error('Coleta interrompida pelo usuário.'); };
  const call = async (endpoint, fn) => {
    check(); onProgress(endpoint);
    try {
      const { data } = await fn();
      report.responses.push({ endpoint, collected_at: new Date().toISOString(), response: data });
      return data.data;
    } catch (error) {
      report.complete = false;
      report.errors.push({ endpoint, status: error.response?.status || null, message: 'Consulta não concluída; confira o endpoint no laboratório.' });
      return null;
    }
  };
  const pages = async (label, fn, keys) => {
    const rows = [];
    for (let page = 1; page <= 1000; page++) {
      const payload = await call(`${label}?page=${page}`, () => fn(page));
      if (!payload) break;
      const entries = keys.map(key => payload[key]).find(Array.isArray);
      if (!entries) { report.complete = false; report.errors.push({ endpoint: label, message: 'Lista ausente na resposta.' }); break; }
      rows.push(...entries);
      const totalPages = Number(payload.total_pages || payload.pagination?.total_pages || Math.ceil(Number(payload.filtro?.total_boletins || payload.total_entries || payload.pagination?.total_entries) / 100));
      if ((totalPages > 0 && page >= totalPages) || (!totalPages && entries.length < 100)) break;
      if (page === 1000) { report.complete = false; report.errors.push({ endpoint: label, message: 'Limite de 1000 páginas atingido.' }); }
    }
    return rows;
  };
  try {
    const filters = await call('filters', () => api.labFilters());
    await call('users', () => api.labUsers());
    const bulletinIds = new Set();
    for (const filter of filters?.filtros || []) {
      const rows = await pages(`filters/${filter.id}/bulletins`, page => api.labBulletins(filter.id, { page, per_page: 100 }), ['boletins', 'bulletins']);
      for (const row of rows) bulletinIds.add(row.id);
    }
    for (const id of bulletinIds) await call(`bulletins/${id}`, () => api.labBulletin(id));
    const monitored = await pages('monitored', page => api.labMonitored({ page, per_page: 100 }), ['electronics_trading', 'monitored_biddings', 'trading_biddings', 'biddings', 'licitacoes']);
    for (const id of new Set(monitored.map(row => row.bidding_id).filter(Boolean))) {
      await pages(`monitored/${id}/messages`, page => api.labMessages(id, { page, per_page: 100 }), ['trading_messages', 'messages']);
    }
  } catch (error) {
    report.complete = false;
    report.errors.push({ message: error.message });
  }
  report.finished_at = new Date().toISOString();
  return report;
}

export function conlicitacaoExportJson(report) {
  return JSON.stringify(report, (key, value) =>
    /^(authorization|password|token|access_token|refresh_token|api_key|secret|secret_key)$/i.test(key)
      ? '[REDACTED]' : value, 2);
}
