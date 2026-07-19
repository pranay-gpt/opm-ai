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

export default function Sidebar() {
  const { activePanel, setActivePanel, sidebarOpen, setSidebarOpen } = useUIStore();
  const llmProvider = useLLMProvider();

  return (
    <>
      {/* Overlay for mobile */}
      <div
        className={`fixed inset-0 z-40 bg-base/80 backdrop-blur-sm lg:hidden transition-opacity ${
          sidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <aside
        className={`fixed lg:relative z-50 h-full w-64 bg-sidebarBg border-r border-border flex flex-col transition-transform duration-300 ease-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
        aria-label="Navigation"
      >
        {/* Logo / Brand */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center">
              <span className="text-base text-base font-bold">O</span>
            </div>
            <span className="text-lg font-semibold text-textPrimary">OPM-AI</span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1.5 rounded text-textSecondary hover:text-textPrimary hover:bg-surfaceHover"
            aria-label="Close sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" role="navigation">
          {navItems.map((item) => (
            <button
              key={item.path}
              onClick={() => {
                setActivePanel(getPanelFromPath(item.path) as any);
                setSidebarOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-all duration-150 ${
                activePanel === getPanelFromPath(item.path)
                  ? 'bg-primary/15 text-primary border-l-2 border-primary'
                  : 'text-textSecondary hover:text-textPrimary hover:bg-surfaceHover'
              }`}
            >
              <span className="text-base flex-shrink-0">{item.icon}</span>
              <span>{item.label}</span>
              {activePanel === getPanelFromPath(item.path) && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary" />
              )}
            </button>
          ))}
        </nav>

        {/* Footer / Status */}
        <div className="p-3 border-t border-border">
          <div className="flex items-center gap-2 text-xs text-textSecondary">
            <span className="w-2 h-2 rounded-full bg-success" />
            <span>API Connected</span>
          </div>
          <div className="mt-2 pt-2 border-t border-border text-xs text-textMuted">
            <div className="font-medium text-textSecondary mb-1">LLM Provider</div>
            <span className={`badge text-xs ${
              llmProvider === 'groq' ? 'badge-primary' :
              llmProvider === 'nim' ? 'badge-success' : 'badge-warning'
            }`}>
              {llmProvider.toUpperCase()}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}