import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchEvents, type EventRow } from '../api/client';
import { TimelineRowSkeleton } from '../components/Skeleton';
import { getEventTypeDescription, getSeverityLabel, getSeverityDescription, getBehaviorDescription, FLAGS } from '../labels';
import { usePlaybackAtMoment } from '../PlaybackContext';

const RANGES = [
  { label: 'Last 24 hours', date_from: () => new Date(Date.now() - 86400 * 1000).toISOString().slice(0, 10) },
  { label: 'Last 7 days', date_from: () => new Date(Date.now() - 7 * 86400 * 1000).toISOString().slice(0, 10) },
  { label: 'All', date_from: () => undefined },
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

function TimelineRow({ e, onPlayMoment }: { e: EventRow; onPlayMoment?: (e: EventRow) => void }) {
  const [expanded, setExpanded] = useState(false);
  const severity = e.severity || 'medium';
  const borderClass = severity === 'high' ? 'border-l-red-500' : severity === 'medium' ? 'border-l-amber-500' : 'border-l-zinc-600';
  const meta = e.metadata ? (() => { try { return JSON.parse(e.metadata); } catch { return null; } })() : null;
  const eventLabel = meta?.event ?? e.event_type;
  const eventDesc = meta?.event ? getBehaviorDescription(String(meta.event)) : getEventTypeDescription(e.event_type);
  const objectLabel = meta?.object ?? null;
  const emotionLabel = meta?.emotion ?? null;
  return (
    <div className={`border-b border-zinc-800/80 ${borderClass} border-l-4`}>
      <div className="flex items-center gap-2 w-full">
      <button
        type="button"
        onClick={() => setExpanded((x) => !x)}
        className="flex-1 flex flex-wrap items-center gap-3 py-2.5 px-2 text-left text-sm hover:bg-zinc-800/50 rounded-r min-w-0"
      >
        <span className="font-mono text-zinc-400 shrink-0 w-44">{e.timestamp}</span>
        <span className="text-cyan-400 font-medium" title={eventDesc || undefined}>{eventLabel}</span>
        {!e.acknowledged_at && (
          <span className="px-1.5 py-0.5 rounded text-xs bg-amber-500/20 text-amber-400" title={FLAGS.NEEDS_REVIEW.title}>{FLAGS.NEEDS_REVIEW.label}</span>
        )}
        {severity === 'high' && (
          <span className="px-1.5 py-0.5 rounded text-xs bg-red-500/20 text-red-400" title={FLAGS.HIGH_PRIORITY.title}>{FLAGS.HIGH_PRIORITY.label}</span>
        )}
        {objectLabel != null && objectLabel !== 'None' && <span className="text-zinc-300">{objectLabel}</span>}
        {emotionLabel != null && emotionLabel !== 'Neutral' && <span className="text-zinc-400">{emotionLabel}</span>}
        <SeverityBadge s={severity} />
        {e.camera_id && <span className="text-zinc-500">Cam {e.camera_id}</span>}
        {e.acknowledged_at && <span className="text-zinc-600 text-xs" title={FLAGS.ACKNOWLEDGED.title}>{FLAGS.ACKNOWLEDGED.label}</span>}
        <span className="ml-auto text-zinc-600">{expanded ? '−' : '+'}</span>
      </button>
      {onPlayMoment && (
        <button type="button" onClick={() => onPlayMoment(e)} className="shrink-0 px-2 py-1 rounded text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200 mr-2" title="Play recording at this moment">Play</button>
      )}
      </div>
      {expanded && (meta || e.acknowledged_by || e.timestamp_utc) && (
        <div className="px-2 pb-2 pt-0 text-xs text-zinc-500 bg-zinc-900/50 rounded-b-r">
          {e.timestamp_utc && <p title="Chain of custody (UTC)">UTC: {e.timestamp_utc}</p>}
          {e.acknowledged_by && <p>Acknowledged by: {e.acknowledged_by}</p>}
          {meta && typeof meta === 'object' && (
            <>
              {(meta.pose != null || meta.scene != null || meta.crowd_count != null || meta.license_plate != null) && (
                <p className="mt-1">
                  {meta.pose != null && <span>Pose: {String(meta.pose)} </span>}
                  {meta.scene != null && <span>Scene: {String(meta.scene)} </span>}
                  {meta.crowd_count != null && <span>Crowd: {meta.crowd_count} </span>}
                  {meta.license_plate && <span>Plate: {meta.license_plate}</span>}
                </p>
              )}
              <pre className="mt-1 overflow-x-auto">{JSON.stringify(meta, null, 2)}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function Timeline() {
  const queryClient = useQueryClient();
  const [rangeIndex, setRangeIndex] = useState(0);
  const range = RANGES[rangeIndex];
  const dateFrom = range.date_from();
  const { openPlaybackAtMoment } = usePlaybackAtMoment() ?? {};
  const { data: events, isLoading, error } = useQuery({
    queryKey: ['events', 'timeline', dateFrom ?? 'all'],
    queryFn: () => fetchEvents({ limit: 500, date_from: dateFrom }),
  });

  if (error) return <div className="p-4 text-red-400">Error: {(error as Error).message}</div>;

  const sorted = [...(events ?? [])].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  const exportCsv = () => {
    if (sorted.length === 0) return;
    const headers = ['id', 'timestamp', 'event_type', 'severity', 'camera_id', 'acknowledged_at', 'metadata'];
    const escape = (v: unknown) => '"' + String(v != null ? v : '').replace(/"/g, '""') + '"';
    const rows = sorted.map((e) =>
      headers.map((h) => escape((e as Record<string, unknown>)[h])).join(',')
    );
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `timeline_${dateFrom ?? 'all'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold text-cyan-400 mb-1">Timeline</h1>
      <p className="text-zinc-500 text-sm mb-4">Acquired events by time (newest first). Click a row to expand metadata.</p>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {RANGES.map((r, i) => (
          <button
            key={r.label}
            type="button"
            onClick={() => setRangeIndex(i)}
            className={`px-3 py-1.5 rounded text-sm font-medium ${i === rangeIndex ? 'bg-cyan-600 text-black' : 'bg-zinc-800 text-zinc-400 hover:text-white'}`}
          >
            {r.label}
          </button>
        ))}
        <button type="button" onClick={() => queryClient.invalidateQueries({ queryKey: ['events'] })} className="px-3 py-1.5 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200" title="Reload events">Refresh</button>
        <button type="button" onClick={exportCsv} disabled={sorted.length === 0} className="px-3 py-1.5 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50" title="Download timeline as CSV">Export CSV</button>
      </div>
      <div className="rounded-lg border border-zinc-800 overflow-hidden">
        {isLoading ? (
          <>
            {[1, 2, 3, 4, 5, 6, 7].map((i) => <TimelineRowSkeleton key={i} />)}
          </>
        ) : sorted.length === 0 ? (
          <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 p-8 text-center">
            <p className="text-zinc-500 font-medium">No events in this range</p>
            <p className="text-zinc-600 text-sm mt-1">Select a different range or wait for new acquired data.</p>
          </div>
        ) : (
          sorted.map((e: EventRow) => <TimelineRow key={e.id} e={e} onPlayMoment={openPlaybackAtMoment} />)
        )}
      </div>
    </div>
  );
}
