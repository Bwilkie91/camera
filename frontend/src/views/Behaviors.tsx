import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchEvents,
  fetchAggregates,
  acknowledgeEvent,
  type EventRow,
} from '../api/client';
import { CardSkeleton, EventRowSkeleton } from '../components/Skeleton';
import {
  getEventTypeLabel,
  getEventTypeDescription,
  getSeverityLabel,
  getSeverityDescription,
  getBehaviorLabel,
  getBehaviorDescription,
  FLAGS,
} from '../labels';

const BEHAVIOR_TYPES = ['motion', 'loitering', 'line_cross', 'fall', 'crowding'] as const;
const DATE_RANGES = [
  { label: 'Today', date_from: () => new Date().toISOString().slice(0, 10), date_to: () => new Date().toISOString().slice(0, 10) },
  { label: 'Last 7 days', date_from: () => new Date(Date.now() - 7 * 86400 * 1000).toISOString().slice(0, 10), date_to: () => new Date().toISOString().slice(0, 10) },
] as const;

function SeverityBadge({ s }: { s: string }) {
  const c = s === 'high' ? 'bg-red-600/90 text-white' : s === 'medium' ? 'bg-amber-600/90 text-black' : 'bg-zinc-600 text-zinc-200';
  const desc = getSeverityDescription(s);
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${c}`} title={desc || getSeverityLabel(s)}>
      {getSeverityLabel(s)}
    </span>
  );
}

function FeedRow({ e, onAck }: { e: EventRow; onAck: (id: number) => void }) {
  const meta = e.metadata ? (() => { try { return JSON.parse(e.metadata); } catch { return {}; } })() : {};
  const severity = e.severity || 'medium';
  const borderClass = severity === 'high' ? 'border-l-red-500' : severity === 'medium' ? 'border-l-amber-500' : 'border-l-zinc-600';
  const behaviorLabel = meta.event ? getBehaviorLabel(String(meta.event)) : getEventTypeLabel(e.event_type);
  return (
    <div className={`flex items-center justify-between gap-3 py-2 px-2 border-b border-zinc-800/60 border-l-4 ${borderClass} rounded-r hover:bg-zinc-800/40`}>
      <div className="min-w-0 flex flex-wrap items-center gap-2 text-sm">
        <span className="font-mono text-zinc-400 shrink-0 w-28">{e.timestamp}</span>
        <SeverityBadge s={severity} />
        {!e.acknowledged_at && (
          <span className="px-1.5 py-0.5 rounded text-xs bg-amber-500/20 text-amber-400" title={FLAGS.NEEDS_REVIEW.title}>{FLAGS.NEEDS_REVIEW.label}</span>
        )}
        <span className="text-cyan-400 font-medium" title={getEventTypeDescription(e.event_type) || getBehaviorDescription(String(meta.event || ''))}>{behaviorLabel}</span>
        {e.camera_id && <span className="text-zinc-500">Cam {e.camera_id}</span>}
        {meta.object && meta.object !== 'None' && <span className="text-zinc-400">· {String(meta.object)}</span>}
      </div>
      {!e.acknowledged_at ? (
        <button type="button" onClick={() => onAck(e.id)} className="shrink-0 px-2 py-1 rounded text-xs bg-cyan-600 hover:bg-cyan-500 text-black font-medium">Ack</button>
      ) : (
        <span className="text-zinc-600 text-xs shrink-0">{FLAGS.ACKNOWLEDGED.label}</span>
      )}
    </div>
  );
}

export default function Behaviors() {
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const [dateRangeIndex, setDateRangeIndex] = useState(0);
  const [behaviorFilter, setBehaviorFilter] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const range = DATE_RANGES[dateRangeIndex];
  const dateFrom = range.date_from();
  const dateTo = range.date_to();

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['events', 'behaviors', dateFrom, dateTo, behaviorFilter, severityFilter],
    queryFn: () =>
      fetchEvents({
        limit: 200,
        date_from: dateFrom,
        date_to: dateTo,
        event_type: behaviorFilter || undefined,
        severity: severityFilter || undefined,
      }),
  });

  const { data: eventsUnack } = useQuery({
    queryKey: ['events', 'unack'],
    queryFn: () => fetchEvents({ limit: 500, acknowledged: 'false' }),
  });

  const { data: aggregates, isLoading: aggLoading } = useQuery({
    queryKey: ['aggregates', 'behaviors', today],
    queryFn: () => fetchAggregates({ date_from: today, date_to: today }),
  });

  const ack = useMutation({
    mutationFn: (id: number) => acknowledgeEvent(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });

  const list = events ?? [];
  const unackCount = eventsUnack?.length ?? 0;

  const byType = (() => {
    const m: Record<string, number> = {};
    list.forEach((e) => {
      const t = e.event_type || 'other';
      m[t] = (m[t] ?? 0) + 1;
    });
    return m;
  })();

  const byHour = (() => {
    const buckets: Record<number, number> = {};
    for (let h = 0; h < 24; h++) buckets[h] = 0;
    (aggregates?.aggregates ?? []).forEach((a) => {
      const h = parseInt(a.hour, 10);
      if (!Number.isNaN(h) && h >= 0 && h < 24) buckets[h] = (buckets[h] ?? 0) + (a.count || 0);
    });
    return buckets;
  })();
  const maxByHour = Math.max(1, ...Object.values(byHour));

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['events'] });
    queryClient.invalidateQueries({ queryKey: ['aggregates'] });
  };
  const exportCsv = () => {
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
    a.download = `behaviors_export_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div>
          <h1 className="text-xl font-semibold text-cyan-400 mb-1">Behaviors &amp; tracking</h1>
          <p className="text-zinc-500 text-sm">
            Rules, events, and activity in one place. Summary by behavior type, activity over time, and a filterable event feed. Aligns with enterprise VMS behavior and tracking workflows.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={refresh} className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm" title="Refresh events and aggregates">Refresh</button>
          <button type="button" onClick={exportCsv} disabled={list.length === 0} className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 text-zinc-200 text-sm" title="Export current event list as CSV">Export CSV</button>
        </div>
      </div>

      {/* Summary cards */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {eventsLoading ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : (
          <>
            {BEHAVIOR_TYPES.map((t) => (
              <div
                key={t}
                className="rounded-lg bg-zinc-900 border border-zinc-700 p-3"
                title={getEventTypeDescription(t)}
              >
                <div className="text-xs font-medium text-zinc-500 uppercase tracking-wide">{getEventTypeLabel(t)}</div>
                <div className="mt-1 text-2xl font-semibold text-zinc-100">{byType[t] ?? 0}</div>
                <div className="text-xs text-zinc-500">in range</div>
              </div>
            ))}
            <Link
              to="/events"
              className="rounded-lg bg-zinc-900 border border-amber-600/50 p-3 hover:border-amber-500 block"
              title={FLAGS.NEEDS_REVIEW.title}
            >
              <div className="text-xs font-medium text-amber-400/90 uppercase tracking-wide">Needs review</div>
              <div className="mt-1 text-2xl font-semibold text-amber-400">{unackCount}</div>
              <div className="text-xs text-zinc-500">unacknowledged</div>
            </Link>
          </>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active triggers / rules */}
        <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
          <h2 className="text-sm font-medium text-cyan-400 uppercase tracking-wide mb-2">Active triggers</h2>
          <p className="text-zinc-500 text-xs mb-3">
            Behaviors that generate alerts. Configure loiter zones and crossing lines in Settings.
          </p>
          <ul className="space-y-2 text-sm text-zinc-300">
            <li className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-500" />
              <span>Motion detection — pixel change in frame</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <span>Loitering — dwell time in zone</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>Line crossing — virtual line cross</span>
            </li>
          </ul>
          <Link to="/settings" className="mt-3 inline-block text-xs text-cyan-400 hover:text-cyan-300">
            Configure in Settings →
          </Link>
        </section>

        {/* Activity by hour (today) */}
        <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4 lg:col-span-2">
          <h2 className="text-sm font-medium text-cyan-400 uppercase tracking-wide mb-2">Activity today (by hour)</h2>
          <p className="text-zinc-500 text-xs mb-3">
            Event density by hour for quick pattern review. Peak hours show higher bars.
          </p>
          {aggLoading ? (
            <div className="h-24 flex items-center justify-center text-zinc-500 text-sm">Loading…</div>
          ) : (
            <div className="flex items-end gap-0.5 h-24" aria-label="Events per hour">
              {Array.from({ length: 24 }, (_, i) => (
                <div
                  key={i}
                  className="flex-1 min-w-0 flex flex-col justify-end group"
                  title={`${i}:00 – ${(byHour[i] ?? 0)} events`}
                >
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
      </div>

      {/* Event feed */}
      <section className="mt-6 rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
        <div className="p-3 border-b border-zinc-700 flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-medium text-cyan-400 uppercase tracking-wide mr-2">Event feed</h2>
          <select
            value={dateRangeIndex}
            onChange={(e) => setDateRangeIndex(Number(e.target.value))}
            className="px-2 py-1 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs"
            aria-label="Date range"
          >
            {DATE_RANGES.map((r, i) => (
              <option key={r.label} value={i}>{r.label}</option>
            ))}
          </select>
          <select
            value={behaviorFilter}
            onChange={(e) => setBehaviorFilter(e.target.value)}
            className="px-2 py-1 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs"
            aria-label="Filter by behavior"
          >
            <option value="">All behaviors</option>
            {BEHAVIOR_TYPES.map((t) => (
              <option key={t} value={t}>{getEventTypeLabel(t)}</option>
            ))}
          </select>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-2 py-1 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs"
            aria-label="Filter by severity"
          >
            <option value="">All severities</option>
            <option value="high">{getSeverityLabel('high')}</option>
            <option value="medium">{getSeverityLabel('medium')}</option>
            <option value="low">{getSeverityLabel('low')}</option>
          </select>
          <span className="text-zinc-500 text-xs ml-auto">{list.length} events</span>
        </div>
        <div className="max-h-[360px] overflow-y-auto">
          {eventsLoading ? (
            <>
              {[1, 2, 3, 4, 5, 6, 7].map((i) => <EventRowSkeleton key={i} />)}
            </>
          ) : list.length === 0 ? (
            <div className="p-8 text-center text-zinc-500 text-sm">No events in this range. Change filters or try Timeline.</div>
          ) : (
            [...list]
              .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
              .slice(0, 80)
              .map((e) => <FeedRow key={e.id} e={e} onAck={(id) => ack.mutate(id)} />)
          )}
        </div>
        <div className="p-2 border-t border-zinc-700 flex flex-wrap gap-2 text-xs">
          <Link to="/events" className="text-cyan-400 hover:text-cyan-300">Events (full list)</Link>
          <span className="text-zinc-600">|</span>
          <Link to="/timeline" className="text-cyan-400 hover:text-cyan-300">Timeline</Link>
          <span className="text-zinc-600">|</span>
          <Link to="/log" className="text-cyan-400 hover:text-cyan-300">Activity log</Link>
          <span className="text-zinc-600">|</span>
          <Link to="/analytics" className="text-cyan-400 hover:text-cyan-300">Analytics</Link>
          <span className="text-zinc-600">|</span>
          <Link to="/map" className="text-cyan-400 hover:text-cyan-300">Map</Link>
        </div>
      </section>
    </div>
  );
}
