// =============================================================================
// components/graph/AttackGraphCanvas.tsx
// =============================================================================
//
// Live Cytoscape canvas for the attack graph. Renders hosts as colored nodes
// (by risk bucket) and communications as edges. When an attack path is
// selected, the corresponding nodes + edges are highlighted with a dashed,
// animated stroke so the analyst sees propagation visually.
// =============================================================================

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Core, ElementDefinition } from 'cytoscape';
import CytoscapeComponent from 'react-cytoscapejs';

import type { GraphEdge, GraphNode } from '@/types/graph';

import { cyDefaultLayout, cyStylesheet, riskBucketClass } from '@/visualization/cytoscapeConfig';

export interface AttackGraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightedHostIds?: string[];
  highlightedEdgeIds?: string[];
  pivotHostIds?: string[];
}

interface EdgeTooltipState {
  x: number;
  y: number;
  sourceLabel: string;
  targetLabel: string;
  label: string;
  weight?: number;
  suspicion?: number;
  srcPorts: number[];
  dstPorts: number[];
  protocols: string[];
  serviceLabels: string[];
  onAttackPath?: boolean;
}

function inferServiceLabels(dstPorts: number[], protocols: string[]): string[] {
  const labels: string[] = [];
  const portMap: Record<number, string> = {
    22: 'SSH',
    53: 'DNS',
    80: 'HTTP',
    88: 'Kerberos',
    135: 'RPC',
    139: 'NetBIOS',
    389: 'LDAP',
    443: 'HTTPS',
    445: 'SMB',
    636: 'LDAPS',
    3389: 'RDP',
    5985: 'WinRM',
    5986: 'WinRM-TLS',
  };

  for (const port of dstPorts) {
    const label = portMap[port];
    if (label && !labels.includes(label)) labels.push(label);
  }

  if (labels.length === 0) {
    for (const protocol of protocols) {
      const value = protocol.toUpperCase();
      if (!labels.includes(value)) labels.push(value);
    }
  }

  return labels;
}

function toElements(
  nodes: GraphNode[],
  edges: GraphEdge[],
  highlightedHosts: Set<string>,
  highlightedEdges: Set<string>,
  pivots: Set<string>,
): ElementDefinition[] {
  const nodeElements: ElementDefinition[] = nodes.map((node) => {
    const classes = [riskBucketClass(node.data.risk)];
    if (pivots.has(node.data.id)) classes.push('pivot');
    if (highlightedHosts.has(node.data.id)) classes.push('attack-host');
    return {
      group: 'nodes',
      data: { ...node.data },
      classes: classes.join(' '),
    };
  });

  const edgeElements: ElementDefinition[] = edges.map((edge) => {
    const classes: string[] = [];
    const onPath =
      highlightedEdges.has(edge.data.id) ||
      (highlightedHosts.has(edge.data.source) && highlightedHosts.has(edge.data.target));
    if (onPath) classes.push('attack-path');
    const label = edge.data.label
      ?? [edge.data.source, edge.data.target].join(' -> ');
    return {
      group: 'edges',
      data: { ...edge.data, label },
      classes: classes.join(' '),
    };
  });

  return [...nodeElements, ...edgeElements];
}

