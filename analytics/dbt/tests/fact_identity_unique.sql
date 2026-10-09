select tenant_id,source,kind,source_id,count(*)
from {{ source('ledger','facts') }}
group by tenant_id,source,kind,source_id having count(*)>1
