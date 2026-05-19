// =============================================================================
// themes/cyberTheme.ts — Framer Motion variants + reusable motion presets
// =============================================================================
//
// PURPOSE
// -------
// Houses the motion vocabulary used across the SOC dashboard so animations
// feel consistent ("alerts fade in the same way everywhere"):
//   - fadeUp        : card / panel entrance
//   - pulseGlow     : threat indicator
//   - pathDraw      : SVG attack-path drawing
//   - sweep         : scanning line over loading panels
//
// CYBERSECURITY UX REASONING
// --------------------------
// Animations carry meaning in a SOC product. Sudden uncoordinated motion
// is fatiguing. Centralizing variants here keeps timings/easings unified,
// which makes the dashboard feel "engineered" rather than "flashy".
// =============================================================================

import type { Variants } from 'framer-motion';

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1, y: 0,
    transition: { duration: 0.35, ease: [0.22, 0.61, 0.36, 1] },
  },
};

export const stagger = (delay = 0.05): Variants => ({
  hidden: {},
  visible: { transition: { staggerChildren: delay } },
});

export const pulseGlow: Variants = {
  rest:   { boxShadow: '0 0 12px rgba(34,211,238,0.35)' },
  active: {
    boxShadow: ['0 0 12px rgba(34,211,238,0.35)', '0 0 32px rgba(34,211,238,0.75)', '0 0 12px rgba(34,211,238,0.35)'],
    transition: { duration: 2.4, repeat: Infinity, ease: 'easeInOut' },
  },
};

export const pathDraw: Variants = {
  hidden:  { pathLength: 0, opacity: 0.0 },
  visible: { pathLength: 1, opacity: 1.0, transition: { duration: 1.2, ease: 'easeInOut' } },
};
