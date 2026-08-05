// API types matching backend schemas from 06-chat-and-api.md

export type ExplanationLevel = 'beginner' | 'intermediate' | 'advanced';

export interface DeckSaveRequest {
  content: string;
  filename?: string;
}

export interface DeckSaveResponse {
  deck_path: string;
}

/** One .DATA deck on the server, from GET /api/files. */
export interface DeckEntry {
  name: string;
  path: string;
  size: number;
  has_includes: boolean;
}

export interface DeckListResponse {
  root: string;
  parent: string | null;
  roots: string[];
  dirs: string[];
  decks: DeckEntry[];
  truncated: boolean;
}

export interface UploadResponse {
  deck_path: string;
  include_dir: string | null;
  byte_count: number;
}

export interface BuildRequest {
  description: string;
  output_path?: string;
  use_llm?: boolean;
  fluid?: FluidDescriptorRequest | null;
  // Stage 3.2: optional rock-basics overrides. null/undefined means
  // "use whatever the offline extractor produced"; a number/list means
  // "the user has confirmed or replaced this value before generating".
  porosity?: number | null;
  top_depth?: number | null;
  initial_pressure?: number | null;
  dz?: number[] | null;
  permx?: number[] | null;
  permy?: number[] | null;
  permz?: number[] | null;
}

export interface FluidDescriptorRequest {
  api_gravity: number;
  gas_specific_gravity: number;
  gor: number;
  reservoir_temp_f?: number;
  reservoir_temp_c?: number;
  salinity_ppm?: number;
  pressure_range_psi: [number, number];
  unit_system?: 'FIELD' | 'METRIC';
  // User-selected oil PVT correlation family. Null/undefined means
  // "use the default" (currently Standing on the backend).
  correlation?: 'Standing' | 'VasquezBeggs' | 'AlMarhoun' | null;
}

export interface LintIssue {
  severity: 'ERROR' | 'WARNING' | 'INFO';
  section: string | null;
  keyword: string | null;
  line: number | null;
  message: string;
  rule_id: string | null;
}

export interface LintResult {
  deck_path: string;
  issues: LintIssue[];
  lint_summary: string | null;
  errors: string[];
  passed: boolean;
}

export interface BuildResponse {
  deck: string;
  lint: LintResult;
  // Provenance per rock-basics field: where the resolved value came from.
  // Values: "extracted" | "defaulted" | "user_override" | "required_missing".
  provenance: Record<string, string>;
  // Final resolved values the UI can show next to the provenance tag.
  resolved: Record<string, number | number[]>;
}

export interface LintRequest {
  deck_path: string;
}

export interface RunRequest {
  deck_path: string;
  timeout?: number;
}

export type JobStatusValue = 'pending' | 'running' | 'completed' | 'failed';

export interface JobStatus {
  job_id: string;
  status: JobStatusValue;
  result?: SimulationResult | null;
  error?: string | null;
}

export interface SimulationResultDTO {
  success: boolean;
  output_dir: string;
  crash_report: CrashReportDTO | null;
  returncode: number | null;
  duration_s: number;
  stdout: string;
  stderr: string;
  warnings: string[];
  summary_files: Record<string, string>;
  prt_path: string | null;
}

export interface CrashReportDTO {
  keyword: string | null;
  line: number | null;
  message: string;
}

export interface SimulationResult {
  output_dir: string;
  success: boolean;
  stdout: string;
  stderr: string;
  return_code: number;
}

export interface KPIsResponse {
  kpis: Record<string, any>;
  plots: Record<string, string>; // plot_name -> Plotly JSON (fig.to_json())
  viewer_available?: boolean; // True if /api/results/{id}/resinsight can launch a GUI
}

// Snapshots types
export interface SnapshotsResponse {
  success: boolean;
  snapshots: string[]; // PNG filenames, served at /results/{job_id}/snapshots/{name}
  error: string | null;
  duration_s: number;
}

// ResInsight GUI launch (localhost-gated; non-loopback returns 403)
export interface ResinsightLaunchResponse {
  launched: boolean;
  pid: number | null;
  reason: string | null; // e.g. "already running" when launched=false
  error: string | null;
}

// ============================================
// 3D grid viewer (docs/3d-viewer-contract.md section 1)
// ============================================

export interface GridTimeStep {
  index: number;
  report: number;
  days: number;
  date: string;
}

