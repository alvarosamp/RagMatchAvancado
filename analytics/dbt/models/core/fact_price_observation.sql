select * from {{ source('ledger','facts') }} where kind='price'
