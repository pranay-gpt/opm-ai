import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { useShallow } from 'zustand/react/shallow';
import type { ChatMessage, JobStatus, LintResult, KPIsResponse, SimulationResult, BuildResponse, Settings } from '../types';

// ============================================
// Settings Store
// ============================================

interface SettingsState {
  settings: Settings;
  setGroqApiKey: (key: string) => void;
  setOpenaiApiKey: (key: string) => void;
  setNimApiKey: (key: string) => void;
  setNimBaseUrl: (url: string) => void;
  setLLMProvider: (provider: 'groq' | 'openai' | 'nim' | 'offline') => void;
  updateSettings: (settings: Partial<Settings>) => void;
}

const DEFAULT_SETTINGS: Settings = {
  groqApiKey: '',
  openaiApiKey: '',
  nimApiKey: '',
  nimBaseUrl: 'https://integrate.api.nvidia.com/v1',
  llmProvider: 'offline',
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      settings: DEFAULT_SETTINGS,

      setGroqApiKey: (key) => set((state) => ({ settings: { ...state.settings, groqApiKey: key } })),
      setOpenaiApiKey: (key) => set((state) => ({ settings: { ...state.settings, openaiApiKey: key } })),
      setNimApiKey: (key) => set((state) => ({ settings: { ...state.settings, nimApiKey: key } })),
      setNimBaseUrl: (url) => set((state) => ({ settings: { ...state.settings, nimBaseUrl: url } })),
      setLLMProvider: (provider) => set((state) => ({ settings: { ...state.settings, llmProvider: provider } })),
      updateSettings: (newSettings) => set((state) => ({ settings: { ...state.settings, ...newSettings } })),
    }),
    {
      name: 'opm-ai-settings',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ settings: { llmProvider: state.settings.llmProvider } }),
    }
  )
);

// ============================================
// Chat Store
// ============================================

