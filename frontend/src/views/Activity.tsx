/**
 * Unified Activity — one data-rich container for all collected analysis.
 * Tabs: Feed (merged timeline), Events, Log (AI data), Charts.
 * Avoids redundant Events/Timeline/Log/Behaviors pages; single place to view and act.
 */
import { useState, useMemo, useEffect } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchEvents,
  fetchGetData,
  fetchAggregates,
  acknowledgeEvent,
  searchQuery,
  fetchRecordingStatus,
  type EventRow,
  type AIDataRow,
  type AggregateRow,
} from '../api/client';
import { EventRowSkeleton, TimelineRowSkeleton, CardSkeleton } from '../components/Skeleton';
import {
  getEventTypeLabel,
  getSeverityLabel,
  getSeverityDescription,
  getBehaviorLabel,
  getBehaviorDescription,
  FLAGS,
} from '../labels';
import { usePlaybackAtMoment } from '../PlaybackContext';

const TAB_KEYS = ['feed', 'events', 'log', 'charts'] as const;
type TabKey = (typeof TAB_KEYS)[number];

const RANGES = [
  { label: 'Last 24h', date_from: () => new Date(Date.now() - 86400 * 1000).toISOString().slice(0, 10), date_to: () => new Date().toISOString().slice(0, 10) },
  { label: 'Last 7 days', date_from: () => new Date(Date.now() - 7 * 86400 * 1000).toISOString().slice(0, 10), date_to: () => new Date().toISOString().slice(0, 10) },
  { label: 'All', date_from: () => undefined, date_to: () => undefined },
] as const;

function SeverityBadge({ s, small }: { s: string; small?: boolean }) {
  const c = s === 'high' ? 'bg-red-600/90 text-white' : s === 'medium' ? 'bg-amber-600/90 text-black' : 'bg-zinc-600 text-zinc-200';
  const desc = getSeverityDescription(s);
  return (
    <span
      className={`${small ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-0.5 text-xs'} rounded font-medium ${c}`}
      title={desc || getSeverityLabel(s)}
    >
      {getSeverityLabel(s)}
    </span>
  );
}

/** Single merged row for Feed: either an event or an AI data row */
type FeedItem = { type: 'event'; event: EventRow } | { type: 'ai'; ai: AIDataRow; sortKey: string };

function FeedRowEvent({ e, onAck, onPlayMoment }: { e: EventRow; onAck: (id: number) => void; onPlayMoment?: (e: EventRow) => void }) {
  const meta = e.metadata ? (() => { try { return JSON.parse(e.metadata); } catch { return {}; } })() : {};
  const severity = e.severity || 'medium';
  const borderClass = severity === 'high' ? 'border-l-red-500' : severity === 'medium' ? 'border-l-amber-500' : 'border-l-zinc-600';
  const behaviorLabel = meta.event ? getBehaviorLabel(String(meta.event)) : getEventTypeLabel(e.event_type);
  return (
    <div className={`flex items-center justify-between gap-3 py-2 px-2 border-b border-zinc-800/60 border-l-4 ${borderClass} rounded-r bg-zinc-900/40`}>
      <div className="min-w-0 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-zinc-500 text-xs font-medium uppercase w-14 shrink-0">Event</span>
        <span className="font-mono text-zinc-400 shrink-0 w-36">{e.timestamp}</span>
        <SeverityBadge s={severity} small />
        {!e.acknowledged_at && (
          <span className="px-1.5 py-0.5 rounded text-xs bg-amber-500/20 text-amber-400" title={FLAGS.NEEDS_REVIEW.title}>{FLAGS.NEEDS_REVIEW.label}</span>
        )}
        <span className="text-cyan-400 font-medium" title={getBehaviorDescription(String(meta.event || ''))}>{behaviorLabel}</span>
        {e.camera_id && <span className="text-zinc-500">Cam {e.camera_id}</span>}
        {meta.object && meta.object !== 'None' && <span className="text-zinc-400">· {String(meta.object)}</span>}
      </div>
      <div className="shrink-0 flex items-center gap-1.5">
        {onPlayMoment && (
          <button type="button" onClick={() => onPlayMoment(e)} className="px-2 py-1 rounded text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200" title="Play recording at this moment">Play</button>
        )}
        {!e.acknowledged_at ? (
          <button type="button" onClick={() => onAck(e.id)} className="px-2 py-1 rounded text-xs bg-cyan-600 hover:bg-cyan-500 text-black font-medium">Ack</button>
        ) : (
          <span className="text-zinc-600 text-xs">{FLAGS.ACKNOWLEDGED.label}</span>
        )}
      </div>
    </div>
  );
}

