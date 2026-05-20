export interface DiscoveryRunResult {
  status: string;
  job_id: string;
  source_kind: string;
  source_value: string;
  resolved_source_path: string;
  started_at: string;
  completed_at: string;
  generated_at: string;
  host_count: number;
  edge_count: number;
  subnet_count: number;
  gateway_count: number;
  service_count: number;
  baseline_path: string;
  registry_path: string;
}

export interface DiscoveryUploadResult {
  status: string;
  filename: string;
  stored_path: string;
}
