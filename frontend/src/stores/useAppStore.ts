import { useEffect, useState } from 'react';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { useShallow } from 'zustand/react/shallow';
import type { ChatMessage, JobStatus, LintResult, KPIsResponse, SimulationResult, BuildResponse, Settings, FluidDescriptorRequest, CategorizedVectors } from '../types';

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
      // Persist messages with sessionId: server keeps history keyed by
      // sessionId, so an empty UI after reload would silently diverge.
      partialize: (state) => ({ sessionId: state.sessionId, messages: state.messages }),
      // Older builds stored raw tool_result objects as message content, which
      // React cannot render. Coerce on load so poisoned storage self-heals.
      merge: (persisted, current) => {
        const saved = persisted as Partial<ChatState> | undefined;
        const messages = (saved?.messages ?? []).map((m) =>
          typeof m.content === 'string' ? m : { ...m, content: JSON.stringify(m.content, null, 2) }
        );
        return { ...current, ...saved, messages };
      },
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
  categoriesByJob: Record<string, CategorizedVectors>;
  setCurrentJob: (job: JobStatus | null) => void;
  addToHistory: (job: JobStatus) => void;
  updateJobInHistory: (jobId: string, updates: Partial<JobStatus>) => void;
  setLastResults: (results: KPIsResponse | null) => void;
  setCategories: (jobId: string, cats: CategorizedVectors) => void;
  getCategories: (jobId: string) => CategorizedVectors | null;
}

export const useSimulationStore = create<SimulationState>()(
  persist(
    (set, get) => ({
      currentJob: null,
      jobHistory: [],
      lastResults: null,
      categoriesByJob: {},

      setCurrentJob: (job) => set({ currentJob: job }),
      addToHistory: (job) => set((state) => ({ jobHistory: [job, ...state.jobHistory].slice(0, 50) })),
      updateJobInHistory: (jobId, updates) =>
        set((state) => ({
          jobHistory: state.jobHistory.map((j) => (j.job_id === jobId ? { ...j, ...updates } : j)),
          currentJob: state.currentJob?.job_id === jobId ? { ...state.currentJob, ...updates } : state.currentJob,
        })),
      setLastResults: (results) => set({ lastResults: results }),
      setCategories: (jobId, cats) => set((s) => ({
        categoriesByJob: { ...s.categoriesByJob, [jobId]: cats },
      })),
      getCategories: (jobId) => get().categoriesByJob[jobId] ?? null,
    }),
    {
      name: 'opm-ai-simulation',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ jobHistory: state.jobHistory, lastResults: state.lastResults, currentJob: state.currentJob }),
    }
  )
);

// ============================================
// Builder Store
// ============================================
//
// Holds DeckBuilder form state so a route change does not wipe what the user
// typed. isBuilding and error stay LOCAL to the component - persisting them
// across a reload would strand the UI mid-flight.

// Rock-basics values the user can override between extraction and build.
// Each entry is null when the user hasn't touched the field; otherwise it
// is the user's confirmed value (a scalar for porosity/top_depth/
// initial_pressure, an array for dz/permx/permy/permz - one entry per layer).
// See Stage 3.2 in docs/superpowers/specs/2026-08-03-phase-2-design.md.
export interface RockBasicsOverrides {
  porosity: number | null;
  top_depth: number | null;
  initial_pressure: number | null;
  dz: number[] | null;
  permx: number[] | null;
  permy: number[] | null;
  permz: number[] | null;
}

const DEFAULT_ROCK_BASICS: RockBasicsOverrides = {
  porosity: null,
  top_depth: null,
  initial_pressure: null,
  dz: null,
  permx: null,
  permy: null,
  permz: null,
};

// Last resolved rock-basics values from a successful /api/build. The UI
// uses this to render the "what was actually generated" badge alongside
// the user's editable overrides. Keyed by the same names as
// RockBasicsOverrides.
export interface ResolvedRockBasics {
  porosity: number;
  top_depth: number;
  initial_pressure: number;
  dz: number[];
  permx: number[];
  permy: number[];
  permz: number[];
}

