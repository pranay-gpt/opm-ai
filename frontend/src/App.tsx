import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { useEffect } from 'react';
import { useSettingsStore, useChatStore, useChatActions, useUIStore } from './stores/useAppStore';
import { connectChat } from './api/client';
import Home from './components/Home';
import DeckBuilder from './components/DeckBuilder';
import DeckEditor from './components/DeckEditor';
import SimulationRunner from './components/SimulationRunner';
import ResultsViewer from './components/ResultsViewer';
import ChatPanel from './components/ChatPanel';
import LinterPanel from './components/LinterPanel';
import SettingsPanel from './components/SettingsPanel';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import './index.css';

function AppLayout() {
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { isConnected, setConnected, setStreaming, sessionId, messages, addMessage, updateLastMessage, clearChat } = useChatStore();
  const { settings } = useSettingsStore();

  useEffect(() => {
    // Initialize WebSocket connection for chat
    let wsConnection: ReturnType<typeof connectChat> | null = null;

    const connect = () => {
      wsConnection = connectChat(
        sessionId,
        messages,
        {
          onToken: (content: string) => {
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
    };

    connect();

    return () => {
      wsConnection?.close();
    };
  }, [sessionId, messages, addMessage, updateLastMessage, setConnected, setStreaming]);

  return (
    <div className="flex h-screen bg-base overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header onMenuClick={toggleSidebar} />
        <main className="flex-1 overflow-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Home />} />
          <Route path="deck-builder" element={<DeckBuilder />} />
          <Route path="deck-editor" element={<DeckEditor />} />
          <Route path="simulator" element={<SimulationRunner />} />
          <Route path="results" element={<ResultsViewer />} />
          <Route path="chat" element={<ChatPanel />} />
          <Route path="linter" element={<LinterPanel />} />
          <Route path="settings" element={<SettingsPanel />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;