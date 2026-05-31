// =============================================================================
// tailwind.config.ts — LateD SOC theme tokens
// =============================================================================
//
// PURPOSE
// -------
// Single source of truth for the visual language of the SOC dashboard.
// Defines:
//   - color palette (dark + neon cyber accents),
//   - typography stack (Inter + JetBrains Mono for telemetry),
//   - spacing scale,
//   - blur + shadow utilities for glassmorphism panels,
//   - animation curves used by Framer Motion variants.
//
// DESIGN INSPIRATION
// ------------------
// CrowdStrike Falcon, Microsoft Defender XDR, SentinelOne, Cortex XDR,
// Elastic Security. The platform should LOOK like a high-end SOC product
// at first glance: dark canvas, neon highlights, generous spacing.
// =============================================================================

import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{ts,tsx}',
    './src/components/**/*.{ts,tsx}',
    './src/layouts/**/*.{ts,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Base canvas
        canvas:    '#070A12',  // near-black, slightly cool
        surface:   '#0E1320',  // panel backgrounds
        elevated:  '#141A2B',
        outline:   '#1F2942',
        outlineStrong: '#2A375F',
        // Text
        ink:       '#E6EAF3',
        muted:     '#7C8AA9',
        // Cyber accents
        cyan:      '#22D3EE',
        neon:      '#7DF9FF',
        violet:    '#A78BFA',
        brand:     '#A78BFA',
        brandStrong: '#B79CFF',
        brandBlue: '#6F7CF7',
        // Severity ladder (matches Severity enum on backend)
        sev: {
          info:     '#60A5FA',
          low:      '#34D399',
          medium:   '#FBBF24',
          high:     '#FB923C',
          critical: '#F43F5E',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow:  '0 0 24px rgba(167, 139, 250, 0.28)',
        panel: '0 8px 32px rgba(0, 0, 0, 0.45)',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #B79CFF 0%, #8B6BF0 45%, #6F7CF7 100%)',
        'cyber-gradient': 'linear-gradient(135deg, #22D3EE 0%, #7DF9FF 100%)',
      },
      backdropBlur: {
        glass: '18px',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 12px rgba(34,211,238,0.4)' },
          '50%':       { boxShadow: '0 0 32px rgba(34,211,238,0.75)' },
        },
        scan: {
          '0%':   { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
      animation: {
        pulseGlow: 'pulseGlow 2.4s ease-in-out infinite',
        scan:      'scan 6s linear infinite',
      },
    },
  },
  plugins: [],
};

export default config;
