import type {
  BuildRequest,
  BuildResponse,
  LintRequest,
  LintResult,
  RunRequest,
  JobStatus,
  KPIsResponse,
  ChatMessage,
  WSServerMessage,
  ToolCall,
  Settings,
} from '../types';

// ============================================
// HTTP API Client
// ============================================

const API_BASE = '/api';

async function fetchJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
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
  RunRequest,
  JobStatus,
  KPIsResponse,
  ChatMessage,
  ToolCall,
  Settings,
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
  const maxReconnectAttempts = 5;
  const reconnectDelay = 1000;

  function connect(): WebSocket {
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('[Chat] WebSocket connected');
      reconnectAttempts = 0;

      // Send initial message with session_id and messages
      socket.send(
        JSON.stringify({
          messages,
          session_id: sessionId,
        })
      );
    };

    socket.onmessage = (event) => {
      try {
        const data: WSServerMessage = JSON.parse(event.data);

        switch (data.type) {
          case 'token':
            callbacks.onToken?.(data.content);
            break;
          case 'tool_call':
            callbacks.onToolCall?.(data.tool_call);
            break;
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

      // Attempt reconnection
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        setTimeout(() => {
          ws = connect();
        }, reconnectDelay * reconnectAttempts);
      }
    };

    return socket;
  }

  ws = connect();

  return {
    send: (newMessages: ChatMessage[]) => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            messages: newMessages,
            session_id: sessionId,
          })
        );
      }
    },
    close: () => {
      ws?.close();
      ws = null;
    },
    isOpen: () => ws?.readyState === WebSocket.OPEN,
  };
}