export function AttackGraphCanvas({
  nodes,
  edges,
  highlightedHostIds = [],
  highlightedEdgeIds = [],
  pivotHostIds = [],
}: AttackGraphCanvasProps) {
  const cyRef = useRef<Core | null>(null);
  const animationRef = useRef<number | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<EdgeTooltipState | null>(null);

  const nodeLabelById = useMemo(
    () => new Map(nodes.map((node) => [node.data.id, node.data.label ?? node.data.id])),
    [nodes],
  );

  const elements = useMemo(
    () =>
      toElements(
        nodes,
        edges,
        new Set(highlightedHostIds),
        new Set(highlightedEdgeIds),
        new Set(pivotHostIds),
      ),
    [nodes, edges, highlightedHostIds, highlightedEdgeIds, pivotHostIds],
  );

  useEffect(() => {
    const cy = cyRef.current;
    if (cy === null) return;
    cy.layout(cyDefaultLayout).run();
    cy.fit(undefined, 40);
  }, [nodes.length, edges.length]);

  useEffect(() => {
    const cy = cyRef.current;
    if (cy === null) return;

    const handleMouseOver = (event: any) => {
      const edge = event.target;
      if (!('isEdge' in edge) || !edge.isEdge()) return;
      edge.addClass('edge-hover');

      const data = edge.data();
      const box = edge.renderedBoundingBox();
      const sourceId = String(data.source ?? '');
      const targetId = String(data.target ?? '');
      setHoveredEdge({
        x: box.x1 + ((box.x2 - box.x1) / 2),
        y: box.y1 + ((box.y2 - box.y1) / 2),
        sourceLabel: nodeLabelById.get(sourceId) ?? sourceId,
        targetLabel: nodeLabelById.get(targetId) ?? targetId,
        label: String(data.label ?? `${sourceId} -> ${targetId}`),
        weight: typeof data.weight === 'number' ? data.weight : undefined,
        suspicion: typeof data.suspicion === 'number' ? data.suspicion : undefined,
        srcPorts: Array.isArray(data.src_ports) ? data.src_ports.map(Number).filter(Number.isFinite) : [],
        dstPorts: Array.isArray(data.dst_ports) ? data.dst_ports.map(Number).filter(Number.isFinite) : [],
        protocols: Array.isArray(data.protocols) ? data.protocols.map(String) : [],
        serviceLabels: Array.isArray(data.service_labels)
          ? data.service_labels.map(String)
          : inferServiceLabels(
            Array.isArray(data.dst_ports) ? data.dst_ports.map(Number).filter(Number.isFinite) : [],
            Array.isArray(data.protocols) ? data.protocols.map(String) : [],
          ),
        onAttackPath: Boolean(data.onAttackPath),
      });
    };

    const handleMouseOut = (event: any) => {
      const edge = event.target;
      if (!('isEdge' in edge) || !edge.isEdge()) return;
      edge.removeClass('edge-hover');
      setHoveredEdge((current) => {
        if (current === null) return null;
        const data = edge.data();
        const label = String(data.label ?? `${data.source ?? ''} -> ${data.target ?? ''}`);
        return current.label === label ? null : current;
      });
    };

    const handleViewportChange = () => {
      setHoveredEdge(null);
    };

    cy.on('mouseover', 'edge', handleMouseOver);
    cy.on('mouseout', 'edge', handleMouseOut);
    cy.on('pan zoom', handleViewportChange);

    return () => {
      cy.off('mouseover', 'edge', handleMouseOver);
      cy.off('mouseout', 'edge', handleMouseOut);
      cy.off('pan zoom', handleViewportChange);
    };
  }, [elements, nodeLabelById]);

  useEffect(() => {
    const cy = cyRef.current;
    if (cy === null) return;
    if (animationRef.current !== null) {
      window.cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
    const start = performance.now();
    const tick = () => {
      const elapsed = (performance.now() - start) / 1000;
      const offset = (elapsed * 24) % 24;
      cy.edges('.attack-path').style('line-dash-offset', -offset);
      animationRef.current = window.requestAnimationFrame(tick);
    };
    if (cy.edges('.attack-path').nonempty()) tick();
    return () => {
      if (animationRef.current !== null) {
        window.cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
    };
  }, [highlightedHostIds, highlightedEdgeIds, elements]);

  return (
    <div className="glass relative w-full h-full overflow-hidden">
      {nodes.length === 0 ? (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-muted">
          No graph data yet.
        </div>
      ) : (
        <CytoscapeComponent
          elements={elements}
          stylesheet={cyStylesheet}
          layout={cyDefaultLayout}
          style={{ width: '100%', height: '100%' }}
          cy={(cy) => {
            cyRef.current = cy;
          }}
          autounselectify={false}
          boxSelectionEnabled={false}
          minZoom={0.25}
          maxZoom={3}
        />
      )}
      {hoveredEdge && (
        <div
          className="pointer-events-none absolute z-20 min-w-[230px] max-w-[320px] rounded-lg border border-cyan/40 bg-slate-950/95 px-3 py-2 shadow-2xl backdrop-blur"
          style={{
            left: Math.min(hoveredEdge.x + 14, window.innerWidth > 768 ? hoveredEdge.x + 14 : hoveredEdge.x),
            top: Math.max(hoveredEdge.y - 16, 12),
            transform: 'translate(0, -50%)',
          }}
        >
          <p className="text-[10px] uppercase tracking-[0.25em] text-cyan/80">Connection</p>
          <p className="mt-1 text-xs font-medium text-ink">
            {hoveredEdge.sourceLabel} <span className="text-muted">→</span> {hoveredEdge.targetLabel}
          </p>
          <p className="mt-1 text-[11px] text-muted">{hoveredEdge.label}</p>
          {hoveredEdge.serviceLabels.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {hoveredEdge.serviceLabels.map((service) => (
                <span
                  key={service}
                  className="rounded-full border border-cyan/40 bg-cyan/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan"
                >
                  {service}
                </span>
              ))}
            </div>
          )}
          <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-muted">
            <span>Weight</span>
            <span className="text-right font-mono text-ink">
              {hoveredEdge.weight !== undefined ? hoveredEdge.weight : '—'}
            </span>
            <span>Suspicion</span>
            <span className="text-right font-mono text-ink">
              {hoveredEdge.suspicion !== undefined ? `${(hoveredEdge.suspicion * 100).toFixed(0)}%` : '—'}
            </span>
            <span>Attack path</span>
            <span className="text-right font-mono text-ink">
              {hoveredEdge.onAttackPath ? 'yes' : 'no'}
            </span>
            <span>Ports</span>
            <span className="text-right font-mono text-ink">
              {hoveredEdge.dstPorts.length > 0 ? hoveredEdge.dstPorts.join(', ') : '—'}
            </span>
            <span>Protocol</span>
            <span className="text-right font-mono text-ink uppercase">
              {hoveredEdge.protocols.length > 0 ? hoveredEdge.protocols.join(', ') : '—'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
