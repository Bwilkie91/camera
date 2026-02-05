import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchAggregates,
  fetchHeatmap,
  fetchZoneDwell,
  fetchVehicleActivity,
  fetchSpatialHeatmap,
  fetchWorldHeatmap,
  type AggregateRow,
} from '../api/client';

type SpatialHeatmapResponse = {
  grid_rows: number;
  grid_cols: number;
  cells: { i: number; j: number; count: number; person_seconds: number }[];
  interval_seconds: number;
};

function SpatialHeatmapGrid({ data }: { data: SpatialHeatmapResponse }) {
  const { grid_rows, grid_cols, cells, interval_seconds } = data;
  const byCell = useMemo(() => {
    const m: Record<string, number> = {};
    for (const c of cells) {
      m[`${c.i},${c.j}`] = c.count;
    }
    return m;
  }, [cells]);
  const maxCount = useMemo(() => Math.max(1, ...cells.map((c) => c.count)), [cells]);
  return (
    <div className="inline-block border border-zinc-800 rounded overflow-hidden" style={{ aspectRatio: `${grid_cols} / ${grid_rows}` }}>
      <div
        className="grid w-full h-full gap-px p-px bg-zinc-800"
        style={{ gridTemplateColumns: `repeat(${grid_cols}, minmax(0, 1fr))`, gridTemplateRows: `repeat(${grid_rows}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: grid_rows * grid_cols }, (_, idx) => {
          const j = Math.floor(idx / grid_cols);
          const i = idx % grid_cols;
          const count = byCell[`${i},${j}`] ?? 0;
          const pct = maxCount ? (count / maxCount) * 100 : 0;
          return (
            <div
              key={`${i}-${j}`}
              className="min-w-[4px] min-h-[4px] rounded-sm"
              style={{ backgroundColor: `rgba(6, 182, 212, ${0.1 + (pct / 100) * 0.9})` }}
              title={`(${i},${j}) ${count} detections, ${count * interval_seconds}s`}
            />
          );
        })}
      </div>
    </div>
  );
}

function AggregateTable({ rows }: { rows: AggregateRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 p-8 text-center">
        <p className="text-zinc-500 font-medium">No aggregate data</p>
        <p className="text-zinc-600 text-sm mt-1">Acquired AI/event data for the selected period will appear here.</p>
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800">
      <table className="w-full text-sm text-left">
        <thead>
          <tr className="border-b border-zinc-700 bg-zinc-900/80 text-zinc-400">
            <th className="p-3">Date</th>
            <th className="p-3">Hour</th>
            <th className="p-3">Event</th>
            <th className="p-3">Camera</th>
            <th className="p-3 text-right">Count</th>
            <th className="p-3 text-right">Crowd</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a, i) => (
            <tr key={i} className="border-b border-zinc-800 hover:bg-zinc-800/30">
              <td className="p-3">{a.date}</td>
              <td className="p-3 font-mono">{a.hour}:00</td>
              <td className="p-3 text-cyan-400 font-medium">{a.event}</td>
              <td className="p-3">{a.camera_id}</td>
              <td className="p-3 text-right">{a.count}</td>
              <td className="p-3 text-right">{a.total_crowd ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Analytics({ embedded }: { embedded?: boolean } = {}) {
  const queryClient = useQueryClient();
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));
  const [dateFrom, setDateFrom] = useState(() => new Date(Date.now() - 7 * 86400 * 1000).toISOString().slice(0, 10));
  const [spatialCameraId, setSpatialCameraId] = useState('');
  const [spatialGridSize, setSpatialGridSize] = useState(16);
  const [worldCameraId, setWorldCameraId] = useState('');
  const [worldGridSize, setWorldGridSize] = useState(16);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['analytics', dateFrom, dateTo] });
    queryClient.invalidateQueries({ queryKey: ['heatmap', dateFrom, dateTo] });
    queryClient.invalidateQueries({ queryKey: ['zoneDwell', dateFrom, dateTo] });
    queryClient.invalidateQueries({ queryKey: ['vehicleActivity', dateFrom, dateTo] });
    queryClient.invalidateQueries({ queryKey: ['spatialHeatmap', dateFrom, dateTo, spatialCameraId, spatialGridSize] });
    queryClient.invalidateQueries({ queryKey: ['worldHeatmap', dateFrom, dateTo, worldCameraId, worldGridSize] });
  };
  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics', dateFrom, dateTo],
    queryFn: () => fetchAggregates({ date_from: dateFrom, date_to: dateTo }),
  });
  const { data: heatmapData } = useQuery({
    queryKey: ['heatmap', dateFrom, dateTo],
    queryFn: () => fetchHeatmap({ date_from: dateFrom, date_to: dateTo, bucket_hours: 1 }),
  });
  const { data: zoneDwellData } = useQuery({
    queryKey: ['zoneDwell', dateFrom, dateTo],
    queryFn: () => fetchZoneDwell({ date_from: dateFrom, date_to: dateTo }),
  });
  const { data: vehicleData } = useQuery({
    queryKey: ['vehicleActivity', dateFrom, dateTo],
    queryFn: () => fetchVehicleActivity({ date_from: dateFrom, date_to: dateTo }),
  });
  const { data: spatialHeatmapData } = useQuery({
    queryKey: ['spatialHeatmap', dateFrom, dateTo, spatialCameraId || null, spatialGridSize],
    queryFn: () =>
      fetchSpatialHeatmap({
        date_from: dateFrom,
        date_to: dateTo,
        camera_id: spatialCameraId || undefined,
        grid_size: spatialGridSize,
      }),
  });
  const { data: worldHeatmapData } = useQuery({
    queryKey: ['worldHeatmap', dateFrom, dateTo, worldCameraId || null, worldGridSize],
    queryFn: () =>
      fetchWorldHeatmap({
        date_from: dateFrom,
        date_to: dateTo,
        camera_id: worldCameraId || undefined,
        grid_size: worldGridSize,
      }),
  });

  const rows = data?.aggregates ?? [];
  const cameraIds = useMemo(
    () => [...new Set((rows as AggregateRow[]).map((a) => a.camera_id).filter(Boolean))].sort(),
    [rows]
  );
  /* Used in spatial heatmap Camera/Grid selects below */
  void [setSpatialCameraId, setSpatialGridSize, cameraIds];
  const zoneDwellBuckets = zoneDwellData?.zone_dwell ?? [];
  const sightings = vehicleData?.sightings ?? [];
  const byPlate = vehicleData?.by_plate ?? {};
  const totalEvents = rows.reduce((s, a) => s + (a.count || 0), 0);
  const eventTypes = [...new Set(rows.map((a) => a.event))];
  const topEvent = rows.length ? rows.reduce((best, a) => (a.count > (best?.count ?? 0) ? a : best), rows[0]) : null;

  const heatmapGrid = useMemo(() => {
    const buckets = heatmapData?.heatmap ?? [];
    const byDayHour: Record<string, number> = {};
    for (const b of buckets) {
      const key = `${b.date}_${b.hour}`;
      byDayHour[key] = (byDayHour[key] ?? 0) + (b.count ?? 0);
    }
    const days = [...new Set(buckets.map((b) => b.date))].sort();
    const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
    const maxCount = Math.max(1, ...Object.values(byDayHour));
    return { byDayHour, days, hours, maxCount };
  }, [heatmapData]);

  const exportAggregatesCsv = () => {
    if (rows.length === 0) return;
    const headers = ['date', 'hour', 'event', 'camera_id', 'count', 'total_crowd'];
    const escape = (v: unknown) => '"' + String(v != null ? v : '').replace(/"/g, '""') + '"';
    const csv = headers.join(',') + '\n' + rows.map((a) => [a.date, a.hour, a.event, a.camera_id, a.count, a.total_crowd].map(escape).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aggregates_${dateFrom}_${dateTo}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) return <div className="p-4 text-zinc-400">Loading analytics...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {(error as Error).message}</div>;

  return (
    <div className={embedded ? '' : 'p-4'}>
      {!embedded && <h1 className="text-xl font-semibold text-cyan-400 mb-1">Analytics</h1>}
      {embedded && <h2 className="text-sm font-medium text-zinc-400 mb-2">Analytics</h2>}
      <p className="text-zinc-500 text-sm mb-3">
        Aggregates by event and camera. Set range then export CSV if needed.
      </p>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <label className="text-zinc-500 text-sm">From</label>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="px-2 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm"
        />
        <label className="text-zinc-500 text-sm">To</label>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="px-2 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm"
        />
        <button
          type="button"
          onClick={refresh}
          className="px-2 py-1.5 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200"
          title="Reload analytics data"
        >
          Refresh
        </button>
        <button
          type="button"
          onClick={exportAggregatesCsv}
          disabled={rows.length === 0}
          className="px-2 py-1.5 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50"
          title="Download current aggregates as CSV"
        >
          Aggregates (CSV)
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-3">
          <div className="text-xs text-zinc-500 uppercase tracking-wide">Total events</div>
          <div className="text-xl font-semibold text-zinc-100 mt-0.5">{totalEvents}</div>
        </div>
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-3">
          <div className="text-xs text-zinc-500 uppercase tracking-wide">Event types</div>
          <div className="text-xl font-semibold text-zinc-100 mt-0.5">{eventTypes.length}</div>
        </div>
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-3">
          <div className="text-xs text-zinc-500 uppercase tracking-wide">Top event</div>
          <div className="text-cyan-400 font-medium mt-0.5 truncate">{topEvent ? `${topEvent.event} (${topEvent.count})` : '—'}</div>
        </div>
      </div>
      {heatmapData && (heatmapGrid.days.length > 0 || heatmapGrid.hours.length > 0) && (
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-3 mb-4">
          <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Activity heatmap (events by day × hour)</h3>
          <div className="overflow-x-auto">
            <div className="inline-flex flex-col gap-0.5 min-w-0">
              <div className="flex gap-0.5 text-xs text-zinc-500 font-mono">
                <div className="w-20 shrink-0" />
                {heatmapGrid.hours.map((h) => (
                  <div key={h} className="w-6 text-center" title={`${h}:00`}>{h}</div>
                ))}
              </div>
              {heatmapGrid.days.slice(0, 14).map((d) => (
                <div key={d} className="flex gap-0.5 items-center">
                  <div className="w-20 shrink-0 text-xs text-zinc-500 font-mono">{d}</div>
                  {heatmapGrid.hours.map((h) => {
                    const count = heatmapGrid.byDayHour[`${d}_${h}`] ?? 0;
                    const pct = heatmapGrid.maxCount ? (count / heatmapGrid.maxCount) * 100 : 0;
                    return (
                      <div
                        key={`${d}_${h}`}
                        className="w-6 h-5 rounded-sm border border-zinc-800 flex items-center justify-center text-[10px] text-zinc-300"
                        style={{ backgroundColor: `rgba(6, 182, 212, ${0.15 + (pct / 100) * 0.85})` }}
                        title={`${d} ${h}:00 — ${count} events`}
                      >
                        {count > 0 ? count : ''}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      <AggregateTable rows={rows} />

      <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-3 mt-4">
        <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Spatial heatmap (camera view)</h3>
        <p className="text-zinc-500 text-sm mb-2">
          Where people appeared in frame (primary person centroid). Select camera and grid size, then refresh if needed.
        </p>
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <label className="text-zinc-400 text-sm">Camera</label>
          <select
            value={spatialCameraId}
            onChange={(e) => setSpatialCameraId(e.target.value)}
            className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-zinc-200 text-sm"
          >
            <option value="">All cameras</option>
            {cameraIds.map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
            {cameraIds.length === 0 && <option value="0">0</option>}
          </select>
          <label className="text-zinc-400 text-sm">Grid</label>
          <select
            value={spatialGridSize}
            onChange={(e) => setSpatialGridSize(Number(e.target.value))}
            className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-zinc-200 text-sm"
          >
            {[8, 12, 16, 24, 32].map((n) => (
              <option key={n} value={n}>{n}×{n}</option>
            ))}
          </select>
        </div>
        {spatialHeatmapData && spatialHeatmapData.cells.length > 0 ? (
          <SpatialHeatmapGrid data={spatialHeatmapData} />
        ) : (
          <p className="text-zinc-500 text-sm">No centroid data for this range. Record with AI on to populate.</p>
        )}
      </div>

      <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-3 mt-4">
        <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">World heatmap (floor plan)</h3>
        <p className="text-zinc-500 text-sm mb-2">
          Where people appeared on the floor plan (world_x, world_y). Requires homography.json per camera. Select camera and grid size.
        </p>
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <label className="text-zinc-400 text-sm">Camera</label>
          <select
            value={worldCameraId}
            onChange={(e) => setWorldCameraId(e.target.value)}
            className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-zinc-200 text-sm"
          >
            <option value="">All cameras</option>
            {cameraIds.map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
            {cameraIds.length === 0 && <option value="0">0</option>}
          </select>
          <label className="text-zinc-400 text-sm">Grid</label>
          <select
            value={worldGridSize}
            onChange={(e) => setWorldGridSize(Number(e.target.value))}
            className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-zinc-200 text-sm"
          >
            {[8, 12, 16, 24, 32].map((n) => (
              <option key={n} value={n}>{n}×{n}</option>
            ))}
          </select>
        </div>
        {worldHeatmapData && worldHeatmapData.cells.length > 0 ? (
          <SpatialHeatmapGrid data={worldHeatmapData} />
        ) : (
          <p className="text-zinc-500 text-sm">No world data for this range. Configure homography.json and record to get world_x/world_y.</p>
        )}
      </div>

      {zoneDwellBuckets.length > 0 && (
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-3 mt-4">
          <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Zone dwell (person-seconds per zone)</h3>
          <p className="text-zinc-500 text-sm mb-2">Crowd density: time spent per zone per hour. Interval: {zoneDwellData?.interval_seconds ?? 10}s per frame.</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-zinc-700 text-zinc-400">
                  <th className="p-2">Date</th>
                  <th className="p-2">Hour</th>
                  <th className="p-2">Camera</th>
                  <th className="p-2">Zone</th>
                  <th className="p-2 text-right">Person-sec</th>
                </tr>
              </thead>
              <tbody>
                {zoneDwellBuckets.slice(0, 50).map((b, i) => (
                  <tr key={i} className="border-b border-zinc-800 hover:bg-zinc-800/30">
                    <td className="p-2">{b.date}</td>
                    <td className="p-2 font-mono">{b.hour_bucket}:00</td>
                    <td className="p-2">{b.camera_id}</td>
                    <td className="p-2">{b.zone_index}</td>
                    <td className="p-2 text-right">{b.person_seconds}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {zoneDwellBuckets.length > 50 && <p className="text-zinc-500 text-xs mt-2">Showing first 50 of {zoneDwellBuckets.length}</p>}
          </div>
        </div>
      )}

      {(sightings.length > 0 || Object.keys(byPlate).length > 0) && (
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-3 mt-4">
          <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Vehicle activity (LPR)</h3>
          <p className="text-zinc-500 text-sm mb-2">License plate sightings and per-plate summary.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h4 className="text-zinc-400 text-sm font-medium mb-2">By plate</h4>
              <ul className="space-y-1 text-sm">
                {Object.entries(byPlate).slice(0, 15).map(([plate, info]) => (
                  <li key={plate} className="flex justify-between">
                    <span className="font-mono text-cyan-400">{plate}</span>
                    <span className="text-zinc-500">{info.count} sighting(s) · {info.camera_ids.join(', ')}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-zinc-400 text-sm font-medium mb-2">Recent sightings</h4>
              <div className="overflow-x-auto max-h-48 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-zinc-500 border-b border-zinc-700">
                      <th className="p-1 text-left">Plate</th>
                      <th className="p-1 text-left">Date / time</th>
                      <th className="p-1">Camera</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sightings.slice(0, 20).map((s, i) => (
                      <tr key={i} className="border-b border-zinc-800">
                        <td className="p-1 font-mono text-cyan-400">{s.license_plate}</td>
                        <td className="p-1">{s.date} {s.time}</td>
                        <td className="p-1">{s.camera_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
