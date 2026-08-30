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
        // ── Tokens legados — agrupados no namespace "ink" para não conflitar ──
        // com as paletas padrão do Tailwind (slate, green, red, amber, yellow)
        ink: {
          DEFAULT: '#080808',
          50:      '#141414',
          100:     '#0F0F0F',
          card:    '#111111',  // ex slate.card
          border:  '#2A2A2A',  // ex slate.border
          hover:   '#1A1A1A',  // ex slate.hover
        },
        // ── Mantido para compatibilidade com main.jsx (border-azure/30) ─────
        azure:  { DEFAULT: '#1F3F68', dim: '#16304F', glow: '#3B6EA5' },
        // ── Padrão comercial (BI Editais e telas restilizadas) ────────────
        brand: {
          DEFAULT: '#1f3f68', light: '#3B6EA5', dark: '#16304F',
          match: '#10B981', 'match-dim': '#065F46',
          fail: '#EF4444', 'fail-dim': '#7F1D1D',
          warn: '#EAB308', 'warn-dim': '#713F12',
        },
        surface: { DEFAULT: '#F7F8FA', dark: '#0F172A' },
      },
      animation: {
        'fade-up':   'fadeUp 0.4s ease forwards',
        'pulse-dot': 'pulseDot 1.4s ease-in-out infinite',
        'scan':      'scan 2s linear infinite',
        'progress':  'progress 0.6s ease forwards',
      },
      keyframes: {
        fadeUp:   { '0%': { opacity: 0, transform: 'translateY(12px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        pulseDot: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } },
        scan:     { '0%': { transform: 'translateY(-100%)' }, '100%': { transform: 'translateY(100vh)' } },
        progress: { '0%': { width: '0%' }, '100%': { width: 'var(--progress)' } },
      },
    },
  },
  plugins: [],
}
