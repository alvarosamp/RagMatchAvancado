import { useEffect } from 'react'

const CRM_ENTRYPOINT = '/crm/'

export default function CrmHub() {
  useEffect(() => {
    window.location.replace(CRM_ENTRYPOINT)
  }, [])

  return (
    <div className="grid min-h-screen place-items-center bg-[#f6f1ea] text-slate-950 dark:bg-surface-dark dark:text-white">
      <div className="text-center">
        <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-red-200 border-t-red-700 dark:border-red-600/25 dark:border-t-red-600" />
        <p className="mt-4 text-sm font-semibold">Abrindo CRM...</p>
      </div>
    </div>
  )
}
