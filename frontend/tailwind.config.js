/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      screens: {
        xs: '420px',
      },
      colors: {
        brand: {
          50:  '#f0fdf4',
          100: '#dcfce7',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          900: '#14532d',
        },
        surface: {
          900: '#0f1117',
          800: '#161b22',
          700: '#1c2333',
          600: '#21262d',
          500: '#30363d',
          400: '#484f58',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-green': 'pulseGreen 1.5s ease-in-out infinite',
        'count-up': 'countUp 0.6s ease-out',
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
        pulseGreen: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(34,197,94,0.4)' },
          '50%': { boxShadow: '0 0 0 8px rgba(34,197,94,0)' },
        },
      },
    },
  },
  plugins: [],
}