export interface GridBBox {
  min: [number, number, number];
  max: [number, number, number];
}

export interface GridInfoResponse {
  nx: number;
  ny: number;
  nz: number;
  active_cells: number;
  total_cells: number;
  unit_system: string; // "METRIC" | "FIELD" | "" when unknown
  length_unit: string; // ft | m | cm
  origin: [number, number, number];
  bbox: GridBBox; // viewer coords: origin subtracted, Z negated
  static_properties: string[];
  dynamic_properties: string[];
  derived_properties: string[];
  time_steps: GridTimeStep[];
  fault_face_count: number;
  nnc_count: number;
  has_wells: boolean;
}

export interface GridPropertyRangeResponse {
  name: string;
  min: number;
  max: number;
  steps_scanned: number;
}

export type GridWellType =
  | 'producer'
  | 'oil_injector'
  | 'gas_injector'
  | 'water_injector'
  | 'unknown';

export interface GridWellCompletion {
  i: number; // zero-based
  j: number;
  k: number;
  cell: number;
  center: [number, number, number];
  open: boolean;
}

export interface GridWell {
  name: string;
  type: GridWellType;
  head: [number, number, number];
  i: number; // zero-based head cell
  j: number;
  k: number;
  trajectory: [number, number, number][];
  completions: GridWellCompletion[];
}

export interface GridWellsResponse {
  step: number;
  wells: GridWell[];
}

export type ChatRole = 'user' | 'assistant' | 'tool';

export interface ChatMessage {
  role: ChatRole;
  content: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}

export interface ChatRequest {
  messages: ChatMessage[];
  session_id: string;
}

// WebSocket message types for chat
export interface WSClientMessage {
  messages: ChatMessage[];
  session_id: string;
}

export type WSServerMessage =
  | { type: 'token'; content: string }
  | { type: 'tool_call'; tool_name: string; arguments: Record<string, unknown>; tool_call_id: string }
  // result is the raw dict returned by execute_tool, not a string
  | { type: 'tool_result'; tool_name: string; tool_call_id: string; result: Record<string, unknown> }
  | { type: 'error'; message: string }
  | { type: 'done' };

// API error response
export interface ApiError {
  detail: string;
}

// Generic fetch options
export interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

// Settings
export interface Settings {
  groqApiKey: string;
  openaiApiKey: string;
  nimApiKey: string;
  nimBaseUrl: string;
  llmProvider: 'groq' | 'openai' | 'nim' | 'offline';
}

// Backend runtime settings API (POST/GET /api/settings).
// Keys are write-only: sent to the local backend, held in process memory,
// never persisted or echoed back. GET returns booleans only.
export interface SettingsUpdateRequest {
  provider: 'groq' | 'openai' | 'nim' | 'offline';
  groq_api_key?: string;
  openai_api_key?: string;
  nvidia_nim_api_key?: string;
}

export interface SettingsResponse {
  provider: string;
  active_provider: string;
  keys_configured: {
    groq: boolean;
    openai: boolean;
    nim: boolean;
  };
}

// Explainer types
export interface ExplainRequest {
  topic?: string | null;
  kpis?: Record<string, any> | null;
  level: ExplanationLevel;
  context?: Record<string, any> | null;
}

export interface Citation {
  source_id: string;
  title: string;
  url_or_path: string;
  snippet: string;
}

export interface ExplainResponse {
  topic: string;
  level: ExplanationLevel;
  text: string;
  citations: Citation[];
  follow_up_questions: string[];
}

export interface QuizQuestion {
  question: string;
  options: [string, string, string, string];
  correct_index: number;
  explanation: string;
  level: ExplanationLevel;
  topic_tags: string[];
}

export interface QuizRequest {
  scenario_summary: string;
  level?: ExplanationLevel;
  n_questions?: number;
  topic_focus?: string[] | null;
}

export interface QuizResponse {
  scenario_summary: string;
  questions: QuizQuestion[];
}

export interface LearningReportRequest {
  session_id: string;
  conversation_history: Record<string, any>[];
  kpis_history?: Record<string, any>[] | null;
}

export interface LearningReportResponse {
  session_id: string;
  topics_covered: string[];
  explanations_generated: number;
  questions_asked: number;
  quiz_scores: Record<string, number> | null;
  key_concepts: string[];
  citations_used: Citation[];
  markdown: string;
}