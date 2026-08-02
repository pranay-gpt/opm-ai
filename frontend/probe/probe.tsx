// Render-verification harness. Mounts the real Grid3DViewer, in StrictMode,
// the same way ResultsViewer does. Not part of the app build.
import { StrictMode, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '../src/index.css';
import Grid3DViewer from '../src/components/viewer3d/Grid3DViewer';

declare global {
  interface Window {
    __probe: { errors: string[]; contexts: number; released: number };
    __setJob: (j: string | null) => void;
  }
}
window.__probe = { errors: [], contexts: 0, released: 0 };

// Count WebGL contexts so a leak across mounts is visible. Browsers cap at ~16
// live contexts and then start blanking canvases, so a leak here is fatal.
const realGetContext = HTMLCanvasElement.prototype.getContext;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, id: string, ...rest: any[]) {
  if (id === 'webgl2' || id === 'webgl') window.__probe.contexts++;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (realGetContext as any).call(this, id, ...rest);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
} as any;

window.addEventListener('error', (e) => window.__probe.errors.push(String(e.message)));
window.addEventListener('unhandledrejection', (e) =>
  window.__probe.errors.push('reject: ' + String((e as PromiseRejectionEvent).reason)),
);

function Harness() {
  const [job, setJob] = useState<string | null>('probe-spe1');
  window.__setJob = setJob;
  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      {job ? <Grid3DViewer jobId={job} /> : <div id="unmounted">unmounted</div>}
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Harness />
  </StrictMode>,
);
