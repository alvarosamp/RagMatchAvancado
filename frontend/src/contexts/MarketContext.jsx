import { createContext, useContext, useEffect, useState } from 'react'
import { marketApi } from '../api/client'
import { getLocalMarketProfile, mergeMarketProfile } from '../market/profile'

const MarketContext = createContext(null)

export function MarketProvider({ children }) {
  const [market, setMarket] = useState(() => getLocalMarketProfile())

  useEffect(() => {
    marketApi.profile()
      .then((res) => setMarket(mergeMarketProfile(res.data)))
      .catch(() => setMarket(getLocalMarketProfile()))
  }, [])

  return (
    <MarketContext.Provider value={market}>
      {children}
    </MarketContext.Provider>
  )
}

export function useMarket() {
  const ctx = useContext(MarketContext)
  if (!ctx) throw new Error('useMarket deve ser usado dentro de MarketProvider')
  return ctx
}
