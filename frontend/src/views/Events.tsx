import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchEvents, acknowledgeEvent, searchQuery, type EventRow } from '../api/client';

const SAVED_SEARCHES_KEY = 'surveillance_saved_searches';
type SavedSearch = { id: string; name: string; eventType: string; severity: string; ack: string; searchQ: string };
function loadSavedSearches(): SavedSearch[] {
  try {
    const raw = localStorage.getItem(SAVED_SEARCHES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedSearch[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
function saveSavedSearches(list: SavedSearch[]) {
  localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify(list));
}
import { EventRowSkeleton } from '../components/Skeleton';
import { getEventTypeLabel, getEventTypeDescription, getSeverityLabel, getSeverityDescription, getBehaviorLabel, getBehaviorDescription, FLAGS } from '../labels';
import { usePlaybackAtMoment } from '../PlaybackContext';

function SeverityBadge({ s, title }: { s: string; title?: string }) {
  const c = s === 'high' ? 'bg-red-600/90 text-white' : s === 'medium' ? 'bg-amber-600/90 text-black' : 'bg-zinc-600 text-zinc-200';
  const desc = getSeverityDescription(s);
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${c}`}
      title={title ?? (desc ? `${getSeverityLabel(s)}: ${desc}` : getSeverityLabel(s))}
    >
      {getSeverityLabel(s)}
    </span>
  );
}

function EventItem({ e, onAck, onPlayMoment }: { e: EventRow; onAck: (id: number) => void; onPlayMoment?: (e: EventRow) => void }) {
  const meta = e.metadata ? (() => { try { return JSON.parse(e.metadata); } catch { return {}; } })() : {};
  const severity = e.severity || 'medium';
  const borderClass = severity === 'high' ? 'border-l-red-500' : severity === 'medium' ? 'border-l-amber-500' : 'border-l-zinc-600';
  const eventTypeLabel = getEventTypeLabel(e.event_type);
  const eventTypeDesc = getEventTypeDescription(e.event_type);
  const behaviorLabel = meta.event ? getBehaviorLabel(String(meta.event)) : null;
  const behaviorDesc = meta.event ? getBehaviorDescription(String(meta.event)) : null;
  return (
    <div className={`flex items-center justify-between gap-4 p-3 rounded-lg bg-zinc-900 border border-zinc-700 border-l-4 ${borderClass}`}>
      <div className="min-w-0 flex flex-wrap items-center gap-2">
        <span className="font-mono text-zinc-400 text-sm shrink-0">{e.timestamp}</span>
        <SeverityBadge s={severity} />
        {severity === 'high' && (
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/50" title={FLAGS.HIGH_PRIORITY.title}>
            {FLAGS.HIGH_PRIORITY.label}
          </span>
        )}
        {!e.acknowledged_at && (
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-amber-500/20 text-amber-400 border border-amber-500/50" title={FLAGS.NEEDS_REVIEW.title}>
            {FLAGS.NEEDS_REVIEW.label}
          </span>
        )}
        <span className="font-medium text-cyan-400" title={eventTypeDesc || undefined}>{eventTypeLabel}</span>
        {e.camera_id && <span className="text-zinc-500 text-sm">Cam {e.camera_id}</span>}
        {meta.event && (
          <span className="text-zinc-300 text-sm" title={behaviorDesc || undefined}>
            {behaviorLabel ?? String(meta.event)}
          </span>
        )}
        {meta.object && meta.object !== 'None' && <span className="text-zinc-400 text-sm">· {String(meta.object)}</span>}
        {meta.emotion && meta.emotion !== 'Neutral' && <span className="text-zinc-500 text-xs">· {String(meta.emotion)}</span>}
      </div>
      <div className="shrink-0 flex items-center gap-2">
        {onPlayMoment && (
          <button type="button" onClick={() => onPlayMoment(e)} className="px-2 py-1 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200" title="Play recording at this moment">Play</button>
        )}
        {!e.acknowledged_at ? (
          <button
            onClick={() => onAck(e.id)}
            className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium"
          >
            Acknowledge
          </button>
        ) : (
          <span className="text-zinc-500 text-sm" title={FLAGS.ACKNOWLEDGED.title}>{FLAGS.ACKNOWLEDGED.label}</span>
        )}
      </div>
    </div>
  );
}

export default function Events() {
  const queryClient = useQueryClient();
  const [searchQ, setSearchQ] = useState('');
  const [searchSubmitted, setSearchSubmitted] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('');
  const [ackFilter, setAckFilter] = useState<string>('all'); // 'all' | 'unack' | 'ack'
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>(() => loadSavedSearches());
  const [saveSearchName, setSaveSearchName] = useState('');

  const applySavedSearch = useCallback((s: SavedSearch) => {
    setEventTypeFilter(s.eventType);
    setSeverityFilter(s.severity);
    setAckFilter(s.ack);
    setSearchQ(s.searchQ);
    if (s.searchQ) setSearchSubmitted(s.searchQ);
  }, []);

  const saveCurrentSearch = useCallback(() => {
    const name = saveSearchName.trim() || `Search ${new Date().toLocaleString()}`;
    const newItem: SavedSearch = {
      id: `saved_${Date.now()}`,
      name,
      eventType: eventTypeFilter,
      severity: severityFilter,
      ack: ackFilter,
      searchQ,
    };
    const next = [...savedSearches, newItem];
    setSavedSearches(next);
    saveSavedSearches(next);
    setSaveSearchName('');
  }, [saveSearchName, eventTypeFilter, severityFilter, ackFilter, searchQ, savedSearches]);

  const deleteSavedSearch = useCallback((id: string) => {
    const next = savedSearches.filter((s) => s.id !== id);
    setSavedSearches(next);
    saveSavedSearches(next);
  }, [savedSearches]);

  const ackParam = ackFilter === 'unack' ? 'false' : ackFilter === 'ack' ? 'true' : undefined;
  const { data: events, isLoading, error } = useQuery({
    queryKey: ['events', ackFilter, severityFilter, eventTypeFilter],
    queryFn: () => fetchEvents({
      limit: 200,
      acknowledged: ackParam,
      severity: severityFilter || undefined,
      event_type: eventTypeFilter || undefined,
    }),
  });
  const { data: searchResult, isFetching: searchLoading } = useQuery({
    queryKey: ['search', searchSubmitted],
    queryFn: () => searchQuery(searchSubmitted, 30),
    enabled: searchSubmitted.length > 0,
  });
  const ack = useMutation({
    mutationFn: (id: number) => acknowledgeEvent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['events'] }),
  });
  const { openPlaybackAtMoment } = usePlaybackAtMoment() ?? {};

  if (error) return <div className="p-4 text-red-400">Error: {(error as Error).message}</div>;

  const list = events ?? [];

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold text-cyan-400 mb-1">Events</h1>
      <p className="text-zinc-500 text-sm mb-4">
        Alerts and behaviors: motion, loitering, line crossing. Filter by type, severity, or acknowledgment. Flags: Needs review, High priority, Acknowledged.
      </p>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {savedSearches.length > 0 && (
          <>
            <label className="text-zinc-500 text-sm">Saved:</label>
            <select
              className="px-3 py-2 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm"
              value=""
              onChange={(e) => {
                const id = e.target.value;
                if (id) applySavedSearch(savedSearches.find((s) => s.id === id)!);
                e.target.value = '';
              }}
              aria-label="Load saved search"
            >
              <option value="">— Load —</option>
              {savedSearches.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            {savedSearches.map((s) => (
              <span key={s.id} className="flex items-center gap-1 text-xs">
                <button type="button" onClick={() => deleteSavedSearch(s.id)} className="text-red-400 hover:underline" title="Delete saved search">×</button>
                <span className="text-zinc-500">{s.name}</span>
              </span>
            ))}
          </>
        )}
        <input
          type="text"
          placeholder="Name for current filters"
          value={saveSearchName}
          onChange={(e) => setSaveSearchName(e.target.value)}
          className="w-40 px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm placeholder:text-zinc-500"
        />
        <button type="button" onClick={saveCurrentSearch} className="px-2 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm">
          Save search
        </button>
      </div>
      <div className="flex flex-wrap gap-2 mb-4">
        <select
          value={eventTypeFilter}
          onChange={(e) => setEventTypeFilter(e.target.value)}
          className="px-3 py-2 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm"
          aria-label="Filter by event type"
          title="Event type (behavior)"
        >
          <option value="">All types</option>
          <option value="motion">{getEventTypeLabel('motion')}</option>
          <option value="loitering">{getEventTypeLabel('loitering')}</option>
          <option value="line_cross">{getEventTypeLabel('line_cross')}</option>
          <option value="fall">{getEventTypeLabel('fall')}</option>
          <option value="crowding">{getEventTypeLabel('crowding')}</option>
          <option value="motion_alert">{getEventTypeLabel('motion_alert')}</option>
        </select>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="px-3 py-2 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm"
          aria-label="Filter by severity"
          title="Severity: high (urgent), medium, low"
        >
          <option value="">All severities</option>
          <option value="high">{getSeverityLabel('high')}</option>
          <option value="medium">{getSeverityLabel('medium')}</option>
          <option value="low">{getSeverityLabel('low')}</option>
        </select>
        <select
          value={ackFilter}
          onChange={(e) => setAckFilter(e.target.value)}
          className="px-3 py-2 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm"
          aria-label="Filter by acknowledgment"
        >
          <option value="all">All</option>
          <option value="unack">Unacknowledged</option>
          <option value="ack">Acknowledged</option>
        </select>
        <input
          type="search"
          placeholder="Search events and AI data (keyword)..."
          className="flex-1 min-w-[200px] px-3 py-2 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 placeholder-zinc-500 focus:border-cyan-500 focus:outline-none"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setSearchSubmitted(searchQ.trim())}
        />
        <button
          type="button"
          onClick={() => setSearchSubmitted(searchQ.trim())}
          className="px-4 py-2 rounded bg-cyan-600 hover:bg-cyan-500 text-black font-medium text-sm"
        >
          Search
        </button>
        <button
          type="button"
          onClick={() => {
            if (list.length === 0) return;
            const headers = ['id', 'timestamp', 'event_type', 'severity', 'camera_id', 'acknowledged_at', 'metadata'];
            const rows = list.map((e) =>
              headers.map((h) => {
                const v = (e as Record<string, unknown>)[h];
                const s = typeof v === 'string' && (v.includes(',') || v.includes('"') || v.includes('\n')) ? `"${v.replace(/"/g, '""')}"` : String(v ?? '');
                return s;
              }).join(',')
            );
            const csv = [headers.join(','), ...rows].join('\n');
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `events_export_${new Date().toISOString().slice(0, 10)}.csv`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          disabled={list.length === 0}
          className="px-4 py-2 rounded bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 text-zinc-200 font-medium text-sm"
          title="Download current event list as CSV"
        >
          Export CSV
        </button>
      </div>
      {searchSubmitted && (
        <div className="mb-4 p-3 rounded-lg bg-zinc-900/80 border border-zinc-700">
          <h2 className="text-sm font-medium text-cyan-400 mb-2">
            Search: &quot;{searchSubmitted}&quot; {searchLoading && '(loading…)'}
          </h2>
          {searchResult && (
            <>
              {searchResult.events.length > 0 && (
                <p className="text-zinc-400 text-sm mb-1">
                  Events: {searchResult.events.length}
                </p>
              )}
              {searchResult.ai_data.length > 0 && (
                <p className="text-zinc-400 text-sm">
                  AI records: {searchResult.ai_data.length}
                </p>
              )}
              {searchResult.events.length === 0 && searchResult.ai_data.length === 0 && !searchLoading && (
                <p className="text-zinc-500 text-sm">No matches.</p>
              )}
            </>
          )}
        </div>
      )}
      <div className="space-y-2">
        {isLoading && [1, 2, 3, 4, 5].map((i) => <EventRowSkeleton key={i} />)}
        {!isLoading && list.map((e) => (
          <EventItem key={e.id} e={e} onAck={(id) => ack.mutate(id)} onPlayMoment={openPlaybackAtMoment} />
        ))}
        {!isLoading && list.length === 0 && (
          <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 p-8 text-center">
            <p className="text-zinc-500 font-medium">No events</p>
            <p className="text-zinc-600 text-sm mt-1">Acquired events will appear here. Try changing filters or check Timeline for history.</p>
          </div>
        )}
      </div>
    </div>
  );
}
