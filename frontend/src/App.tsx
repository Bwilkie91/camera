import { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom';
import { REDIRECT_KEY } from './AuthContext';
import { QueryClient, QueryClientProvider, useQueryClient, useQuery } from '@tanstack/react-query';
import Dashboard from './views/Dashboard';
import Live from './views/Live';
import Activity from './views/Activity';
import Settings from './views/Settings';
import Export from './views/Export';
import Login from './views/Login';
import NotFound from './views/NotFound';
import { ErrorBoundary } from './ErrorBoundary';
import { AuthProvider, useAuth } from './AuthContext';
import { PlaybackProvider } from './PlaybackContext';
import PlaybackFromUrl from './PlaybackFromUrl';
import { logout, autoLogin, fetchRecordingStatus, fetchSystemStatus, searchQueryWithFilters, resetServerData, type SearchResult } from './api/client';

const RECENT_SEARCHES_KEY = 'vigil_recent_searches';
const RECENT_SEARCHES_MAX = 10;

function getRecentSearches(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.slice(0, RECENT_SEARCHES_MAX) : [];
  } catch {
    return [];
  }
}

function pushRecentSearch(q: string): void {
  if (!q.trim()) return;
  const recent = getRecentSearches().filter((s) => s.trim().toLowerCase() !== q.trim().toLowerCase());
  recent.unshift(q.trim());
  try {
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(recent.slice(0, RECENT_SEARCHES_MAX)));
  } catch {
    // ignore
  }
}

const queryClient = new QueryClient();

function HeaderIndicators() {
  const { data: recording } = useQuery({ queryKey: ['recording'], queryFn: fetchRecordingStatus, refetchInterval: 5000 });
  const { data: systemStatus } = useQuery({ queryKey: ['systemStatus'], queryFn: fetchSystemStatus, refetchInterval: 10000 });
  const isRecording = !!recording?.recording;
  const audioOn = !!systemStatus?.audio_enabled;
  return (
    <div className="flex items-center gap-3 mr-2">
      <span
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-bold tracking-wider ${
          isRecording ? 'bg-red-500/30 text-red-400 animate-pulse' : 'bg-zinc-800 text-zinc-500'
        }`}
        title={isRecording ? 'Recording (blinking = live)' : 'Recording stopped'}
        aria-live="polite"
      >
        <span className={`w-2 h-2 rounded-full ${isRecording ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]' : 'bg-zinc-500'}`} />
        REC
      </span>
      <span
        className={`inline-flex items-center text-base px-1.5 py-0.5 rounded border ${audioOn ? 'bg-cyan-500/15 border-cyan-500/50 text-cyan-400' : 'border-zinc-600 text-zinc-500'}`}
        title={audioOn ? 'Audio recording on' : 'Audio recording off'}
        aria-label={audioOn ? 'Audio recording on' : 'Audio recording off'}
      >
        🎤
      </span>
    </div>
  );
}

const WIPE_CONFIRM_MESSAGE =
  'Clear all cached data and reset visuals? Charts, events, and lists will refetch from server. Server data is not deleted.';

const RESET_SERVER_CONFIRM_MESSAGE =
  'Permanently delete all events and AI data on the server? Counts will go to zero. Recordings and users are not affected. Admin only.';

