// =============================================================================
// types/graph.ts — Graph shapes consumed by Cytoscape
// =============================================================================
// Designed to match Cytoscape's element shape so the data layer doesn't
// need a transform step. This keeps the attack-graph page snappy.
// =============================================================================

export interface GraphNode {
  data: {
    id: string;                // host_id
    label?: string;            // hostname || host_id
    risk: number;              // 0..1
    compromised?: boolean;
    pivot?: boolean;
    subnet?: string | null;
    hostname?: string | null;
    ip_addresses?: string[];
    first_seen?: string;
    last_seen?: string;
    os_guess?: string | null;
    gateway?: boolean;
    service?: boolean;
    external?: boolean;
  };
}

export interface GraphEdge {
  data: {
    id: string;                // `${src}->${dst}@${tsBucket}`
    source: string;
    target: string;
    label?: string;
    weight?: number;           // visual weight (bytes-derived)
    suspicion?: number;        // 0..1
    src_ports?: number[];
    dst_ports?: number[];
    protocols?: string[];
    service_labels?: string[];
    external?: boolean;
    connection_type?: 'internal' | 'external' | string;
    onAttackPath?: boolean;
    pathId?: string;
  };
}

export interface GraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  generated_at: string;
  summary?: {
    host_count: number;
    edge_count: number;
    subnet_count: number;
    subnets: Array<{ cidr: string; host_count: number }>;
    gateway_host_ids: string[];
    service_host_ids: string[];
  };
}
