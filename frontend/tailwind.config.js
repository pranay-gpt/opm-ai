/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        base: '#0A1628',
        surface: '#0F2642',
        surfaceHover: '#153050',
        border: '#1A3A5A',
        primary: '#00D9FF',
        primaryHover: '#33E0FF',
        primaryMuted: '#00D9FF20',
        textPrimary: '#FFFFFF',
        textSecondary: '#A0AEC0',
        textMuted: '#6B7B8D',
        muted: '#6B7B8D',
        success: '#00C853',
        warning: '#FFB020',
        warningMuted: '#FFB02020',
        error: '#FF5252',
        errorMuted: '#FF525220',
      },
    },
  },
  plugins: [],
}