import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { useEffect } from 'react';
import { useUIStore } from './stores/useAppStore';
import Home from './components/Home';
import DeckBuilder from './components/DeckBuilder';
import DeckEditor from './components/DeckEditor';
import SimulationRunner from './components/SimulationRunner';
import ResultsViewer from './components/ResultsViewer';
import ChatPanel from './components/ChatPanel';
import LinterPanel from './components/LinterPanel';
import SettingsPanel from './components/SettingsPanel';
import Learn from './components/Learn';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import './index.css';

function ThemeApplier() {
  const theme = useUIStore((s) => s.theme);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'auto') {
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', theme);
    }
  }, [theme]);
  return null;
}

function AppLayout() {
  const { sidebarOpen, toggleSidebar } = useUIStore();

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
      <ThemeApplier />
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Home />} />
          <Route path="deck-builder" element={<DeckBuilder />} />
          <Route path="deck-editor" element={<DeckEditor />} />
          <Route path="simulator" element={<SimulationRunner />} />
          <Route path="results" element={<ResultsViewer />} />
          <Route path="learn" element={<Learn />} />
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