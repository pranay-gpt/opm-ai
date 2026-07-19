import { useUIStore, useLLMProvider } from '../stores/useAppStore';

const navItems = [
  { path: '/', label: 'Home', icon: '🏠' },
  { path: '/deck-builder', label: 'Deck Builder', icon: '📋' },
  { path: '/deck-editor', label: 'Deck Editor', icon: '📝' },
  { path: '/simulator', label: 'Simulator', icon: '⚙️' },
  { path: '/results', label: 'Results', icon: '📊' },
  { path: '/chat', label: 'AI Chat', icon: '💬' },
  { path: '/linter', label: 'Linter', icon: '🔍' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
] as const;

const getPanelFromPath = (path: string) => path.slice(1) || 'home';

export default function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const { activePanel, setActivePanel } = useUIStore();
  const llmProvider = useLLMProvider();

  return (
    <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-4 lg:px-6">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 rounded-md text-textSecondary hover:text-textPrimary hover:bg-surfaceHover transition-colors"
          aria-label="Toggle sidebar"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div className="hidden lg:flex items-center gap-1 bg-base/50 rounded-md p-1 border border-border">
          {navItems.map((item) => (
            <button
              key={item.path}
              onClick={() => setActivePanel(getPanelFromPath(item.path) as any)}
              className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                activePanel === getPanelFromPath(item.path)
                  ? 'text-primary bg-primaryMuted border-b-2 border-primary'
                  : 'text-textSecondary hover:text-textPrimary hover:bg-surfaceHover'
              }`}
            >
              <span className="text-base">{item.icon}</span>
              <span className="hidden sm:inline">{item.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* LLM Provider Indicator */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface border border-border">
          <span className="text-xs text-textSecondary uppercase tracking-wider">Provider:</span>
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              llmProvider === 'groq'
                ? 'bg-primary/20 text-primary'
                : llmProvider === 'nim'
                ? 'bg-success/20 text-success'
                : 'bg-warning/20 text-warning'
            }`}
          >
            {llmProvider.toUpperCase()}
          </span>
        </div>

        {/* Connection Status */}
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse-glow" />
          <span className="text-xs text-textSecondary hidden sm:inline">Connected</span>
        </div>
      </div>
    </header>
  );
}