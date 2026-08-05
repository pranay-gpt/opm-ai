import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Catches render errors so one bad route does not blank the whole app. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Render error:', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="max-w-2xl mx-auto mt-8 p-6 rounded-lg bg-surface border border-border">
        <h2 className="text-lg font-medium text-error mb-2">Something went wrong</h2>
        <pre className="whitespace-pre-wrap text-xs font-mono text-textSecondary bg-page border border-border rounded p-3 max-h-64 overflow-auto">
          {error.message}
        </pre>
        <div className="mt-4 flex gap-2">
          <button
            onClick={() => this.setState({ error: null })}
            className="px-4 py-2 rounded-lg bg-primary text-page font-medium hover:bg-primaryHover transition-colors"
          >
            Reset
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg border border-border text-textSecondary hover:text-textPrimary hover:bg-surfaceHover transition-colors"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
