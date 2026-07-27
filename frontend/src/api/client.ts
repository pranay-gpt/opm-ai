import type {
  BuildRequest,
  BuildResponse,
  LintRequest,
  LintResult,
  RunRequest,
  JobStatus,
  KPIsResponse,
  SnapshotsResponse,
  ChatMessage,
  WSServerMessage,
  ToolCall,
  Settings,
  SettingsUpdateRequest,
  SettingsResponse,
  ExplainRequest,
  ExplainResponse,
  QuizRequest,
  QuizResponse,
  LearningReportRequest,
  LearningReportResponse,
  FluidDescriptorRequest,
  ExplanationLevel,
  Citation,
  QuizQuestion,
  LintIssue,
  DeckSaveRequest,
  DeckSaveResponse,
  GridInfoResponse,
  GridTimeStep,
  GridBBox,
  GridPropertyRangeResponse,
  GridWell,
  GridWellType,
  GridWellCompletion,
  GridWellsResponse,
} from '../types';

// ============================================
// HTTP API Client
// ============================================

const API_BASE = '/api';

// Read the body once as text; a second read would fail (stream consumed)
async function errorFromResponse(response: Response): Promise<Error> {
  let errorDetail = response.statusText;
  try {
    const errorText = await response.text();
    try {
      errorDetail = JSON.parse(errorText).detail || errorText || errorDetail;
    } catch {
      errorDetail = errorText || errorDetail;
    }
  } catch {
    // Fall back to status text
  }
  return new Error(errorDetail || `HTTP ${response.status}: ${response.statusText}`);
}

async function fetchJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// Sibling of fetchJson for the 3D viewer's binary mesh/property payloads.
// Sends no JSON Content-Type and returns the raw bytes.
async function fetchBinary(path: string, options: RequestInit = {}): Promise<ArrayBuffer> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { Accept: 'application/octet-stream', ...options.headers },
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  return response.arrayBuffer();
}

