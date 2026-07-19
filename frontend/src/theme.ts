// Theme constants extracted from UI_DESIGN_SPEC.md
// Reference: docs/Reference_UI.png (4-panel dashboard)

export const theme = {
  // Core palette (Dark Blue / Cyan technical theme)
  colors: {
    // Base backgrounds
    base: '#0A1628',           // Main background - very dark blue
    surface: '#0F2642',        // Card/surface background - slightly lighter
    surfaceHover: '#153050',   // Hover state for surfaces
    border: '#1A3A5A',         // Subtle borders

    // Primary accent
    primary: '#00D9FF',        // Cyan - primary actions, links, active states
    primaryHover: '#33E0FF',   // Hover state for primary
    primaryMuted: '#00D9FF20', // Subtle backgrounds with primary tint

    // Text
    textPrimary: '#FFFFFF',    // Headings, primary text
    textSecondary: '#A0AEC0',  // Body text, secondary info
    textMuted: '#6B7B8D',      // Muted text, placeholders
    textInverse: '#0A1628',    // Text on primary backgrounds

    // Status colors
    success: '#00C853',        // Green - validation passed, success states
    successMuted: '#00C85320', // Success backgrounds
    warning: '#FFB020',        // Yellow - warnings, attention needed
    warningMuted: '#FFB02020', // Warning backgrounds
    error: '#FF4444',          // Red - errors, critical issues
    errorMuted: '#FF444420',   // Error backgrounds

    // Syntax highlighting (Monaco editor)
    syntax: {
      keyword: '#00D9FF',      // Keywords: RUNSPEC, GRID, PROPS, etc.
      comment: '#4EC9B0',      // Comments (-- ...) - teal/green
      number: '#DCDCAA',       // Numbers - yellow/orange
      string: '#CE9178',       // Strings - orange/tan
      operator: '#D4D4D4',     // Operators
      punctuation: '#D4D4D4',  // Punctuation
      identifier: '#9CDCFE',   // Identifiers/variables
      function: '#DCDCAA',     // Function calls
      type: '#4EC9B0',         // Type names
    },

    // Chart colors (Plotly dark theme compatible)
    chart: {
      primary: '#00D9FF',      // Primary line
      secondary: '#FFFFFF',    // Secondary line
      tertiary: '#FFB020',     // Third line
      quaternary: '#00C853',   // Fourth line
      heatmap: ['#0A1628', '#004E89', '#0080FF', '#00D9FF', '#4EFFD0', '#A8FF78', '#FFF700', '#FF8C00', '#FF0000'], // Blue-cyan-green-yellow-red
      grid: '#1A3A5A',         // Grid lines
      axis: '#A0AEC0',         // Axis labels
    },

    // UI specific
    sidebarBg: '#08101E',      // Sidebar background (darker than base)
    headerBg: '#08101E',       // Top header background
    inputBg: '#0A1628',        // Input backgrounds
    inputBorder: '#1A3A5A',    // Input borders
    inputFocus: '#00D9FF',     // Input focus ring
    badge: '#00D9FF',          // Badge background (OG Banges style)
    badgeText: '#0A1628',      // Badge text
    scrollbarThumb: '#1A3A5A', // Scrollbar thumb
    scrollbarTrack: '#0A1628', // Scrollbar track
  },

  // Spacing scale
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },

  // Border radius
  radius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    full: '9999px',
  },

  // Shadows
  shadows: {
    sm: '0 1px 2px rgba(0, 0, 0, 0.3)',
    md: '0 4px 6px rgba(0, 0, 0, 0.4)',
    lg: '0 10px 15px rgba(0, 0, 0, 0.5)',
    glow: '0 0 20px rgba(0, 217, 255, 0.3)',
    glowSubtle: '0 0 10px rgba(0, 217, 255, 0.15)',
  },

  // Typography
  typography: {
    fontFamily: {
      sans: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      mono: '"JetBrains Mono", "Fira Code", "Monaco", "Consolas", monospace',
    },
    fontSize: {
      xs: '11px',
      sm: '13px',
      base: '14px',
      lg: '16px',
      xl: '18px',
      '2xl': '22px',
      '3xl': '28px',
      '4xl': '36px',
    },
    fontWeight: {
      normal: '400',
      medium: '500',
      semibold: '600',
      bold: '700',
    },
    lineHeight: {
      tight: '1.25',
      normal: '1.5',
      relaxed: '1.75',
    },
  },

  // Transitions
  transitions: {
    fast: '150ms ease',
    normal: '200ms ease',
    slow: '300ms ease',
  },

  // Z-index layers
  zIndex: {
    dropdown: 100,
    sticky: 200,
    modal: 300,
    popover: 400,
    tooltip: 500,
    toast: 600,
  },

  // Breakpoints
  breakpoints: {
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px',
  },
} as const;

// Type exports for TypeScript
export type Theme = typeof theme;
export type ColorKey = keyof typeof theme.colors;
export type SpacingKey = keyof typeof theme.spacing;

// CSS custom properties generator (for runtime theming if needed)
export function generateCSSVariables(themeObj: Theme = theme): string {
  const vars: string[] = [];

  function flatten(obj: Record<string, any>, prefix = ''): void {
    for (const [key, value] of Object.entries(obj)) {
      const newKey = prefix ? `${prefix}-${key}` : key;
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        flatten(value, newKey);
      } else {
        vars.push(`--${newKey}: ${value};`);
      }
    }
  }

  flatten(themeObj.colors);
  flatten(themeObj.spacing, 'space');
  flatten(themeObj.radius, 'radius');
  flatten(themeObj.shadows, 'shadow');
  flatten(themeObj.typography.fontSize, 'text');
  flatten(themeObj.typography.fontWeight, 'font');
  flatten(themeObj.typography.lineHeight, 'leading');
  flatten(themeObj.transitions, 'transition');
  flatten(themeObj.zIndex, 'z');
  flatten(themeObj.breakpoints, 'breakpoint');

  return `:root { ${vars.join(' ')} }`;
}

// Export default for convenience
export default theme;