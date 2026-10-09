select * from {{ source('ledger','entities') }} where kind='category'
