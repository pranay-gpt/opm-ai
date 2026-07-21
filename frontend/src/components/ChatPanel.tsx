import { useState, useEffect, useCallback, useRef } from 'react';
import { useChatStore, useSettingsStore } from '../stores/useAppStore';
import { api, connectChat } from '../api/client';
import type { ChatMessage } from '../api/client';

export default function ChatPanel() {
  const {
    messages,
    sessionId,
    isConnected,
    isStreaming,
    addMessage,
    updateLastMessage,
    clearChat,
    setConnected,
    setStreaming,
  } = useChatStore();
  const { settings } = useSettingsStore();

  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const connectionRef = useRef<ReturnType<typeof connectChat> | null>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Initialize WebSocket connection
  useEffect(() => {
    if (!settings.groqApiKey && !settings.nimApiKey && settings.llmProvider !== 'offline') {
      console.warn('[Chat] No API keys configured, using offline mode');
    }

    connectionRef.current = connectChat(
      sessionId,
      messages,
      {
        onToken: (content) => {
          if (messages.length === 0 || messages[messages.length - 1].role !== 'assistant') {
            addMessage({ role: 'assistant', content });
            setStreaming(true);
          } else {
            updateLastMessage({ content: messages[messages.length - 1].content + content });
          }
        },
        onToolCall: (toolCall) => {
          updateLastMessage({
            tool_calls: [...(messages[messages.length - 1]?.tool_calls || []), toolCall],
          });
        },
        onToolResult: (toolCallId, result) => {
          addMessage({ role: 'tool', content: result, tool_call_id: toolCallId });
        },
        onError: (error) => {
          console.error('[Chat] Error:', error);
          addMessage({ role: 'assistant', content: `Error: ${error}` });
          setStreaming(false);
        },
        onDone: () => {
          setStreaming(false);
        },
        onClose: () => {
          setConnected(false);
        },
      }
    );

    setConnected(true);

    return () => {
      connectionRef.current?.close();
    };
  }, [sessionId, messages, addMessage, updateLastMessage, setConnected, setStreaming]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || isSending) return;

    const userMessage: ChatMessage = { role: 'user', content: input };
    addMessage(userMessage);
    setInput('');
    setIsSending(true);

    connectionRef.current?.send([...messages, userMessage]);
    setIsSending(false);
  }, [input, isSending, messages, addMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <div className="flex flex-col h-full bg-base">
      {/* Connection Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-success' : 'bg-error'}`} />
          <span className="text-sm text-textSecondary">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
          {isStreaming && (
            <span className="px-2 py-0.5 text-xs rounded bg-primary/20 text-primary animate-pulse">
              Streaming...
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={settings.llmProvider}
            onChange={(e) => {
              const newProvider = e.target.value as 'groq' | 'nim' | 'offline';
              useSettingsStore.getState().setLLMProvider(newProvider);
              // Apply to the backend too; keys are managed on the Settings page.
              api.updateSettings({ provider: newProvider }).catch((err) => {
                console.error('[Chat] Failed to update provider:', err);
              });
            }}
            className="text-xs px-2 py-1 rounded bg-base border border-border text-textPrimary"
          >
            <option value="groq">Groq</option>
            <option value="nim">NVIDIA NIM</option>
            <option value="offline">Offline</option>
          </select>
          <button
            onClick={clearChat}
            className="p-2 rounded hover:bg-surfaceHover text-textSecondary hover:text-textPrimary transition-colors"
            title="Clear chat"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-textSecondary">
            <div className="text-6xl mb-4 opacity-50"><svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h4M8 16h4M8 8h4M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg></div>
            <p className="text-lg font-medium text-textPrimary mb-2">Start a conversation</p>
            <p className="text-sm max-w-xs text-center">
              Ask me to build a deck, run a simulation, or explain reservoir engineering concepts.
            </p>
            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              {['Build a 10x10x3 depletion deck', 'Run simulation on last deck', 'Explain PVT modelling', 'Lint my current deck'].map(
                (suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => {
                      setInput(suggestion);
                      handleSend();
                    }}
                    className="text-xs px-3 py-1.5 rounded border border-border text-textSecondary hover:text-textPrimary hover:border-primary/50 hover:bg-surfaceHover transition-colors"
                  >
                    {suggestion}
                  </button>
                )
              )}
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                message.role === 'user'
                  ? 'bg-primary/20 text-primary'
                  : message.role === 'tool'
                  ? 'bg-warning/20 text-warning'
                  : 'bg-surface border border-border'
              }`}
            >
              {message.role === 'user' ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
              ) : message.role === 'tool' ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
              )}
            </div>

            <div className={`flex-1 min-w-0 ${message.role === 'user' ? 'text-right' : ''}`}>
              <div
                className={`prose prose-invert max-w-none ${message.role === 'user' ? 'text-right' : ''}`}
              >
                <pre className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</pre>
              </div>

              {/* Tool calls */}
              {message.tool_calls && message.tool_calls.length > 0 && (
                <div className="mt-2 space-y-1">
                  {message.tool_calls.map((tc, i) => (
                    <div
                      key={i}
                      className={`inline-flex items-center gap-2 px-2 py-1 rounded text-xs font-mono ${
                        message.role === 'tool'
                          ? 'bg-success/20 text-success'
                          : 'bg-primary/20 text-primary'
                      }`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-current" />
                      {tc.function.name}
                      <span className="text-textMuted">{tc.function.arguments.slice(0, 50)}...</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Tool result */}
              {message.role === 'tool' && (
                <div className="mt-2 p-2 rounded bg-base border border-border text-xs font-mono text-textSecondary max-h-32 overflow-auto">
                  {message.content}
                </div>
              )}
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-border p-4 bg-surface">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me to build a deck, run a simulation, or explain a concept..."
            className="flex-1 min-h-[44px] max-h-32 px-4 py-2.5 rounded-lg bg-base border border-border text-textPrimary placeholder-textMuted focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary resize-none font-sans text-sm"
            disabled={isSending}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isSending || !isConnected}
            className="px-6 py-2.5 rounded-lg bg-primary text-base font-medium text-base hover:bg-primaryHover disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            {isSending ? 'Sending...' : 'Send'}
          </button>
        </div>
        <p className="text-xs text-textMuted mt-2 text-center">
          Press Enter to send, Shift+Enter for new line. Provider: {settings.llmProvider.toUpperCase()}
        </p>
      </div>
    </div>
  );
}