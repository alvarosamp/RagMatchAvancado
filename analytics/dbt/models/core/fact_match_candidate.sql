select * from {{ source('ledger','facts') }} where kind='match'
