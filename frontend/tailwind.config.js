/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      screens: {
        xs: '420px',
      },
      colors: {
        // Brand — azure blue
        brand: {
          50:  '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        // Surfaces — deep blue-tinted dark scale
        surface: {
          900: '#0a0e1a',   // page background
          800: '#101725',   // cards
          750: '#141c2e',   // elevated cards / hover
          700: '#1a2336',   // inputs, inner surfaces
          600: '#26314a',   // default borders
          500: '#39476a',   // strong borders / hover borders
          400: '#8e9ab8',   // muted text
          300: '#b3bdd6',   // secondary text
          200: '#d3daeb',   // near-white text
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-glow': 'pulseGlow 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(59,130,246,0.45)' },
          '50%': { boxShadow: '0 0 0 8px rgba(59,130,246,0)' },
        },
      },
    },
  },
  plugins: [],
}
