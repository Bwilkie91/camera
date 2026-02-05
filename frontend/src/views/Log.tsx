import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchGetData, type AIDataRow } from '../api/client';
import { TimelineRowSkeleton } from '../components/Skeleton';
import { getBehaviorLabel, getBehaviorDescription } from '../labels';

const RANGES = [
  { label: 'Last 24h', date_from: () => new Date(Date.now() - 86400 * 1000).toISOString().slice(0, 10), date_to: () => new Date().toISOString().slice(0, 10) },
  { label: 'Last 7 days', date_from: () => new Date(Date.now() - 7 * 86400 * 1000).toISOString().slice(0, 10), date_to: () => new Date().toISOString().slice(0, 10) },
  { label: 'All', date_from: () => undefined, date_to: () => undefined },
] as const;

function LogLine({ row }: { row: AIDataRow }) {
  const time = row.time || '';
  const eventRaw = row.event || 'None';
  const eventLabel = getBehaviorLabel(eventRaw);
  const eventDesc = getBehaviorDescription(eventRaw);
  const obj = row.object || 'None';
  const emotion = row.emotion || 'Neutral';
  const pose = row.pose || '—';
  const scene = row.scene || '—';
  const crowd = row.crowd_count ?? '—';
  const plate = row.license_plate || '—';
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-1.5 px-2 border-b border-zinc-800/60 text-sm font-mono hover:bg-zinc-800/40 rounded">
      <span className="text-zinc-400 shrink-0 w-20" title={`${row.date} ${time}`}>[{time}]</span>
      <span className={eventRaw !== 'None' ? 'text-cyan-400 font-medium' : 'text-zinc-500'} title={eventDesc || undefined}>{eventLabel}</span>
      <span className="text-zinc-300">{obj}</span>
      <span className="text-zinc-300">{emotion}</span>
      <span className="text-zinc-500 text-xs">pose: {pose}</span>
      <span className="text-zinc-500 text-xs">scene: {scene}</span>
      <span className="text-zinc-500 text-xs">crowd: {String(crowd)}</span>
      {plate !== '—' && plate !== '' && <span className="text-amber-400/90 text-xs">plate: {plate}</span>}
      {row.camera_id && <span className="text-zinc-600 text-xs">cam {row.camera_id}</span>}
    </div>
  );
}

export default function Log() {
  const queryClient = useQueryClient();
  const [rangeIndex, setRangeIndex] = useState(0);
  const range = RANGES[rangeIndex];
  const dateFrom = range.date_from();
  const dateTo = range.date_to();
  const { data: rows, isLoading, error } = useQuery({
    queryKey: ['get_data', 'log', dateFrom ?? 'all', dateTo ?? 'all'],
    queryFn: () => fetchGetData({ limit: 500, date_from: dateFrom, date_to: dateTo }),
  });

  const sorted = [...(rows ?? [])].sort((a, b) => {
    const tA = `${a.date} ${a.time}`;
    const tB = `${b.date} ${b.time}`;
    return tB.localeCompare(tA);
  });

  const exportCsv = () => {
    if (sorted.length === 0) return;
    const headers = ['date', 'time', 'event', 'object', 'emotion', 'pose', 'scene', 'crowd_count', 'license_plate', 'camera_id'];
    const escape = (v: unknown) => '"' + String(v != null ? v : '').replace(/"/g, '""') + '"';
    const rowsOut = sorted.map((r) =>
      [r.date, r.time, r.event ?? '', r.object ?? '', r.emotion ?? '', r.pose ?? '', r.scene ?? '', r.crowd_count ?? '', r.license_plate ?? '', r.camera_id ?? ''].map(escape).join(',')
    );
    const csv = headers.join(',') + '\n' + rowsOut.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `activity_log_${dateFrom ?? 'all'}_${dateTo ?? 'all'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (error) return <div className="p-4 text-red-400">Error: {(error as Error).message}</div>;

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold text-cyan-400 mb-1">Activity log</h1>
      <p className="text-zinc-500 text-sm mb-4">
        Detection log: time, behavior (event), object, emotion, pose, scene, crowd, license plate. Hover event for description. Sorted newest first.
      </p>
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
        <button type="button" onClick={() => queryClient.invalidateQueries({ queryKey: ['get_data'] })} className="px-3 py-1.5 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200" title="Reload log">Refresh</button>
        <button type="button" onClick={exportCsv} disabled={sorted.length === 0} className="px-3 py-1.5 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50" title="Download log as CSV">Export CSV</button>
      </div>
      <div className="rounded-lg border border-zinc-800 overflow-hidden bg-zinc-900/30">
        <div className="px-2 py-2 border-b border-zinc-700 text-xs text-zinc-500 font-mono flex flex-wrap gap-x-3 gap-y-1">
          <span className="w-20">[time]</span>
          <span>event</span>
          <span>object</span>
          <span>emotion</span>
          <span>pose</span>
          <span>scene</span>
          <span>crowd</span>
          <span>plate</span>
        </div>
        {isLoading ? (
          <>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => <TimelineRowSkeleton key={i} />)}
          </>
        ) : sorted.length === 0 ? (
          <div className="p-8 text-center text-zinc-500 text-sm">No detection data in this range.</div>
        ) : (
          sorted.map((row, i) => <LogLine key={`${row.date}-${row.time}-${i}`} row={row} />)
        )}
      </div>
    </div>
  );
}
