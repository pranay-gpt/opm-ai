import type {
  BuildRequest,
  BuildResponse,
  LintRequest,
  LintResult,
  RunRequest,
  JobStatus,
  KPIsResponse,
  SnapshotsResponse,
  ResinsightLaunchResponse,
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
  DeckEntry,
  DeckListResponse,
  UploadResponse,
  GridInfoResponse,
  GridTimeStep,
  GridBBox,
  GridPropertyRangeResponse,
  GridWell,
  GridWellType,
  GridWellCompletion,
  GridWellsResponse,
  CategorizedVectors,
  PlotGroupResponse,
  CsvFrequency,
  VectorGroup,
  ImportedResultResponse,
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

// Multipart POST for /api/upload_deck. The browser sets the
// Content-Type with the correct `boundary=` parameter itself when
// the body is a FormData; setting it manually would either lose
// the boundary (parser rejects the body) or send a wrong one
// (server-side parser refuses). So this helper explicitly does
// NOT set Content-Type.
async function fetchMultipart<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: form,
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  return response.json();
}

export const api = {
  // Deck saving
  saveDeck: (request: DeckSaveRequest): Promise<DeckSaveResponse> =>
    fetchJson<DeckSaveResponse>('/decks', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // Browse decks on the server. Returns real paths, so a deck keeps its
  // include/ siblings and its relative INCLUDE paths still resolve.
  listDecks: (path?: string): Promise<DeckListResponse> =>
    fetchJson<DeckListResponse>(
      path ? `/files?path=${encodeURIComponent(path)}` : '/files'
    ),

  // Upload a deck (.DATA) plus an optional include/ folder from
  // the user's laptop. The backend writes them to a fresh mkdtemp
  // and returns the deck's server-side path, which the caller
  // feeds into run() unchanged.
  uploadDeck: (form: FormData): Promise<UploadResponse> =>
    fetchMultipart<UploadResponse>('/upload_deck', form),

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

  runStatus: (jobId: string, signal?: AbortSignal): Promise<JobStatus> =>
    fetchJson<JobStatus>(`/run/${jobId}`, { signal }),

  // Results
  results: (jobId: string): Promise<KPIsResponse> =>
    fetchJson<KPIsResponse>(`/results/${jobId}`),

  // Snapshots
  snapshots: (jobId: string): Promise<SnapshotsResponse> =>
    fetchJson<SnapshotsResponse>(`/results/${jobId}/snapshots`),

  // ResInsight GUI launch (localhost-gated). Returns {launched, pid, reason, error}.
  launchResinsight: (jobId: string): Promise<ResinsightLaunchResponse> =>
    fetchJson<ResinsightLaunchResponse>(`/results/${jobId}/resinsight`, { method: 'POST' }),

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

  // Results page enrichment (Task 4)
  categories: (jobId: string): Promise<CategorizedVectors> =>
    fetchJson<CategorizedVectors>(`/results/${jobId}/categories`),

  plotGroup: (
    jobId: string,
    group: string,
    opts: { wells?: string[]; vectors?: string[]; log?: boolean; unit_system?: 'FIELD' | 'METRIC'; per_property?: boolean } = {}
  ): Promise<PlotGroupResponse> => {
    const params = new URLSearchParams();
    if (opts.wells?.length) params.set('wells', opts.wells.join(','));
    if (opts.vectors?.length) params.set('vectors', opts.vectors.join(','));
    if (opts.log) params.set('log', 'true');
    if (opts.unit_system) params.set('unit_system', opts.unit_system);
    if (opts.per_property) params.set('per_property', 'true');
    const qs = params.toString();
    return fetchJson<PlotGroupResponse>(`/results/${jobId}/plot_group/${group}${qs ? `?${qs}` : ''}`);
  },

  csv: async (
    jobId: string,
    opts: { group: string; vectors: string[]; freq?: CsvFrequency }
  ): Promise<string> => {
    const params = new URLSearchParams();
    params.set('group', opts.group);
    params.set('vectors', opts.vectors.join(','));
    if (opts.freq && opts.freq !== 'native') params.set('freq', opts.freq);
    const response = await fetch(`${API_BASE}/results/${jobId}/csv?${params.toString()}`, {
      headers: { Accept: 'text/csv' },
    });
    if (!response.ok) {
      throw await errorFromResponse(response);
    }
    return response.text();
  },

  // Results page enrichment (Task 8) - Import Results
  importResults: async (formData: FormData): Promise<ImportedResultResponse> => {
    const response = await fetch(`${API_BASE}/imported-results`, {
      method: 'POST',
      body: formData,
      // No Content-Type — browser sets multipart boundary automatically
    });
    if (!response.ok) {
      throw await errorFromResponse(response);
    }
    return response.json() as Promise<ImportedResultResponse>;
  },

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

// Poll job status until completed or failed. The optional AbortSignal
// lets the caller cancel in-flight polls on unmount; without it, a
// pending poll leaks setTimeout handles and re-renders `onUpdate` against
// a dead store.
export async function pollJobStatus(
  jobId: string,
  onUpdate?: (status: JobStatus) => void,
  intervalMs = 2000,
  maxAttempts = 300,
  signal?: AbortSignal
): Promise<JobStatus> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    if (signal?.aborted) {
      throw new DOMException('Polling aborted', 'AbortError');
    }

    const status = await api.runStatus(jobId, signal);
    onUpdate?.(status);

    if (status.status === 'completed' || status.status === 'failed') {
      return status;
    }

    await new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, intervalMs);
      // Abort the sleep so a cancelled poll does not block the next
      // attempt check.
      signal?.addEventListener(
        'abort',
        () => {
          clearTimeout(timer);
          reject(new DOMException('Polling aborted', 'AbortError'));
        },
        { once: true }
      );
    });
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
  DeckEntry,
  DeckListResponse,
  GridInfoResponse,
  GridTimeStep,
  GridBBox,
  GridPropertyRangeResponse,
  GridWell,
  GridWellType,
  GridWellCompletion,
  GridWellsResponse,
  CategorizedVectors,
  PlotGroupResponse,
  CsvFrequency,
  VectorGroup,
  ImportedResultResponse,
};

// ============================================
// WebSocket Chat Client
// ============================================

export interface ChatCallbacks {
  onToken?: (content: string) => void;
  onToolCall?: (toolCall: ToolCall) => void;
  onToolResult?: (toolCallId: string, result: Record<string, unknown> | string) => void;
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