function ClearDataCacheButton({ inHeader = false }: { inHeader?: boolean }) {
  const queryClient = useQueryClient();
  const handleClick = useCallback(() => {
    if (!window.confirm(WIPE_CONFIRM_MESSAGE)) return;
    queryClient.clear();
  }, [queryClient]);
  if (inHeader) {
    return (
      <button
        type="button"
        onClick={handleClick}
        className="px-2 py-1 rounded text-sm font-medium text-amber-400/90 hover:text-amber-300 hover:bg-zinc-800 border border-amber-500/30"
        title="Clear cached data and reset all data visuals (audit: client-side only)"
        aria-label="Clear data cache and reset visuals"
        data-action="clear-data-cache"
      >
        Clear data cache
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={handleClick}
      className="px-3 py-2 rounded text-sm font-medium text-amber-400/90 hover:text-amber-300 hover:bg-zinc-800 border border-amber-500/30"
      title="Clear cached data and reset all data visuals (audit: client-side only)"
      aria-label="Clear data cache and reset visuals"
      data-action="clear-data-cache"
    >
      Clear data cache
    </button>
  );
}

function ResetServerDataButton({ inHeader = false }: { inHeader?: boolean }) {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const handleClick = useCallback(async () => {
    if (!window.confirm(RESET_SERVER_CONFIRM_MESSAGE)) return;
    setLoading(true);
    try {
      const result = await resetServerData();
      if (result.success) {
        queryClient.clear();
      } else {
        window.alert(result.error || 'Reset failed');
      }
    } catch (e) {
      window.alert(e instanceof Error ? e.message : 'Reset failed');
    } finally {
      setLoading(false);
    }
  }, [queryClient]);
  const className = inHeader
    ? 'px-2 py-1 rounded text-sm font-medium text-red-400/90 hover:text-red-300 hover:bg-zinc-800 border border-red-500/40'
    : 'px-3 py-2 rounded text-sm font-medium text-red-400/90 hover:text-red-300 hover:bg-zinc-800 border border-red-500/40';
  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className={className}
      title="Delete all events and AI data on server so counts reset to zero (admin only)"
      aria-label="Reset server data (delete events and AI data)"
      data-action="reset-server-data"
    >
      {loading ? 'Resetting…' : 'Reset server data'}
    </button>
  );
}

