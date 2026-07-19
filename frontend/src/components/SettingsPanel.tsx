import { useState, useCallback, useEffect } from 'react';
import { useSettingsStore } from '../stores/useAppStore';

export default function SettingsPanel() {
  const { settings, updateSettings } = useSettingsStore();

  const [groqKey, setGroqKey] = useState(settings.groqApiKey);
  const [nimKey, setNimKey] = useState(settings.nimApiKey);
  const [nimBaseUrl, setNimBaseUrl] = useState(settings.nimBaseUrl);
  const [provider, setProvider] = useState(settings.llmProvider);
  const [showGroqKey, setShowGroqKey] = useState(false);
  const [showNimKey, setShowNimKey] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = useCallback(() => {
    updateSettings({
      groqApiKey: groqKey,
      nimApiKey: nimKey,
      nimBaseUrl: nimBaseUrl,
      llmProvider: provider,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [groqKey, nimKey, nimBaseUrl, provider, updateSettings]);

  const handleProviderChange = useCallback((newProvider: 'groq' | 'nim' | 'offline') => {
    setProvider(newProvider);
    updateSettings({ llmProvider: newProvider });
  }, [updateSettings]);

  // Load settings from localStorage on mount (handled by persist middleware)
  useEffect(() => {
    setGroqKey(settings.groqApiKey);
    setNimKey(settings.nimApiKey);
    setNimBaseUrl(settings.nimBaseUrl);
    setProvider(settings.llmProvider);
  }, [settings]);

  return (
    <div className="flex flex-col h-full bg-base">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
        <div>
          <h1 className="text-xl font-semibold text-textPrimary">Settings</h1>
          <p className="text-sm text-textSecondary">Configure API keys and preferences</p>
        </div>
        <button onClick={handleSave} className="btn-primary" disabled={saved}>
          {saved ? 'Saved ✓' : 'Save Settings'}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 lg:p-6">
        <div className="max-w-2xl mx-auto space-y-8">
          {/* LLM Provider */}
          <section className="card p-5">
            <h2 className="text-lg font-semibold text-textPrimary mb-4 flex items-center gap-2">
              <span className="text-2xl">🤖</span>
              LLM Provider
            </h2>
            <p className="text-sm text-textSecondary mb-4">
              Select which LLM provider to use for the AI chat. API keys are stored locally in your browser.
            </p>

            <div className="space-y-3">
              {[
                { id: 'groq', label: 'Groq', desc: 'Fast inference with Llama 3.3 70B (requires GROQ_API_KEY)' },
                { id: 'nim', label: 'NVIDIA NIM', desc: 'NVIDIA NIM endpoints (requires NIM_API_KEY)' },
                { id: 'offline', label: 'Offline Mode', desc: 'No LLM - use manual deck building only' },
              ].map((opt) => (
                <label
                  key={opt.id}
                  className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                    provider === opt.id
                      ? 'border-primary bg-primary/10'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="llmProvider"
                    value={opt.id}
                    checked={provider === opt.id}
                    onChange={() => handleProviderChange(opt.id as 'groq' | 'nim' | 'offline')}
                    className="mt-1 w-4 h-4 text-primary border-border focus:ring-primary"
                  />
                  <div>
                    <div className="font-medium text-textPrimary">{opt.label}</div>
                    <div className="text-sm text-textSecondary">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </section>

          {/* Groq API Key */}
          {provider === 'groq' && (
            <section className="card p-5">
              <h2 className="text-lg font-semibold text-textPrimary mb-4 flex items-center gap-2">
                <span className="text-2xl">🔑</span>
                Groq API Key
              </h2>
              <p className="text-sm text-textSecondary mb-4">
                Get your API key from <a href="https://console.groq.com/keys" target="_blank" rel="noopener" className="text-primary hover:underline">console.groq.com</a>
              </p>
              <div className="relative">
                <input
                  type={showGroqKey ? 'text' : 'password'}
                  value={groqKey}
                  onChange={(e) => setGroqKey(e.target.value)}
                  placeholder="gsk_..."
                  className="input pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowGroqKey(!showGroqKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-textSecondary hover:text-textPrimary"
                >
                  {showGroqKey ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
              <p className="text-xs text-textMuted mt-2">Key is stored in localStorage and sent via X-API-Keys header</p>
            </section>
          )}

          {/* NVIDIA NIM API Key */}
          {provider === 'nim' && (
            <section className="card p-5">
              <h2 className="text-lg font-semibold text-textPrimary mb-4 flex items-center gap-2">
                <span className="text-2xl">🔑</span>
                NVIDIA NIM API Key
              </h2>
              <p className="text-sm text-textSecondary mb-4">
                Configure your NVIDIA NIM endpoint. Get API access at <a href="https://build.nvidia.com" target="_blank" rel="noopener" className="text-primary hover:underline">build.nvidia.com</a>
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-textSecondary mb-1">Base URL</label>
                  <input
                    type="text"
                    value={nimBaseUrl}
                    onChange={(e) => setNimBaseUrl(e.target.value)}
                    placeholder="https://integrate.api.nvidia.com/v1"
                    className="input"
                  />
                </div>
                <div className="relative">
                  <input
                    type={showNimKey ? 'text' : 'password'}
                    value={nimKey}
                    onChange={(e) => setNimKey(e.target.value)}
                    placeholder="nvapi_..."
                    className="input pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNimKey(!showNimKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-textSecondary hover:text-textPrimary"
                  >
                    {showNimKey ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
              <p className="text-xs text-textMuted mt-2">Key is stored in localStorage and sent via X-API-Keys header</p>
            </section>
          )}

          {/* UI Preferences */}
          <section className="card p-5">
            <h2 className="text-lg font-semibold text-textPrimary mb-4 flex items-center gap-2">
              <span className="text-2xl">🎨</span>
              UI Preferences
            </h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-textPrimary">Theme</div>
                  <div className="text-sm text-textSecondary">Dark blue/cyan (fixed for this release)</div>
                </div>
                <span className="badge badge-primary text-xs">Dark Blue</span>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-textPrimary">Font</div>
                  <div className="text-sm text-textSecondary">JetBrains Mono for code, Inter for UI</div>
                </div>
                <span className="badge badge-outline text-xs">System Default</span>
              </div>
            </div>
          </section>

          {/* Data Management */}
          <section className="card p-5 border-error/30">
            <h2 className="text-lg font-semibold text-textPrimary mb-4 flex items-center gap-2">
              <span className="text-2xl">🗑️</span>
              Data Management
            </h2>
            <p className="text-sm text-textSecondary mb-4">
              Clear all locally stored data (chat history, settings, job history, decks).
            </p>
            <button
              onClick={() => {
                if (confirm('Clear all local data? This cannot be undone.')) {
                  localStorage.clear();
                  window.location.reload();
                }
              }}
              className="btn-danger"
            >
              Clear All Local Data
            </button>
          </section>

          {/* Info */}
          <section className="card p-5 bg-primary/5 border-primary/20">
            <h3 className="font-medium text-textPrimary mb-2">About OPM-AI</h3>
            <p className="text-sm text-textSecondary">
              OPM-AI Frontend v0.1.0 — React + Vite + TypeScript + Tailwind CSS
            </p>
            <p className="text-sm text-textSecondary mt-1">
              Backend: FastAPI on port 8000 | Frontend dev server: port 5173
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <a href="https://github.com/OPM/opm" target="_blank" rel="noopener" className="text-xs text-primary hover:underline">OPM Project</a>
              <a href="https://opm-project.org" target="_blank" rel="noopener" className="text-xs text-primary hover:underline">Documentation</a>
              <a href="https://github.com/NVIDIA" target="_blank" rel="noopener" className="text-xs text-primary hover:underline">NVIDIA NIM</a>
              <a href="https://groq.com" target="_blank" rel="noopener" className="text-xs text-primary hover:underline">Groq</a>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}