export function buildTenderExport(preview, source) {
  if (!preview?.opportunity || !source) throw new Error('Dados do edital indisponíveis para exportação.');
  const opportunity = preview.opportunity;
  const organ = source.orgao || {};
  const crm = {
    number: source.edital || opportunity.edital_number || null,
    bid_number: source.edital || opportunity.edital_number || null,
    title: source.objeto || opportunity.object || null,
    municipality_name: organ.cidade || opportunity.public_body_city || null,
    state: organ.uf || opportunity.public_body_state || null,
    uasg: organ.codigo || opportunity.uasg || null,
    auction_date: opportunity.opening_at || null,
    estimated_value: source.valor_estimado ?? opportunity.estimated_value ?? null,
    address: organ.endereco || null,
    particularities: source.observacao || null,
    modality: null,
    proposal_validity: null,
    bi_criterion: null,
  };
  // Remove signed document URLs, retaining every other original field.
  const { documento, ...original } = source;
  return {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    source: { provider: 'conlicitacao', external_id: opportunity.external_id,
      filter_id: preview.filter_id, bulletin_id: preview.bulletin_id,
      bulletin_number: preview.bulletin_number, bulletin_closed_at: preview.bulletin_closed_at },
    edital: crm,
    orgao: organ,
    opportunity: { ...opportunity, documents: opportunity.documents.map(({ filename, index }) => ({ filename, index })) },
    provider_data: original,
    documentos: (source.documentos || opportunity.documents).map(({ filename, index }) => ({ filename, index })),
    campos_nao_informados: Object.entries(crm).filter(([, value]) => value == null || value === '').map(([key]) => key),
    limitations: ['Dados da API; conteúdo dos arquivos não analisado. Modalidade, validade e critérios técnicos não são inferidos.'],
  };
}

export function tenderExportJson(preview, source) {
  return JSON.stringify(buildTenderExport(preview, source), (key, value) =>
    /^(token|authorization|password|api_key|secret|access_token|refresh_token)$/i.test(key) ? '[REDACTED]' : value, 2);
}
