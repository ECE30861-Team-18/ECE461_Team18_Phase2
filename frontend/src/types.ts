// Generated from OpenAPI spec for ECE 461 Fall 2025 Project Phase 2

export type ArtifactType = 'model' | 'dataset' | 'code';

export type ArtifactID = string;

export type ArtifactName = string;

export type AuthenticationToken = string;

export type HealthStatus = 'ok' | 'degraded' | 'critical' | 'unknown';

export type AuditAction = 'CREATE' | 'UPDATE' | 'DOWNLOAD' | 'RATE' | 'AUDIT';

export interface User {
  name: string;
  is_admin: boolean;
}

export interface UserAuthenticationInfo {
  password: string;
}

export interface AuthenticationRequest {
  user: User;
  secret: UserAuthenticationInfo;
}

export interface ArtifactMetadata {
  name: ArtifactName;
  id: ArtifactID;
  type: ArtifactType;
}

export interface ArtifactData {
  url: string;
  download_url?: string;
}

export interface Artifact {
  metadata: ArtifactMetadata;
  data: ArtifactData;
}

export interface ArtifactQuery {
  name: ArtifactName;
  types?: ArtifactType[];
}

export interface ArtifactRegEx {
  regex: string;
}

export interface ArtifactAuditEntry {
  user: User;
  date: string;
  artifact: ArtifactMetadata;
  action: AuditAction;
}

export interface ArtifactCostDetails {
  standalone_cost?: number;
  total_cost: number;
}

export interface ArtifactCost {
  [artifactId: string]: ArtifactCostDetails;
}

export interface ArtifactLineageNode {
  artifact_id: ArtifactID;
  name: string;
  source: string;
  metadata?: Record<string, any>;
}

export interface ArtifactLineageEdge {
  from_node_artifact_id: ArtifactID;
  to_node_artifact_id: ArtifactID;
  relationship: string;
}

export interface ArtifactLineageGraph {
  nodes: ArtifactLineageNode[];
  edges: ArtifactLineageEdge[];
}

export interface SimpleLicenseCheckRequest {
  github_url: string;
}

export interface SizeScore {
  raspberry_pi: number;
  jetson_nano: number;
  desktop_pc: number;
  aws_server: number;
}

export interface ModelRating {
  name: string;
  category: string;
  net_score: number;
  net_score_latency: number;
  ramp_up_time: number;
  ramp_up_time_latency: number;
  bus_factor: number;
  bus_factor_latency: number;
  performance_claims: number;
  performance_claims_latency: number;
  license: number;
  license_latency: number;
  dataset_and_code_score: number;
  dataset_and_code_score_latency: number;
  dataset_quality: number;
  dataset_quality_latency: number;
  code_quality: number;
  code_quality_latency: number;
  reproducibility: number;
  reproducibility_latency: number;
  reviewedness: number;
  reviewedness_latency: number;
  tree_score: number;
  tree_score_latency: number;
  size_score: SizeScore;
  size_score_latency: number;
}

export interface HealthRequestSummary {
  window_start: string;
  window_end: string;
  total_requests?: number;
  per_route?: Record<string, number>;
  per_artifact_type?: Record<string, number>;
  unique_clients?: number;
}

export interface HealthComponentBrief {
  id: string;
  display_name?: string;
  status: HealthStatus;
  issue_count?: number;
  last_event_at?: string;
}

export interface HealthMetricValue {
  value: number | string | boolean;
}

export interface HealthTimelineEntry {
  bucket: string;
  value: number;
  unit?: string;
}

export interface HealthIssue {
  code: string;
  severity: 'info' | 'warning' | 'error';
  summary: string;
  details?: string;
}

export interface HealthLogReference {
  label: string;
  url: string;
  tail_available?: boolean;
  last_updated_at?: string;
}

export interface HealthComponentDetail {
  id: string;
  display_name?: string;
  status: HealthStatus;
  observed_at: string;
  description?: string;
  metrics?: Record<string, HealthMetricValue>;
  issues?: HealthIssue[];
  timeline?: HealthTimelineEntry[];
  logs?: HealthLogReference[];
}

export interface HealthComponentCollection {
  components: HealthComponentDetail[];
  generated_at: string;
  window_minutes?: number;
}

export interface TracksResponse {
  plannedTracks: Array<
    'Performance track' | 
    'Access control track' | 
    'High assurance track' | 
    'Other Security track'
  >;
}

// API Response types
export interface ApiError {
  message: string;
  status: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  offset?: string;
}