interface BuilderState {
  description: string;
  showEditor: boolean;
  useLlmExtraction: boolean;
  useCustomFluid: boolean;
  fluidProps: FluidDescriptorRequest;
  showFluidSection: boolean;
  rockBasicsOverrides: RockBasicsOverrides;
  resolvedRockBasics: ResolvedRockBasics | null;
  rockBasicsProvenance: Record<string, string>;
  showRockBasicsSection: boolean;
  setDescription: (s: string) => void;
  setShowEditor: (b: boolean) => void;
  setUseLlmExtraction: (b: boolean) => void;
  setUseCustomFluid: (b: boolean) => void;
  setFluidProps: (
    f: FluidDescriptorRequest | ((prev: FluidDescriptorRequest) => FluidDescriptorRequest),
  ) => void;
  setShowFluidSection: (b: boolean) => void;
  setRockBasicsOverride: <K extends keyof RockBasicsOverrides>(
    field: K,
    value: RockBasicsOverrides[K],
  ) => void;
  resetRockBasicsOverrides: () => void;
  setResolvedRockBasics: (
    resolved: ResolvedRockBasics,
    provenance: Record<string, string>,
  ) => void;
  setShowRockBasicsSection: (b: boolean) => void;
}

const DEFAULT_FLUID: FluidDescriptorRequest = {
  api_gravity: 35,
  gas_specific_gravity: 0.75,
  gor: 800,
  reservoir_temp_f: 200,
  salinity_ppm: 0,
  pressure_range_psi: [14.7, 5000],
  unit_system: 'FIELD',
  // Oil PVT correlation family surfaced in the Builder UI. Standing is
  // the canonical default and matches the historical deck output; users
  // can flip to VasquezBeggs or AlMarhoun via the fluid-card dropdown.
  correlation: 'Standing',
};

export const useBuilderStore = create<BuilderState>()(
  persist(
    (set) => ({
      description: '10x10x3 grid with one producer at 5,5, depletion drive, 3000m depth, 200 bar initial pressure',
      showEditor: false,
      useLlmExtraction: false,
      useCustomFluid: false,
      fluidProps: DEFAULT_FLUID,
      showFluidSection: false,
      rockBasicsOverrides: DEFAULT_ROCK_BASICS,
      resolvedRockBasics: null,
      rockBasicsProvenance: {},
      showRockBasicsSection: false,

      setDescription: (description) => set({ description }),
      setShowEditor: (showEditor) => set({ showEditor }),
      setUseLlmExtraction: (useLlmExtraction) => set({ useLlmExtraction }),
      setUseCustomFluid: (useCustomFluid) => set({ useCustomFluid }),
      setFluidProps: (updater) =>
        set((state) => ({
          fluidProps:
            typeof updater === 'function'
              ? (updater as (prev: FluidDescriptorRequest) => FluidDescriptorRequest)(state.fluidProps)
              : updater,
        })),
      setShowFluidSection: (showFluidSection) => set({ showFluidSection }),
      setRockBasicsOverride: (field, value) =>
        set((state) => ({
          rockBasicsOverrides: { ...state.rockBasicsOverrides, [field]: value },
        })),
      resetRockBasicsOverrides: () => set({ rockBasicsOverrides: { ...DEFAULT_ROCK_BASICS } }),
      setResolvedRockBasics: (resolvedRockBasics, rockBasicsProvenance) =>
        set({ resolvedRockBasics, rockBasicsProvenance }),
      setShowRockBasicsSection: (showRockBasicsSection) => set({ showRockBasicsSection }),
    }),
    {
      name: 'opm-ai-builder',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        description: state.description,
        showEditor: state.showEditor,
        useLlmExtraction: state.useLlmExtraction,
        useCustomFluid: state.useCustomFluid,
        fluidProps: state.fluidProps,
        showFluidSection: state.showFluidSection,
        // Persist overrides and section visibility; resolved values are
        // re-derived on the next build, no need to survive a reload.
        rockBasicsOverrides: state.rockBasicsOverrides,
        showRockBasicsSection: state.showRockBasicsSection,
      }),
    }
  )
);