function FeedRowAI({ row }: { row: AIDataRow }) {
  const eventRaw = row.event || 'None';
  const eventLabel = getBehaviorLabel(eventRaw);
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 px-2 border-b border-zinc-800/40 rounded-r bg-zinc-900/20 border-l-4 border-l-zinc-600">
      <span className="text-zinc-500 text-xs font-medium uppercase w-14 shrink-0">Detection</span>
      <span className="font-mono text-zinc-400 shrink-0 w-36" title={`${row.date} ${row.time}`}>{row.date} {row.time}</span>
      <span className={eventRaw !== 'None' ? 'text-cyan-400/90 font-medium' : 'text-zinc-500'}>{eventLabel}</span>
      <span className="text-zinc-300">{row.object || '—'}</span>
      <span className="text-zinc-400 text-xs">{row.emotion || '—'}</span>
      <span className="text-zinc-500 text-xs">pose: {row.pose || '—'}</span>
      <span className="text-zinc-500 text-xs">crowd: {row.crowd_count ?? '—'}</span>
      {row.camera_id && <span className="text-zinc-600 text-xs">cam {row.camera_id}</span>}
    </div>
  );
}

const PATH_TO_TAB: Record<string, TabKey> = { '/events': 'events', '/timeline': 'feed', '/log': 'log', '/behaviors': 'charts' };

