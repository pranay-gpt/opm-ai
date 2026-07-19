// API types matching backend schemas from 06-chat-and-api.md

export interface BuildRequest {
  description: string;
  output_path?: string;
}

export interface LintResult {
  deck_path: string;
  errors: string[];
  passed: boolean;
}

export interface BuildResponse {
  deck: string;
  lint: LintResult;
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
  | { type: 'tool_call'; tool_call: ToolCall }
  | { type: 'tool_result'; tool_call_id: string; result: string }
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
  nimApiKey: string;
  nimBaseUrl: string;
  llmProvider: 'groq' | 'nim' | 'offline';
}