select distinct on (tenant_id, source, entity, source_id)
    tenant_id, source, entity, source_id, payload, payload_hash, source_updated_at, ingested_at
from {{ source('raw','records') }}
order by tenant_id, source, entity, source_id, revision_number desc
