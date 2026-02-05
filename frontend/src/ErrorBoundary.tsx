import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = { children: ReactNode };
type State = { hasError: boolean; error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError && this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#0f0f0f] p-4">
          <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-6 max-w-md">
            <h1 className="text-lg font-semibold text-red-400 mb-2">Something went wrong</h1>
            <p className="text-zinc-400 text-sm mb-4 font-mono break-all">
              {this.state.error.message}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => this.setState({ hasError: false, error: null })}
                className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium"
              >
                Try again
              </button>
              <a
                href="/"
                className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm font-medium"
              >
                Go to Live
              </a>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
