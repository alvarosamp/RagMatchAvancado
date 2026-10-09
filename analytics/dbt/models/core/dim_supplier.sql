select * from {{ source('ledger','entities') }} where kind='supplier'
