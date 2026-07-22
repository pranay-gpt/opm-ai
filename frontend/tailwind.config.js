/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Named 'page' (not 'base') so text-base stays the font-size utility
        page:          'rgb(var(--c-base) / <alpha-value>)',
        surface:       'rgb(var(--c-surface) / <alpha-value>)',
        surfaceHover:  'rgb(var(--c-surface-hover) / <alpha-value>)',
        border:        'rgb(var(--c-border) / <alpha-value>)',
        primary:       'rgb(var(--c-primary) / <alpha-value>)',
        primaryHover:  'rgb(var(--c-primary-hover) / <alpha-value>)',
        primaryMuted:  'rgb(var(--c-primary) / 0.12)',
        textPrimary:   'rgb(var(--c-text-primary) / <alpha-value>)',
        textSecondary: 'rgb(var(--c-text-secondary) / <alpha-value>)',
        textMuted:     'rgb(var(--c-text-muted) / <alpha-value>)',
        muted:         'rgb(var(--c-text-muted) / <alpha-value>)',
        success:       'rgb(var(--c-success) / <alpha-value>)',
        successMuted:  'rgb(var(--c-success) / 0.12)',
        warning:       'rgb(var(--c-warning) / <alpha-value>)',
        warningMuted:  'rgb(var(--c-warning) / 0.12)',
        error:         'rgb(var(--c-error) / <alpha-value>)',
        errorMuted:    'rgb(var(--c-error) / 0.12)',
        sidebarBg:     'rgb(var(--c-sidebar) / <alpha-value>)',
      },
    },
  },
  plugins: [],
}