interface ChatState {
  messages: ChatMessage[];
  sessionId: string;
  isConnected: boolean;
  isStreaming: boolean;
  addMessage: (message: ChatMessage) => void;
  updateLastMessage: (partial: Partial<ChatMessage>) => void;
  clearChat: () => void;
  setConnected: (connected: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setSessionId: (id: string) => void;
}

const generateSessionId = () => `session-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      sessionId: generateSessionId(),
      isConnected: false,
      isStreaming: false,

      addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),

      updateLastMessage: (partial) =>
        set((state) => {
          if (state.messages.length === 0) return state;
          const updated = [...state.messages];
          updated[updated.length - 1] = { ...updated[updated.length - 1], ...partial };
          return { messages: updated };
        }),

      clearChat: () => set({ messages: [], sessionId: generateSessionId() }),
      setConnected: (connected) => set({ isConnected: connected }),
      setStreaming: (streaming) => set({ isStreaming: streaming }),
      setSessionId: (id) => set({ sessionId: id }),
    }),
    {
      name: 'opm-ai-chat',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ sessionId: state.sessionId }),
    }
  )
);

// ============================================
// Deck Store
// ============================================

interface DeckState {
  currentDeck: string | null;
  currentDeckPath: string | null;
  lastBuildResponse: BuildResponse | null;
  lastDeckPath: string | null;
  setCurrentDeck: (deck: string | null, path?: string | null) => void;
  setLastBuildResponse: (response: BuildResponse | null) => void;
  setLastDeckPath: (path: string) => void;
}

export const useDeckStore = create<DeckState>()(
  persist(
    (set) => ({
      currentDeck: null,
      currentDeckPath: null,
      lastBuildResponse: null,
      lastDeckPath: null,

      setCurrentDeck: (deck, path = null) => set({ currentDeck: deck, currentDeckPath: path }),
      setLastBuildResponse: (response) => set({ lastBuildResponse: response }),
      setLastDeckPath: (path) => set({ lastDeckPath: path }),
    }),
    {
      name: 'opm-ai-deck',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ currentDeck: state.currentDeck, currentDeckPath: state.currentDeckPath, lastBuildResponse: state.lastBuildResponse, lastDeckPath: state.lastDeckPath }),
    }
  )
);

// ============================================
// Lint Store
// ============================================

interface LintState {
  lastLintResult: LintResult | null;
  setLastLintResult: (result: LintResult | null) => void;
}

export const useLintStore = create<LintState>()(
  persist(
    (set) => ({
      lastLintResult: null,
      setLastLintResult: (result) => set({ lastLintResult: result }),
    }),
    {
      name: 'opm-ai-lint',
      storage: createJSONStorage(() => localStorage),
    }
  )
);

// ============================================
// Simulation Store
// ============================================

interface SimulationState {
  currentJob: JobStatus | null;
  jobHistory: JobStatus[];
  lastResults: KPIsResponse | null;
  setCurrentJob: (job: JobStatus | null) => void;
  addToHistory: (job: JobStatus) => void;
  updateJobInHistory: (jobId: string, updates: Partial<JobStatus>) => void;
  setLastResults: (results: KPIsResponse | null) => void;
}

export const useSimulationStore = create<SimulationState>()(
  persist(
    (set) => ({
      currentJob: null,
      jobHistory: [],
      lastResults: null,

      setCurrentJob: (job) => set({ currentJob: job }),
      addToHistory: (job) => set((state) => ({ jobHistory: [job, ...state.jobHistory].slice(0, 50) })),
      updateJobInHistory: (jobId, updates) =>
        set((state) => ({
          jobHistory: state.jobHistory.map((j) => (j.job_id === jobId ? { ...j, ...updates } : j)),
          currentJob: state.currentJob?.job_id === jobId ? { ...state.currentJob, ...updates } : state.currentJob,
        })),
      setLastResults: (results) => set({ lastResults: results }),
    }),
    {
      name: 'opm-ai-simulation',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ jobHistory: state.jobHistory, lastResults: state.lastResults }),
    }
  )
);

// ============================================
// UI Store
// ============================================

interface UIState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));

// ============================================
// Selectors for convenience
// ============================================

// Settings
export const useLLMProvider = () => useSettingsStore((state) => state.settings.llmProvider);
export const useSettings = () => useSettingsStore((state) => state.settings);
export const useSettingsActions = () => useSettingsStore(useShallow((state) => ({
  setGroqApiKey: state.setGroqApiKey,
  setOpenaiApiKey: state.setOpenaiApiKey,
  setNimApiKey: state.setNimApiKey,
  setNimBaseUrl: state.setNimBaseUrl,
  setLLMProvider: state.setLLMProvider,
  updateSettings: state.updateSettings,
})));

// Chat
export const useChatMessages = () => useChatStore((state) => state.messages);
export const useChatSessionId = () => useChatStore((state) => state.sessionId);
export const useChatConnected = () => useChatStore((state) => state.isConnected);
export const useChatStreaming = () => useChatStore((state) => state.isStreaming);
export const useChatActions = () => useChatStore(useShallow((state) => ({
  addMessage: state.addMessage,
  updateLastMessage: state.updateLastMessage,
  clearChat: state.clearChat,
  setConnected: state.setConnected,
  setStreaming: state.setStreaming,
  setSessionId: state.setSessionId,
})));

// Deck
export const useCurrentDeck = () => useDeckStore((state) => state.currentDeck);
export const useCurrentDeckPath = () => useDeckStore((state) => state.currentDeckPath);
export const useLastBuildResponse = () => useDeckStore((state) => state.lastBuildResponse);
export const useLastDeckPath = () => useDeckStore((state) => state.lastDeckPath);
export const useDeckActions = () => useDeckStore(useShallow((state) => ({
  setCurrentDeck: state.setCurrentDeck,
  setLastBuildResponse: state.setLastBuildResponse,
  setLastDeckPath: state.setLastDeckPath,
})));

// Lint
export const useLastLintResult = () => useLintStore((state) => state.lastLintResult);
export const useLintActions = () => useLintStore(useShallow((state) => ({
  setLastLintResult: state.setLastLintResult,
})));

// Simulation
export const useCurrentJob = () => useSimulationStore((state) => state.currentJob);
export const useJobHistory = () => useSimulationStore((state) => state.jobHistory);
export const useLastResults = () => useSimulationStore((state) => state.lastResults);
export const useSimulationActions = () => useSimulationStore(useShallow((state) => ({
  setCurrentJob: state.setCurrentJob,
  addToHistory: state.addToHistory,
  updateJobInHistory: state.updateJobInHistory,
  setLastResults: state.setLastResults,
})));

// UI
export const useSidebarOpen = () => useUIStore((state) => state.sidebarOpen);
export const useUIActions = () => useUIStore(useShallow((state) => ({
  toggleSidebar: state.toggleSidebar,
  setSidebarOpen: state.setSidebarOpen,
})));