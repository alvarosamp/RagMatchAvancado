export default function ProductMark({ className = 'h-11 w-11', title = 'Edital Matcher' }) {
  return (
    <span
      className={`inline-grid flex-shrink-0 place-items-center overflow-hidden rounded-xl bg-gradient-to-br from-blue-700 via-blue-600 to-cyan-500 text-white shadow-sm ${className}`}
      role="img"
      aria-label={title}
    >
      <svg viewBox="0 0 48 48" className="h-[68%] w-[68%]" fill="none" aria-hidden="true">
        <path d="M12 15.5 24 9l12 6.5L24 22 12 15.5Z" fill="currentColor" />
        <path
          d="m12 23 12 6.5L36 23M12 30.5 24 37l12-6.5"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}
