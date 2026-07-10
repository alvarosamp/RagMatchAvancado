/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['DM Sans', 'sans-serif'],
        body:    ['DM Sans', 'sans-serif'],
        mono:    ['JetBrains Mono', 'monospace'],
      },
      colors: {
        ink:    { DEFAULT: '#080808', 50: '#141414', 100: '#0F0F0F' },
        slate:  { card: '#111111', border: '#2A2A2A', hover: '#1A1A1A' },
        azure:  { DEFAULT: '#1F3F68', dim: '#16304F', glow: '#3B6EA5' },
        amber:  { DEFAULT: '#F0F0F0', dim: '#D4D4D4', glow: '#FFFFFF' },
        green:  { match: '#10B981', dim: '#065F46' },
        red:    { fail: '#EF4444',   dim: '#7F1D1D' },
        yellow: { warn: '#EAB308',   dim: '#713F12' },
        // ── Padrão comercial (BI Editais e telas restilizadas) ────────────
        // Navy usado em barras/gráficos de dados — distinto do vermelho da
        // marca (usado em ações primárias/navegação). surface é o fundo
        // neutro sólido que substitui o gradiente com glow.
        brand:   { DEFAULT: '#1f3f68', light: '#3B6EA5', dark: '#16304F' },
        surface: { DEFAULT: '#F7F8FA', dark: '#0F172A' },
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
