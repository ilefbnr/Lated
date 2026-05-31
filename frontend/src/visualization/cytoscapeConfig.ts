// =============================================================================
// visualization/cytoscapeConfig.ts — Cytoscape options + stylesheet
// =============================================================================

import type { LayoutOptions } from 'cytoscape';

import { palette } from '@/themes/tokens';

// Cytoscape accepts both `style: {...}` and `css: {...}` selector objects at
// runtime. The @types/cytoscape namespace alias is awkward to import here, so
// we define a minimal local shape good enough for our static stylesheet.
export interface StyleRule {
  selector: string;
  style: Record<string, unknown>;
}

export const cyStylesheet: StyleRule[] = [
  {
    selector: 'node',
    style: {
      'background-color': palette.cyan,
      label: 'data(label)',
      color: palette.ink,
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 6,
      'font-size': 10,
      'font-family': 'JetBrains Mono, monospace',
      'text-opacity': 0,
      'text-background-color': '#09111d',
      'text-background-opacity': 0,
      'text-background-padding': 3,
      width: 28,
      height: 28,
      'border-width': 1,
      'border-color': palette.outline,
      'transition-property': 'background-color, border-color, width, height, text-opacity',
      'transition-duration': 180,
    },
  },
  {
    selector: 'node.node-hover',
    style: {
      'text-opacity': 1,
      'text-background-opacity': 0.85,
      'border-color': palette.neon,
      'border-width': 2,
      'z-index': 999,
    },
  },
  {
    selector: 'node.attack-host, node.pivot, node.risk-critical',
    style: {
      'text-opacity': 1,
      'text-background-opacity': 0.7,
    },
  },
  {
    selector: 'node.risk-low',
    style: { 'background-color': palette.sev.low, 'border-color': palette.sev.low },
  },
  {
    selector: 'node.risk-medium',
    style: { 'background-color': palette.sev.medium, 'border-color': palette.sev.medium },
  },
  {
    selector: 'node.risk-high',
    style: { 'background-color': palette.sev.high, 'border-color': palette.sev.high },
  },
  {
    selector: 'node.risk-critical',
    style: {
      'background-color': palette.sev.critical,
      'border-color': palette.sev.critical,
      width: 34,
      height: 34,
    },
  },
  {
    selector: 'node.pivot',
    style: {
      'border-width': 4,
      'border-color': palette.neon,
      'border-style': 'double',
      width: 38,
      height: 38,
    },
  },
  // -------- Network zone accents (subtle border tint, risk takes priority) --
  {
    selector: 'node.zone-datacenter',
    style: { 'border-color': palette.zone.datacenter, 'border-width': 2 },
  },
  {
    selector: 'node.zone-dmz',
    style: { 'border-color': palette.zone.dmz, 'border-width': 2 },
  },
  {
    selector: 'node.zone-iot',
    style: { 'border-color': palette.zone.iot, 'border-width': 2 },
  },
  {
    selector: 'node.zone-ot',
    style: { 'border-color': palette.zone.ot, 'border-width': 2 },
  },
  {
    selector: 'node.zone-public-owned',
    style: { 'border-color': palette.zone.public_owned, 'border-width': 2 },
  },
  {
    selector: 'node.zone-partner',
    style: { 'border-color': palette.zone.partner, 'border-width': 2 },
  },
  {
    selector: 'node.zone-external',
    style: {
      'border-color': palette.zone.external,
      'border-width': 2,
      'border-style': 'dashed',
    },
  },
  // -------- Critical asset (gold halo, slightly larger) --------------------
  {
    selector: 'node.critical-asset',
    style: {
      shape: 'diamond',
      width: 34,
      height: 34,
      'border-color': palette.critical,
      'border-width': 3,
      'overlay-color': palette.critical,
      'overlay-opacity': 0.18,
      'overlay-padding': 6,
    },
  },
  {
    selector: 'node.attack-host',
    style: {
      'border-width': 3,
      'border-color': palette.violet,
      color: palette.neon,
      'font-weight': 700,
    },
  },
  {
    selector: 'edge',
    style: {
      'curve-style': 'bezier',
      'line-color': palette.cyan,
      'target-arrow-color': palette.cyan,
      'target-arrow-shape': 'triangle',
      'arrow-scale': 1,
      width: 1.8,
      opacity: 0.72,
      label: 'data(label)',
      color: palette.ink,
      'font-size': 9,
      'font-family': 'JetBrains Mono, monospace',
      'text-background-color': '#09111d',
      'text-background-opacity': 0,
      'text-background-padding': 3,
      'text-border-opacity': 0,
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
      'text-opacity': 0,
      'overlay-padding': 8,
    },
  },
  {
    selector: 'edge.edge-internal',
    style: {
      'line-color': '#22d3ee',
      'target-arrow-color': '#22d3ee',
      width: 2.4,
      opacity: 0.95,
    },
  },
  {
    selector: 'edge.edge-external',
    style: {
      'line-color': '#fb923c',
      'target-arrow-color': '#fb923c',
      width: 3,
      opacity: 1,
      'line-style': 'dotted',
    },
  },
  {
    selector: 'edge[?suspicion]',
    style: {
      'line-color': palette.violet,
      'target-arrow-color': palette.violet,
      opacity: 0.82,
    },
  },
  {
    selector: 'edge.attack-path',
    style: {
      'line-color': palette.sev.critical,
      'target-arrow-color': palette.sev.critical,
      width: 3.5,
      opacity: 1,
      'line-style': 'dashed',
      'line-dash-pattern': [8, 4],
      'line-dash-offset': 0,
    },
  },
  {
    selector: 'edge.edge-hover',
    style: {
      'line-color': palette.neon,
      'target-arrow-color': palette.neon,
      width: 4.2,
      opacity: 1,
      'text-opacity': 1,
      'text-background-opacity': 0.9,
      'text-border-opacity': 0.35,
      'text-border-color': palette.neon,
      'z-index': 999,
    },
  },
  {
    selector: ':selected',
    style: { 'border-color': palette.neon, 'border-width': 4 },
  },
];

export const cyDefaultLayout: LayoutOptions = {
  name: 'fcose',
  animate: false,
  quality: 'default',
  randomize: true,
  nodeRepulsion: 8000,
  idealEdgeLength: 120,
  edgeElasticity: 0.25,
  gravity: 0.35,
  gravityRange: 3.8,
  nestingFactor: 1.0,
  numIter: 2500,
  tile: true,
  tilingPaddingVertical: 18,
  tilingPaddingHorizontal: 18,
  packComponents: true,
  nodeDimensionsIncludeLabels: false,
} as unknown as LayoutOptions;

/** Bucket a numeric risk [0,1] into a node class for styling. */
export function riskBucketClass(risk: number | undefined): string {
  const r = typeof risk === 'number' ? risk : 0;
  if (r >= 0.75) return 'risk-critical';
  if (r >= 0.5) return 'risk-high';
  if (r >= 0.25) return 'risk-medium';
  return 'risk-low';
}

/**
 * Map a backend `zone` value to a Cytoscape class. Returns `null` for the
 * default zone (corporate/unknown) so we don't emit redundant classes.
 */
export function zoneClass(zone: string | undefined | null): string | null {
  if (!zone) return null;
  switch (zone) {
    case 'datacenter':   return 'zone-datacenter';
    case 'dmz':          return 'zone-dmz';
    case 'iot':          return 'zone-iot';
    case 'ot':           return 'zone-ot';
    case 'public_owned': return 'zone-public-owned';
    case 'partner':      return 'zone-partner';
    case 'external':     return 'zone-external';
    default:             return null; // corporate / unknown -> baseline style
  }
}
