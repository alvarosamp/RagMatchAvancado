/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        body:    ['DM Sans', 'sans-serif'],
        mono:    ['JetBrains Mono', 'monospace'],
      },
      colors: {
        ink:    { DEFAULT: '#0B0F1A', 50: '#1A2035', 100: '#131929' },
        slate:  { card: '#141929', border: '#1E2A42', hover: '#1C2438' },
        azure:  { DEFAULT: '#3B82F6', dim: '#1D4ED8', glow: '#60A5FA' },
        amber:  { DEFAULT: '#F59E0B', dim: '#B45309', glow: '#FCD34D' },
        green:  { match: '#10B981', dim: '#065F46' },
        red:    { fail: '#EF4444',   dim: '#7F1D1D' },
        yellow: { warn: '#EAB308',   dim: '#713F12' },
      },
      animation: {
        'fade-up':   'fadeUp 0.4s ease forwards',
        'pulse-dot': 'pulseDot 1.4s ease-in-out infinite',
        'scan':      'scan 2s linear infinite',
        'progress':  'progress 0.6s ease forwards',
      },
      keyframes: {
        fadeUp:    { '0%': { opacity: 0, transform: 'translateY(12px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        pulseDot:  { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } },
        scan:      { '0%': { transform: 'translateY(-100%)' }, '100%': { transform: 'translateY(100vh)' } },
        progress:  { '0%': { width: '0%' }, '100%': { width: 'var(--progress)' } },
      },
    },
  },
  plugins: [],
}