export const api = {
  // Deck saving
  saveDeck: (request: DeckSaveRequest): Promise<DeckSaveResponse> =>
    fetchJson<DeckSaveResponse>('/decks', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // Build
  build: (request: BuildRequest): Promise<BuildResponse> =>
    fetchJson<BuildResponse>('/build', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // Lint
  lint: (request: LintRequest): Promise<LintResult> =>
    fetchJson<LintResult>('/lint', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // Run
  run: (request: RunRequest): Promise<JobStatus> =>
    fetchJson<JobStatus>('/run', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  runStatus: (jobId: string): Promise<JobStatus> =>
    fetchJson<JobStatus>(`/run/${jobId}`),

  // Results
  results: (jobId: string): Promise<KPIsResponse> =>
    fetchJson<KPIsResponse>(`/results/${jobId}`),

  // Snapshots
  snapshots: (jobId: string): Promise<SnapshotsResponse> =>
    fetchJson<SnapshotsResponse>(`/results/${jobId}/snapshots`),

  // 3D grid viewer. Binary endpoints accept a signal so the UI can abort
  // in-flight requests while the user scrubs the time-step slider.
  gridInfo: (jobId: string, signal?: AbortSignal): Promise<GridInfoResponse> =>
    fetchJson<GridInfoResponse>(`/results/${jobId}/grid/info`, { signal }),

  gridMesh: (jobId: string, includeInactive = false, signal?: AbortSignal): Promise<ArrayBuffer> =>
    fetchBinary(
      `/results/${jobId}/grid/mesh?include_inactive=${includeInactive ? 'true' : 'false'}`,
      { signal }
    ),

  // Per-active-cell companion to the mesh: i/j/k, centres, fault faces, NNCs.
  // Independent of include_inactive, so it is fetched once per job.
  gridCells: (jobId: string, signal?: AbortSignal): Promise<ArrayBuffer> =>
    fetchBinary(`/results/${jobId}/grid/cells`, { signal }),

  gridProperty: (
    jobId: string,
    name: string,
    step: number,
    signal?: AbortSignal
  ): Promise<ArrayBuffer> =>
    fetchBinary(
      `/results/${jobId}/grid/property?name=${encodeURIComponent(name)}&step=${step}`,
      { signal }
    ),

  gridPropertyRange: (
    jobId: string,
    name: string,
    signal?: AbortSignal
  ): Promise<GridPropertyRangeResponse> =>
    fetchJson<GridPropertyRangeResponse>(
      `/results/${jobId}/grid/property/range?name=${encodeURIComponent(name)}`,
      { signal }
    ),

  gridWells: (jobId: string, step = 0, signal?: AbortSignal): Promise<GridWellsResponse> =>
    fetchJson<GridWellsResponse>(`/results/${jobId}/grid/wells?step=${step}`, { signal }),

  // Explainer
  explainConcept: (request: ExplainRequest): Promise<ExplainResponse> =>
    fetchJson<ExplainResponse>('/explain', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  generateQuiz: (request: QuizRequest): Promise<QuizResponse> =>
    fetchJson<QuizResponse>('/quiz', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  learningReport: (request: LearningReportRequest): Promise<LearningReportResponse> =>
    fetchJson<LearningReportResponse>('/learning-report', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // Runtime settings (in-memory on the backend; keys never echoed back)
  getSettings: (): Promise<SettingsResponse> =>
    fetchJson<SettingsResponse>('/settings'),

  updateSettings: (request: SettingsUpdateRequest): Promise<SettingsResponse> =>
    fetchJson<SettingsResponse>('/settings', {
      method: 'POST',
      body: JSON.stringify(request),
    }),
};

// Poll job status until completed or failed
export async function pollJobStatus(
  jobId: string,
  onUpdate?: (status: JobStatus) => void,
  intervalMs = 2000,
  maxAttempts = 300
): Promise<JobStatus> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const status = await api.runStatus(jobId);
    onUpdate?.(status);

    if (status.status === 'completed' || status.status === 'failed') {
      return status;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error(`Job ${jobId} timed out after ${maxAttempts * intervalMs}ms`);
}

// Re-export types for components
export type {
  BuildRequest,
  BuildResponse,
  LintRequest,
  LintResult,
  LintIssue,
  RunRequest,
  JobStatus,
  KPIsResponse,
  SnapshotsResponse,
  ChatMessage,
  ToolCall,
  Settings,
  SettingsUpdateRequest,
  SettingsResponse,
  ExplainRequest,
  ExplainResponse,
  QuizRequest,
  QuizResponse,
  LearningReportRequest,
  LearningReportResponse,
  FluidDescriptorRequest,
  ExplanationLevel,
  Citation,
  QuizQuestion,
  DeckSaveRequest,
  DeckSaveResponse,
  GridInfoResponse,
  GridTimeStep,
  GridBBox,
  GridPropertyRangeResponse,
  GridWell,
  GridWellType,
  GridWellCompletion,
  GridWellsResponse,
};

// ============================================
// WebSocket Chat Client
// ============================================

export interface ChatCallbacks {
  onToken?: (content: string) => void;
  onToolCall?: (toolCall: ToolCall) => void;
  onToolResult?: (toolCallId: string, result: string) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
  onClose?: () => void;
}

export interface ChatConnection {
  send: (messages: ChatMessage[]) => void;
  close: () => void;
  isOpen: () => boolean;
}

export function connectChat(
  sessionId: string,
  messages: ChatMessage[],
  callbacks: ChatCallbacks
): ChatConnection {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/chat`;

  let ws: WebSocket | null = null;
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closedByUser = false;
  let pendingSend: string | null = null;
  const maxReconnectAttempts = 5;
  const reconnectDelay = 1000;

  function connect(): WebSocket {
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('[Chat] WebSocket connected');
      reconnectAttempts = 0;

      // Flush a message queued while (re)connecting, else send initial history
      const payload =
        pendingSend ?? JSON.stringify({ messages, session_id: sessionId });
      pendingSend = null;
      socket.send(payload);
    };

    socket.onmessage = (event) => {
      try {
        const data: WSServerMessage = JSON.parse(event.data);

        switch (data.type) {
          case 'token':
            callbacks.onToken?.(data.content);
            break;
          case 'tool_call': {
            const toolCall: ToolCall = {
              id: data.tool_call_id,
              type: 'function',
              function: {
                name: data.tool_name,
                arguments: JSON.stringify(data.arguments ?? {}),
              },
            };
            callbacks.onToolCall?.(toolCall);
            break;
          }
          case 'tool_result':
            callbacks.onToolResult?.(data.tool_call_id, data.result);
            break;
          case 'error':
            callbacks.onError?.(data.message);
            break;
          case 'done':
            callbacks.onDone?.();
            break;
        }
      } catch (error) {
        console.error('[Chat] Failed to parse message:', error);
      }
    };

    socket.onerror = (error) => {
      console.error('[Chat] WebSocket error:', error);
      callbacks.onError?.('Connection error');
    };

    socket.onclose = () => {
      console.log('[Chat] WebSocket closed');
      callbacks.onClose?.();

      // Reconnect unless the caller closed intentionally
      if (!closedByUser && reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          ws = connect();
        }, reconnectDelay * reconnectAttempts);
      }
    };

    return socket;
  }

  ws = connect();

  return {
    send: (newMessages: ChatMessage[]) => {
      const payload = JSON.stringify({
        messages: newMessages,
        session_id: sessionId,
      });
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(payload);
      } else {
        // Queue; onopen of the (re)connecting socket will flush it
        pendingSend = payload;
      }
    },
    close: () => {
      closedByUser = true;
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      ws?.close();
      ws = null;
    },
    isOpen: () => ws?.readyState === WebSocket.OPEN,
  };
}