import Card from './Card'

export default function StatCard({ label, value, danger = false }) {
  return (
    <Card className={`p-5 ${danger ? 'border-red-300 dark:border-red-800' : ''}`}>
      <p className={`text-sm font-semibold ${danger ? 'text-red-700 dark:text-red-400' : 'text-slate-600 dark:text-slate-400'}`}>
        {label}
      </p>
      <p className="mt-5 text-4xl font-bold tracking-tight text-slate-950 dark:text-white">{value}</p>
    </Card>
  )
}
