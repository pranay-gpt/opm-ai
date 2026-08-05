import { useUIStore, useLLMProvider, useSidebarCollapsed, useUIActions } from '../stores/useAppStore';

const THEME_OPTIONS = [
  { value: 'auto', label: 'Auto', title: 'Follow system preference' },
  { value: 'light', label: 'Light', title: 'Light mode' },
  { value: 'dark', label: 'Dark', title: 'Dark mode' },
] as const;

export default function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const llmProvider = useLLMProvider();
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);
  const sidebarCollapsed = useSidebarCollapsed();
  const { toggleSidebarCollapsed } = useUIActions();

  return (
    <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-4 lg:px-6 gap-4">
      {/* Mobile menu button */}
      <button
        onClick={onMenuClick}
        className="lg:hidden p-2 rounded-lg text-textSecondary hover:text-textPrimary hover:bg-surfaceHover transition-colors flex-shrink-0"
        aria-label="Toggle sidebar"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* Spacer + desktop expand-sidebar button. The desktop nav duplicates the
       sidebar links, so we dropped it - the sidebar is now the single nav
       surface on desktop. The expand button only renders when the sidebar
       is collapsed, so it does not clutter the normal view. */}
      <div className="hidden lg:flex items-center gap-2 flex-1 min-w-0">
        {sidebarCollapsed && (
          <button
            onClick={toggleSidebarCollapsed}
            className="p-2 rounded-lg text-textSecondary hover:text-textPrimary hover:bg-surfaceHover transition-colors flex-shrink-0"
            aria-label="Expand sidebar"
            title="Expand sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        )}
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3 flex-shrink-0">
        {/* Theme toggle */}
        <div className="theme-toggle" role="group" aria-label="Color theme">
          {THEME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              title={opt.title}
              className={theme === opt.value ? 'theme-toggle-btn-active' : 'theme-toggle-btn'}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* LLM provider badge */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-page border border-border">
          <span className="text-xs text-textMuted">LLM</span>
          <span className={`badge text-xs ${
            llmProvider === 'groq'    ? 'badge-primary' :
            llmProvider === 'nim'     ? 'badge-success' :
            llmProvider === 'openai'  ? 'badge-warning' :
                                        'badge-outline'
          }`}>
            {llmProvider.toUpperCase()}
          </span>
        </div>

        {/* API status dot */}
        <span className="w-2 h-2 rounded-full bg-success animate-pulse-glow flex-shrink-0" title="API connected" />
      </div>
    </header>
  );
}