export default function Activity() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const pathTab = PATH_TO_TAB[location.pathname];
  const tabParam = (pathTab ?? searchParams.get('view') ?? 'feed') as TabKey;
  const tab = TAB_KEYS.includes(tabParam) ? tabParam : 'feed';
  const setTab = (t: TabKey) => setSearchParams({ view: t }, { replace: true });

  useEffect(() => {
    if (pathTab && pathTab !== searchParams.get('view')) setSearchParams({ view: pathTab }, { replace: true });
  }, [pathTab, searchParams, setSearchParams]);

  const [rangeIndex, setRangeIndex] = useState(0);
  const range = RANGES[rangeIndex];
  const dateFrom = range.date_from();
  const dateTo = range.date_to();

  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [ackFilter, setAckFilter] = useState<'all' | 'unack' | 'ack'>('all');
  const [searchQ, setSearchQ] = useState('');
  const [searchSubmitted, setSearchSubmitted] = useState('');

  const queryClient = useQueryClient();
  const ackParam = ackFilter === 'unack' ? 'false' : ackFilter === 'ack' ? 'true' : undefined;

  const { data: recordingStatus } = useQuery({
    queryKey: ['recording'],
    queryFn: fetchRecordingStatus,
    refetchInterval: 10000,
  });
  const isRecording = !!recordingStatus?.recording;

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['events', 'activity', dateFrom ?? 'all', dateTo ?? 'all', ackParam, severityFilter, eventTypeFilter],
    queryFn: () =>
      fetchEvents({
        limit: 300,
        date_from: dateFrom,
        date_to: dateTo,
        acknowledged: ackParam,
        severity: severityFilter || undefined,
        event_type: eventTypeFilter || undefined,
      }),
    enabled: tab === 'feed' || tab === 'events',
    refetchInterval: tab === 'feed' || tab === 'events' ? 20000 : false,
  });

  const { data: aiRows, isLoading: aiLoading } = useQuery({
    queryKey: ['get_data', 'activity', dateFrom ?? 'all', dateTo ?? 'all'],
    queryFn: () => fetchGetData({ limit: 300, date_from: dateFrom, date_to: dateTo }),
    enabled: tab === 'feed' || tab === 'log',
    refetchInterval: tab === 'feed' || tab === 'log' ? 20000 : false,
  });

  const { data: aggregates, isLoading: aggLoading } = useQuery({
    queryKey: ['aggregates', 'activity', dateTo ?? new Date().toISOString().slice(0, 10)],
    queryFn: () => fetchAggregates({ date_from: dateFrom ?? new Date().toISOString().slice(0, 10), date_to: dateTo ?? new Date().toISOString().slice(0, 10) }),
    enabled: tab === 'charts',
  });

  const { data: searchResult, isFetching: searchLoading } = useQuery({
    queryKey: ['search', searchSubmitted],
    queryFn: () => searchQuery(searchSubmitted, 30),
    enabled: searchSubmitted.length > 0 && tab === 'events',
  });

  const ack = useMutation({
    mutationFn: (id: number) => acknowledgeEvent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['events'] }),
  });
  const { openPlaybackAtMoment } = usePlaybackAtMoment() ?? {};

  const feedItems: FeedItem[] = useMemo(() => {
    const list: FeedItem[] = [];
    (events ?? []).forEach((e) => list.push({ type: 'event', event: e }));
    (aiRows ?? []).forEach((r) => {
      const sortKey = `${r.date}T${r.time}`;
      list.push({ type: 'ai', ai: r, sortKey });
    });
    list.sort((a, b) => {
      const tsA = a.type === 'event' ? a.event.timestamp : a.sortKey;
      const tsB = b.type === 'event' ? b.event.timestamp : b.sortKey;
      return tsB.localeCompare(tsA);
    });
    return list.slice(0, 200);
  }, [events, aiRows]);

  const aggRows = useMemo<AggregateRow[]>(() => aggregates?.aggregates ?? [], [aggregates?.aggregates]);
  const byHour: Record<number, number> = useMemo(() => {
    const buckets: Record<number, number> = {};
    for (let h = 0; h < 24; h++) buckets[h] = 0;
    aggRows.forEach((a) => {
      const h = parseInt(a.hour, 10);
      if (!Number.isNaN(h) && h >= 0 && h < 24) buckets[h] = (buckets[h] ?? 0) + (a.count || 0);
    });
    return buckets;
  }, [aggRows]);
  const maxByHour = Math.max(1, ...Object.values(byHour));

  const eventsList = events ?? [];
  const logRows = useMemo(() => [...(aiRows ?? [])].sort((a, b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`)), [aiRows]);

  const exportEventsCsv = () => {
    if (eventsList.length === 0) return;
    const headers = ['id', 'event_type', 'camera_id', 'timestamp', 'severity', 'acknowledged_at', 'metadata'];
    const escape = (v: unknown) => '"' + String(v != null ? v : '').replace(/"/g, '""') + '"';
    const rows = eventsList.map((e) =>
      [e.id, e.event_type, e.camera_id ?? '', e.timestamp, e.severity ?? '', e.acknowledged_at ?? '', e.metadata ?? ''].map(escape).join(',')
    );
    const csv = headers.join(',') + '\n' + rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `events_${dateFrom ?? 'all'}_${dateTo ?? 'all'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportLogCsv = () => {
    if (logRows.length === 0) return;
    const headers = ['date', 'time', 'event', 'object', 'emotion', 'pose', 'scene', 'crowd_count'];
    const escape = (v: unknown) => '"' + String(v != null ? v : '').replace(/"/g, '""') + '"';
    const rows = logRows.map((r) =>
      [r.date, r.time, r.event ?? '', r.object ?? '', r.emotion ?? '', r.pose ?? '', r.scene ?? '', r.crowd_count ?? ''].map(escape).join(',')
    );
    const csv = headers.join(',') + '\n' + rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ai_log_${dateFrom ?? 'all'}_${dateTo ?? 'all'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <h1 className="text-xl font-semibold text-cyan-400 mb-1">Activity — AI detections &amp; events</h1>
      <p className="text-zinc-500 text-sm mb-4">
        All collected analysis in one place: unified feed, events (with acknowledge), AI detection log, and charts. Data is collected only while recording is on (start from Live).
      </p>

      {!isRecording && (tab === 'feed' || tab === 'events' || tab === 'log') && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-200 text-sm flex items-center gap-2" role="status">
          <span className="font-medium">Recording is off.</span>
          <span>Start recording from the Live view to collect new AI detections and events.</span>
        </div>
      )}

      <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 p-2 border-b border-zinc-700 bg-zinc-900">
          {TAB_KEYS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`px-3 py-2 rounded text-sm font-medium capitalize ${tab === t ? 'bg-cyan-600 text-black' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
              aria-pressed={tab === t}
            >
              {t === 'feed' ? 'Feed' : t === 'events' ? 'Events' : t === 'log' ? 'Log' : 'Charts'}
            </button>
          ))}
          <div className="flex-1" />
          {(tab === 'feed' || tab === 'events' || tab === 'log') && (
            <div className="flex flex-wrap items-center gap-2">
              {RANGES.map((r, i) => (
                <button
                  key={r.label}
                  type="button"
                  onClick={() => setRangeIndex(i)}
                  className={`px-2 py-1 rounded text-xs ${i === rangeIndex ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
                >
                  {r.label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  queryClient.invalidateQueries({ queryKey: ['events'] });
                  queryClient.invalidateQueries({ queryKey: ['getData'] });
                  queryClient.invalidateQueries({ queryKey: ['aggregates'] });
                }}
                className="px-2 py-1 rounded text-xs bg-zinc-700 text-zinc-300 hover:text-white"
                title="Reload feed, events, and log"
              >
                Refresh
              </button>
            </div>
          )}
        </div>

        <div className="min-h-[320px]">
          {tab === 'feed' && (
            <>
              <div className="px-2 py-1.5 border-b border-zinc-800 text-xs text-zinc-500 flex flex-wrap gap-x-4">
                <span>Merged by time (newest first). Event = alert; Detection = AI sample.</span>
                <span>{feedItems.length} items</span>
              </div>
              <div className="max-h-[70vh] overflow-y-auto">
                {eventsLoading || aiLoading ? (
                  [1, 2, 3, 4, 5, 6, 7].map((i) => <TimelineRowSkeleton key={i} />)
                ) : feedItems.length === 0 ? (
                  <div className="p-8 text-center text-zinc-500 text-sm">
                    No data in this range.
                    {!isRecording && <span className="block mt-2 text-amber-400/90">Start recording from Live to collect new detections and events.</span>}
                  </div>
                ) : (
                  feedItems.map((item, i) =>
                    item.type === 'event' ? (
                      <FeedRowEvent key={`ev-${item.event.id}`} e={item.event} onAck={(id) => ack.mutate(id)} onPlayMoment={openPlaybackAtMoment} />
                    ) : (
                      <FeedRowAI key={`ai-${i}-${item.ai.date}-${item.ai.time}`} row={item.ai} />
                    )
                  )
                )}
              </div>
            </>
          )}

          {tab === 'events' && (
            <>
              <div className="p-2 border-b border-zinc-800 flex flex-wrap items-center gap-2">
                <select
                  value={eventTypeFilter}
                  onChange={(e) => setEventTypeFilter(e.target.value)}
                  className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs"
                  aria-label="Event type"
                >
                  <option value="">All types</option>
                  <option value="motion">{getEventTypeLabel('motion')}</option>
                  <option value="loitering">{getEventTypeLabel('loitering')}</option>
                  <option value="line_cross">{getEventTypeLabel('line_cross')}</option>
                  <option value="fall">{getEventTypeLabel('fall')}</option>
                  <option value="crowding">{getEventTypeLabel('crowding')}</option>
                </select>
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs"
                  aria-label="Severity"
                >
                  <option value="">All severities</option>
                  <option value="high">{getSeverityLabel('high')}</option>
                  <option value="medium">{getSeverityLabel('medium')}</option>
                  <option value="low">{getSeverityLabel('low')}</option>
                </select>
                <select
                  value={ackFilter}
                  onChange={(e) => setAckFilter(e.target.value as 'all' | 'unack' | 'ack')}
                  className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs"
                >
                  <option value="all">All</option>
                  <option value="unack">Unacknowledged</option>
                  <option value="ack">Acknowledged</option>
                </select>
                <input
                  type="search"
                  placeholder="Search…"
                  className="flex-1 min-w-[140px] px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs placeholder-zinc-500 focus:border-cyan-500 focus:outline-none"
                  value={searchQ}
                  onChange={(e) => setSearchQ(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && setSearchSubmitted(searchQ.trim())}
                />
                <button
                  type="button"
                  onClick={() => setSearchSubmitted(searchQ.trim())}
                  className="px-3 py-1.5 rounded text-xs bg-cyan-600 hover:bg-cyan-500 text-black font-medium"
                >
                  Search
                </button>
                <button
                  type="button"
                  onClick={exportEventsCsv}
                  disabled={eventsList.length === 0}
                  className="px-3 py-1.5 rounded text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50 ml-auto"
                  title="Download current filtered events as CSV"
                >
                  Export events (CSV)
                </button>
              </div>
              {searchSubmitted && (
                <div className="px-2 py-2 border-b border-zinc-800 text-xs text-zinc-400">
                  Search &quot;{searchSubmitted}&quot; {searchLoading && '(loading…)'}
                  {searchResult && ` — Events: ${searchResult.events.length}, AI: ${searchResult.ai_data.length}`}
                </div>
              )}
              <div className="max-h-[60vh] overflow-y-auto">
                {eventsLoading ? (
                  [1, 2, 3, 4, 5].map((i) => <EventRowSkeleton key={i} />)
                ) : eventsList.length === 0 ? (
                  <div className="p-8 text-center text-zinc-500 text-sm">
                    No events. Change filters or range.
                    {!isRecording && <span className="block mt-2 text-amber-400/90">Events are created when recording is on and motion/loitering/line-cross is detected.</span>}
                  </div>
                ) : (
                  eventsList.map((e) => (
                    <div
                      key={e.id}
                      className={`flex items-center justify-between gap-3 py-2 px-2 border-b border-zinc-800/60 border-l-4 rounded-r ${
                        (e.severity || 'medium') === 'high' ? 'border-l-red-500' : (e.severity || 'medium') === 'medium' ? 'border-l-amber-500' : 'border-l-zinc-600'
                      }`}
                    >
                      <div className="min-w-0 flex flex-wrap items-center gap-2 text-sm">
                        <span className="font-mono text-zinc-400 shrink-0 w-36">{e.timestamp}</span>
                        <SeverityBadge s={e.severity || 'medium'} small />
                        {!e.acknowledged_at && <span className="px-1.5 py-0.5 rounded text-xs bg-amber-500/20 text-amber-400">{FLAGS.NEEDS_REVIEW.label}</span>}
                        <span className="text-cyan-400 font-medium">{getEventTypeLabel(e.event_type)}</span>
                        {e.camera_id && <span className="text-zinc-500">Cam {e.camera_id}</span>}
                        {e.metadata && (() => { try { const m = JSON.parse(e.metadata); return m.object && m.object !== 'None' ? <span className="text-zinc-400">· {String(m.object)}</span> : null; } catch { return null; } })()}
                      </div>
                      <div className="shrink-0 flex items-center gap-1.5">
                        {openPlaybackAtMoment && (
                          <button type="button" onClick={() => openPlaybackAtMoment(e)} className="px-2 py-1 rounded text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200" title="Play recording at this moment">Play</button>
                        )}
                        {!e.acknowledged_at ? (
                          <button type="button" onClick={() => ack.mutate(e.id)} className="px-2 py-1 rounded text-xs bg-cyan-600 hover:bg-cyan-500 text-black font-medium">Ack</button>
                        ) : (
                          <span className="text-zinc-600 text-xs">{FLAGS.ACKNOWLEDGED.label}</span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          )}

          {tab === 'log' && (
            <>
              <div className="p-2 border-b border-zinc-800 flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs text-zinc-500">{logRows.length} rows</span>
                <button
                  type="button"
                  onClick={exportLogCsv}
                  disabled={logRows.length === 0}
                  className="px-3 py-1.5 rounded text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50"
                  title="Download AI detection log as CSV"
                >
                  Export log (CSV)
                </button>
              </div>
              <div className="px-2 py-1.5 border-b border-zinc-800 text-xs text-zinc-500 font-mono flex flex-wrap gap-x-3">
                <span className="w-36">date time</span>
                <span>event</span>
                <span>object</span>
                <span>emotion</span>
                <span>pose</span>
                <span>scene</span>
                <span>crowd</span>
              </div>
              <div className="max-h-[70vh] overflow-y-auto">
                {aiLoading ? (
                  [1, 2, 3, 4, 5, 6, 7].map((i) => <TimelineRowSkeleton key={i} />)
                ) : logRows.length === 0 ? (
                  <div className="p-8 text-center text-zinc-500 text-sm">
                    No AI data in this range.
                    {!isRecording && <span className="block mt-2 text-amber-400/90">Start recording from Live to collect AI detection samples.</span>}
                  </div>
                ) : (
                  logRows.map((r, i) => (
                    <div key={`${r.date}-${r.time}-${i}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-1.5 px-2 border-b border-zinc-800/60 text-sm font-mono hover:bg-zinc-800/30">
                      <span className="text-zinc-400 shrink-0 w-36">{r.date} {r.time}</span>
                      <span className={r.event !== 'None' ? 'text-cyan-400' : 'text-zinc-500'}>{getBehaviorLabel(r.event || 'None')}</span>
                      <span className="text-zinc-300">{r.object || '—'}</span>
                      <span className="text-zinc-400">{r.emotion || '—'}</span>
                      <span className="text-zinc-500 text-xs">pose: {r.pose || '—'}</span>
                      <span className="text-zinc-500 text-xs">scene: {r.scene || '—'}</span>
                      <span className="text-zinc-500 text-xs">crowd: {r.crowd_count ?? '—'}</span>
                    </div>
                  ))
                )}
              </div>
            </>
          )}

          {tab === 'charts' && (
            <div className="p-4 space-y-6">
              <section>
                <h2 className="text-sm font-medium text-cyan-400 uppercase tracking-wide mb-2">Activity by hour</h2>
                {aggLoading ? (
                  <div className="h-24 flex items-center justify-center text-zinc-500 text-sm">Loading…</div>
                ) : (
                  <div className="flex items-end gap-0.5 h-24" aria-label="Events per hour">
                    {Array.from({ length: 24 }, (_, i) => (
                      <div key={i} className="flex-1 min-w-0 flex flex-col justify-end group" title={`${i}:00 – ${byHour[i] ?? 0} events`}>
                        <div
                          className="bg-cyan-600/80 rounded-t group-hover:bg-cyan-500 transition-colors"
                          style={{ height: `${Math.round(((byHour[i] ?? 0) / maxByHour) * 100)}%`, minHeight: (byHour[i] ?? 0) > 0 ? 4 : 0 }}
                        />
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex justify-between text-xs text-zinc-500 mt-1">
                  <span>00:00</span>
                  <span>12:00</span>
                  <span>23:00</span>
                </div>
              </section>
              <section>
                <h2 className="text-sm font-medium text-cyan-400 uppercase tracking-wide mb-2">Summary by event type</h2>
                {aggLoading ? (
                  <div className="grid grid-cols-3 gap-2">
                    <CardSkeleton /><CardSkeleton /><CardSkeleton />
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {['motion', 'loitering', 'line_cross', 'fall', 'crowding'].map((t) => {
                      const count = aggRows.filter((a) => a.event === t).reduce((s, a) => s + (a.count || 0), 0);
                      return (
                        <div key={t} className="rounded-lg bg-zinc-800/50 border border-zinc-700 p-3">
                          <div className="text-xs text-zinc-500 uppercase tracking-wide">{getEventTypeLabel(t)}</div>
                          <div className="text-xl font-semibold text-zinc-100 mt-0.5">{count}</div>
                        </div>
                      );
                    })}
                    <div className="rounded-lg bg-zinc-800/50 border border-zinc-700 p-3">
                      <div className="text-xs text-zinc-500 uppercase tracking-wide">Total</div>
                      <div className="text-xl font-semibold text-zinc-100 mt-0.5">{aggRows.reduce((s, a) => s + (a.count || 0), 0)}</div>
                    </div>
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