function Nav() {
  const link = (to: string, label: string) => (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-3 py-2 rounded text-sm font-medium ${isActive ? 'bg-cyan-600 text-black' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`
      }
    >
      {label}
    </NavLink>
  );
  return (
    <nav className="flex flex-wrap gap-2 border-b border-zinc-800 bg-zinc-900/50 px-4 py-2 items-center">
      {link('/dashboard', 'Dashboard')}
      {link('/', 'Live')}
      {link('/activity', 'Activity')}
      {link('/export', 'Export')}
      {link('/settings', 'Settings')}
      <ClearDataCacheButton />
      <ResetServerDataButton />
    </nav>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/" element={<Live />} />
      <Route path="/activity" element={<Activity />} />
      <Route path="/events" element={<Activity />} />
      <Route path="/behaviors" element={<Activity />} />
      <Route path="/timeline" element={<Activity />} />
      <Route path="/log" element={<Activity />} />
      <Route path="/map" element={<Navigate to="/export" replace />} />
      <Route path="/analytics" element={<Navigate to="/export" replace />} />
      <Route path="/export" element={<Export />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function EventToast({ show, onDismiss }: { show: boolean; onDismiss: () => void }) {
  useEffect(() => {
    if (!show) return;
    const t = setTimeout(onDismiss, 4000);
    return () => clearTimeout(t);
  }, [show, onDismiss]);
  if (!show) return null;
  return (
    <div
      className="fixed bottom-4 right-4 z-50 px-4 py-2 rounded-lg bg-cyan-600 text-black font-medium text-sm shadow-lg border border-cyan-400"
      role="status"
      aria-live="polite"
    >
      New event — <NavLink to="/activity?view=events" className="underline">View Activity</NavLink>
    </div>
  );
}

function HelpModal({ show, onClose }: { show: boolean; onClose: () => void }) {
  useEffect(() => {
    const onEscape = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    if (show) window.addEventListener('keydown', onEscape);
    return () => window.removeEventListener('keydown', onEscape);
  }, [show, onClose]);
  if (!show) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose} role="dialog" aria-label="Keyboard shortcuts">
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4 max-w-sm shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-cyan-400 mb-2">Keyboard shortcuts</h2>
        <ul className="text-sm text-zinc-300 space-y-1">
          <li><kbd className="px-1.5 py-0.5 rounded bg-zinc-700">Ctrl+K</kbd> / <kbd className="px-1.5 py-0.5 rounded bg-zinc-700">⌘K</kbd> — Quick search</li>
          <li><kbd className="px-1.5 py-0.5 rounded bg-zinc-700">?</kbd> — Show this help</li>
          <li><kbd className="px-1.5 py-0.5 rounded bg-zinc-700">Esc</kbd> — Close help</li>
          <li><kbd className="px-1.5 py-0.5 rounded bg-zinc-700">F</kbd> — Fullscreen (when a stream is focused on Live)</li>
        </ul>
        <p className="text-zinc-500 text-xs mt-2">Live: streams and recording. Activity: events, timeline, chart. Export: CSV, recordings, map, analytics. Focus a stream and press <kbd className="px-1 py-0.5 rounded bg-zinc-700">F</kbd> for fullscreen.</p>
        <button type="button" onClick={onClose} className="mt-3 w-full py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-sm">Close</button>
      </div>
    </div>
  );
}

function SearchModal({ show, onClose }: { show: boolean; onClose: () => void }) {
  const [q, setQ] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [eventType, setEventType] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recent = getRecentSearches();

  const runSearch = useCallback(async (overrideQuery?: string) => {
    const query = (overrideQuery ?? q).trim();
    if (!query) return;
    if (!overrideQuery) setQ(query);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await searchQueryWithFilters({
        q: query,
        limit: 50,
        date_from: dateFrom.trim() || undefined,
        date_to: dateTo.trim() || undefined,
        event_type: eventType.trim() || undefined,
      });
      setResult(data);
      pushRecentSearch(query);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [q, dateFrom, dateTo, eventType]);

  useEffect(() => {
    const onEscape = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    if (show) window.addEventListener('keydown', onEscape);
    return () => window.removeEventListener('keydown', onEscape);
  }, [show, onClose]);

  useEffect(() => {
    if (show) setResult(null);
  }, [show]);

  if (!show) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose} role="dialog" aria-label="Quick search">
      <div
        className="bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b border-zinc-700">
          <h2 className="text-lg font-semibold text-cyan-400 mb-3">Quick search</h2>
          <div className="flex flex-col gap-2">
            <input
              type="search"
              placeholder="Search events and detections…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
              className="w-full px-3 py-2 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              autoFocus
            />
            <div className="flex flex-wrap gap-2">
              <input
                type="date"
                placeholder="From"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
              />
              <input
                type="date"
                placeholder="To"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
              />
              <input
                type="text"
                placeholder="Event type (e.g. motion)"
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm flex-1 min-w-[120px]"
              />
              <button
                type="button"
                onClick={() => runSearch()}
                disabled={loading || !q.trim()}
                className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black font-medium text-sm disabled:opacity-50"
              >
                {loading ? 'Searching…' : 'Search'}
              </button>
            </div>
          </div>
          {recent.length > 0 && (
            <div className="mt-2">
              <span className="text-xs text-zinc-500">Recent: </span>
              {recent.slice(0, 5).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => { setQ(s); runSearch(); }}
                  className="text-xs text-cyan-400 hover:underline mr-2"
                >
                  {s.length > 24 ? s.slice(0, 24) + '…' : s}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="flex-1 overflow-auto p-4">
          {error && <p className="text-red-400 text-sm">{error}</p>}
          {result && (
            <>
              <p className="text-zinc-500 text-sm mb-2">
                {result.events.length} events, {result.ai_data.length} AI records
              </p>
              <div className="space-y-2 text-sm">
                {result.events.slice(0, 15).map((ev) => (
                  <div key={ev.id} className="py-1.5 px-2 rounded bg-zinc-800 border border-zinc-700">
                    <span className="text-cyan-400 font-medium">{ev.event_type}</span>
                    <span className="text-zinc-500 ml-2">{ev.timestamp}</span>
                    {ev.metadata && <span className="text-zinc-400 ml-2 truncate block">{ev.metadata}</span>}
                  </div>
                ))}
                {result.ai_data.slice(0, 10).map((row, i) => (
                  <div key={i} className="py-1.5 px-2 rounded bg-zinc-800 border border-zinc-700">
                    <span className="text-cyan-400">{row.event}</span>
                    <span className="text-zinc-500 ml-2">{row.date} {row.time}</span>
                    {row.object && <span className="text-zinc-400 ml-2">{row.object}</span>}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
        <div className="p-2 border-t border-zinc-700 flex justify-end">
          <button type="button" onClick={onClose} className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-sm">Close</button>
        </div>
      </div>
    </div>
  );
}

function App() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const { auth } = useAuth();
  const [eventToast, setEventToast] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const helpTriggerRef = useRef<HTMLButtonElement>(null);
  const searchTriggerRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setShowSearch((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  useEffect(() => {
    if (!auth?.authenticated) return;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = () => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.invalidateQueries({ queryKey: ['events', 'recent'] });
      queryClient.invalidateQueries({ queryKey: ['events', 'unack'] });
      setEventToast(true);
    };
    return () => ws.close();
  }, [auth?.authenticated, queryClient]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === '?' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) { e.preventDefault(); setShowHelp((v) => !v); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  if (auth === null) {
    return <div className="min-h-screen flex items-center justify-center bg-[#0f0f0f] text-zinc-400">Loading...</div>;
  }
  if (!auth.authenticated) {
    try {
      const { pathname, search } = location;
      if (pathname && pathname !== '/login') sessionStorage.setItem(REDIRECT_KEY, pathname + search);
    } catch {
      // ignore
    }
    return <Navigate to="/login" replace />;
  }
  return (
    <PlaybackProvider>
    <PlaybackFromUrl />
    <div className="min-h-screen bg-[#0f0f0f] text-zinc-200">
      <a
        href="#main"
        className="absolute left-[-9999px] focus:left-2 focus:top-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-cyan-600 focus:text-black focus:rounded focus:font-medium"
      >
        Skip to main content
      </a>
      <header className="border-b border-zinc-800 px-4 py-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold tracking-tight">
            <span className="text-white">Vigil</span>
            <span className="text-cyan-400 font-semibold ml-1.5">|</span>
            <span className="text-zinc-400 font-normal text-sm ml-1.5 hidden sm:inline">Edge Video Security</span>
          </h1>
          <HeaderIndicators />
        </div>
        <div className="flex items-center gap-2">
          <ClearDataCacheButton inHeader />
          <ResetServerDataButton inHeader />
          <button
            type="button"
            onClick={async () => {
              const r = await autoLogin();
              if (r?.success) window.location.href = '/';
            }}
            className="px-2 py-1 rounded text-sm text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
            title="Sign in as admin when server has AUTO_LOGIN=1"
          >
            Auto sign-in
          </button>
          <button ref={searchTriggerRef} type="button" onClick={() => setShowSearch(true)} className="text-zinc-500 hover:text-zinc-300 text-sm px-2" title="Quick search (Ctrl+K / ⌘K)">⌘K</button>
          <button ref={helpTriggerRef} type="button" onClick={() => setShowHelp(true)} className="text-zinc-500 hover:text-zinc-300 text-sm" title="Keyboard shortcuts (?)">?</button>
          <button onClick={() => logout().then(() => window.location.href = '/login')} className="text-sm text-zinc-400 hover:text-white">Logout</button>
        </div>
      </header>
      <Nav />
      <main id="main">
        <AppRoutes />
      </main>
      <EventToast show={eventToast} onDismiss={() => setEventToast(false)} />
      <HelpModal show={showHelp} onClose={() => { setShowHelp(false); setTimeout(() => helpTriggerRef.current?.focus(), 0); }} />
      <SearchModal show={showSearch} onClose={() => { setShowSearch(false); setTimeout(() => searchTriggerRef.current?.focus(), 0); }} />
    </div>
    </PlaybackProvider>
  );
}

export default function AppWithProviders() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/*" element={<App />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
