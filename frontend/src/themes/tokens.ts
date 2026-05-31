// =============================================================================
// themes/tokens.ts — design tokens
// =============================================================================
//
// PURPOSE
// -------
// Mirrors the Tailwind theme into TypeScript constants so visualization code
// (Cytoscape, D3) — which doesn't read Tailwind classes — can use the same
// palette. Single source of truth, two consumers.
//
// CONVENTION
// ----------
// Whenever a color is added/changed in tailwind.config.ts, mirror it here.
// =============================================================================

export const palette = {
  canvas:   '#070A12',
  surface:  '#0E1320',
  elevated: '#141A2B',
  outline:  '#1F2942',
  ink:      '#E6EAF3',
  muted:    '#7C8AA9',
  cyan:     '#22D3EE',
  neon:     '#7DF9FF',
  violet:   '#A78BFA',
  sev: {
    info:     '#60A5FA',
    low:      '#34D399',
    medium:   '#FBBF24',
    high:     '#FB923C',
    critical: '#F43F5E',
  },
  // Network-zone accents. Used as a SECONDARY visual cue (border tint) so
  // risk colors stay dominant. Tuned to remain readable on the dark canvas.
  zone: {
    corporate:    '#22D3EE',  // cyan — matches default node accent
    dmz:          '#A78BFA',  // violet
    datacenter:   '#F472B6',  // pink — flags sensitive infrastructure
    iot:          '#34D399',  // green
    ot:           '#FDE047',  // yellow
    public_owned: '#38BDF8',  // sky
    partner:      '#FB7185',  // rose
    external:     '#FB923C',  // orange — matches existing edge-external
    unknown:      '#64748B',  // slate
  },
  // Critical asset marker: warm gold ring around DC / SQL prod / jump hosts.
  critical: '#FFD43B',
} as const;

export type SeverityKey = keyof typeof palette.sev;

/** Map a backend Severity value to a palette color. */
export function severityColor(sev: SeverityKey): string {
  return palette.sev[sev];
}