// ============================================
// UI Store
// ============================================

interface UIState {
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  theme: 'dark' | 'light' | 'auto';
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebarCollapsed: () => void;
  setTheme: (theme: 'dark' | 'light' | 'auto') => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      sidebarCollapsed: false,
      theme: 'auto' as const,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebarCollapsed: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'opm-ai-ui',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ theme: state.theme }),
    }
  )
);

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
export const useCategoriesByJob = () => useSimulationStore((state) => state.categoriesByJob);
export const useCategoriesForJob = (jobId: string | undefined) => useSimulationStore((state) => jobId ? state.categoriesByJob[jobId] : null);
export const useSimulationActions = () => useSimulationStore(useShallow((state) => ({
  setCurrentJob: state.setCurrentJob,
  addToHistory: state.addToHistory,
  updateJobInHistory: state.updateJobInHistory,
  setLastResults: state.setLastResults,
  setCategories: state.setCategories,
  getCategories: state.getCategories,
})));

// UI
export const useSidebarOpen = () => useUIStore((state) => state.sidebarOpen);
export const useTheme = () => useUIStore((state) => state.theme);

// Resolved theme ('auto' collapsed to what the system prefers). Use for
// embedded widgets (Monaco, Plotly) that cannot read CSS variables.
export function useResolvedTheme(): 'dark' | 'light' {
  const theme = useTheme();
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches
  );
  useEffect(() => {
    if (theme !== 'auto') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [theme]);
  if (theme === 'auto') return systemDark ? 'dark' : 'light';
  return theme;
}
export const useUIActions = () => useUIStore(useShallow((state) => ({
  toggleSidebar: state.toggleSidebar,
  setSidebarOpen: state.setSidebarOpen,
  toggleSidebarCollapsed: state.toggleSidebarCollapsed,
  setTheme: state.setTheme,
})));

export const useSidebarCollapsed = () => useUIStore((state) => state.sidebarCollapsed);

// Builder selectors. Field selectors return stable primitives so they do NOT
// need useShallow (the zustand 5 selector returns api.getState(), a stable
// ref). The actions selector returns a fresh object literal, so it DOES need
// useShallow to avoid an identity-changed-every-render loop.
export const useBuilderDescription = () => useBuilderStore((state) => state.description);
export const useBuilderShowEditor = () => useBuilderStore((state) => state.showEditor);
export const useBuilderUseLlmExtraction = () => useBuilderStore((state) => state.useLlmExtraction);
export const useBuilderFluidProps = () => useBuilderStore((state) => state.fluidProps);
export const useBuilderUseCustomFluid = () => useBuilderStore((state) => state.useCustomFluid);
export const useBuilderShowFluidSection = () => useBuilderStore((state) => state.showFluidSection);
export const useRockBasicsOverrides = () => useBuilderStore((state) => state.rockBasicsOverrides);
export const useResolvedRockBasics = () => useBuilderStore((state) => state.resolvedRockBasics);
export const useRockBasicsProvenance = () => useBuilderStore((state) => state.rockBasicsProvenance);
export const useShowRockBasicsSection = () => useBuilderStore((state) => state.showRockBasicsSection);
export const useBuilderActions = () => useBuilderStore(useShallow((state) => ({
  setDescription: state.setDescription,
  setShowEditor: state.setShowEditor,
  setUseLlmExtraction: state.setUseLlmExtraction,
  setUseCustomFluid: state.setUseCustomFluid,
  setFluidProps: state.setFluidProps,
  setShowFluidSection: state.setShowFluidSection,
  setRockBasicsOverride: state.setRockBasicsOverride,
  resetRockBasicsOverrides: state.resetRockBasicsOverrides,
  setResolvedRockBasics: state.setResolvedRockBasics,
  setShowRockBasicsSection: state.setShowRockBasicsSection,
})));