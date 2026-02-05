import { useState, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchSites, fetchCameraPositions, fetchMapConfig, fetchSpatialHeatmap, fetchWorldHeatmap } from '../api/client';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix default marker icons in webpack/vite (Leaflet uses file paths that break in bundlers)
const defaultIcon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});
L.Marker.prototype.options.icon = defaultIcon;

const dateTo = () => new Date().toISOString().slice(0, 10);
const dateFrom = () => new Date(Date.now() - 7 * 86400 * 1000).toISOString().slice(0, 10);

function SpatialHeatmapOverlay({ data }: { data: { grid_rows: number; grid_cols: number; cells: { i: number; j: number; count: number }[]; interval_seconds: number } }) {
  const { grid_rows, grid_cols, cells, interval_seconds } = data;
  const byCell = useMemo(() => {
    const m: Record<string, number> = {};
    for (const c of cells) m[`${c.i},${c.j}`] = c.count;
    return m;
  }, [cells]);
  const maxCount = useMemo(() => Math.max(1, ...cells.map((c) => c.count)), [cells]);
  return (
    <div className="inline-block border border-zinc-700 rounded overflow-hidden" style={{ width: 160, aspectRatio: '1' }}>
      <div
        className="grid w-full h-full gap-px p-px bg-zinc-800"
        style={{ gridTemplateColumns: `repeat(${grid_cols}, 1fr)`, gridTemplateRows: `repeat(${grid_rows}, 1fr)` }}
      >
        {Array.from({ length: grid_rows * grid_cols }, (_, idx) => {
          const j = Math.floor(idx / grid_cols);
          const i = idx % grid_cols;
          const count = byCell[`${i},${j}`] ?? 0;
          const pct = maxCount ? (count / maxCount) * 100 : 0;
          return (
            <div
              key={`${i}-${j}`}
              className="min-w-0 min-h-0 rounded-sm"
              style={{ backgroundColor: `rgba(6, 182, 212, ${0.1 + (pct / 100) * 0.9})` }}
              title={`${count} (${count * interval_seconds}s)`}
            />
          );
        })}
      </div>
    </div>
  );
}

function WorldHeatmapOverlay({ data }: { data: { grid_rows: number; grid_cols: number; cells: { i: number; j: number; count: number }[]; interval_seconds: number } }) {
  const { grid_rows, grid_cols, cells, interval_seconds } = data;
  const byCell = useMemo(() => {
    const m: Record<string, number> = {};
    for (const c of cells) m[`${c.i},${c.j}`] = c.count;
    return m;
  }, [cells]);
  const maxCount = useMemo(() => Math.max(1, ...cells.map((c) => c.count)), [cells]);
  const cellW = 100 / grid_cols;
  const cellH = 100 / grid_rows;
  return (
    <div className="absolute inset-0 pointer-events-none z-[1]" aria-hidden>
      {Array.from({ length: grid_rows * grid_cols }, (_, idx) => {
        const j = Math.floor(idx / grid_cols);
        const i = idx % grid_cols;
        const count = byCell[`${i},${j}`] ?? 0;
        const pct = maxCount ? (count / maxCount) * 100 : 0;
        return (
          <div
            key={`${i}-${j}`}
            className="absolute"
            style={{
              left: `${i * cellW}%`,
              top: `${j * cellH}%`,
              width: `${cellW}%`,
              height: `${cellH}%`,
              backgroundColor: `rgba(6, 182, 212, ${0.15 + (pct / 100) * 0.75})`,
            }}
            title={`${count} (${count * interval_seconds}s)`}
          />
        );
      })}
    </div>
  );
}

export default function Map({ embedded }: { embedded?: boolean }) {
  const queryClient = useQueryClient();
  const { data: sites } = useQuery({ queryKey: ['sites'], queryFn: fetchSites });
  const { data: mapConfig } = useQuery({ queryKey: ['mapConfig'], queryFn: fetchMapConfig });
  const [siteId, setSiteId] = useState('default');
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showWorldHeatmap, setShowWorldHeatmap] = useState(false);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['sites'] });
    queryClient.invalidateQueries({ queryKey: ['mapConfig'] });
    queryClient.invalidateQueries({ queryKey: ['camera_positions', siteId] });
    queryClient.invalidateQueries({ queryKey: ['spatialHeatmapMap', dateFrom(), dateTo()] });
    queryClient.invalidateQueries({ queryKey: ['worldHeatmapMap', dateFrom(), dateTo()] });
  };
  useEffect(() => {
    if (sites?.length && (!siteId || !sites.some((s) => s.id === siteId))) {
      queueMicrotask(() => setSiteId(sites[0].id));
    }
  }, [sites, siteId]);
  const currentSite = sites?.find((s) => s.id === siteId) ?? sites?.[0];
  const { data: positions } = useQuery({
    queryKey: ['camera_positions', siteId],
    queryFn: () => fetchCameraPositions(siteId),
    enabled: !!siteId,
  });
  const firstCameraId = positions?.[0]?.camera_id ?? '0';
  const { data: spatialHeatmap } = useQuery({
    queryKey: ['spatialHeatmapMap', dateFrom(), dateTo(), firstCameraId],
    queryFn: () => fetchSpatialHeatmap({ date_from: dateFrom(), date_to: dateTo(), camera_id: firstCameraId, grid_size: 12 }),
    enabled: showHeatmap && !!firstCameraId,
  });
  const mapUrl = currentSite?.map_url?.trim();
  const { data: worldHeatmap } = useQuery({
    queryKey: ['worldHeatmapMap', dateFrom(), dateTo()],
    queryFn: () => fetchWorldHeatmap({ date_from: dateFrom(), date_to: dateTo(), grid_size: 16 }),
    enabled: showWorldHeatmap && !!mapUrl,
  });
  const useOsm = !mapUrl && mapConfig?.map;
  const center: [number, number] = mapConfig?.map
    ? [mapConfig.map.default_lat, mapConfig.map.default_lon]
    : [51.505, -0.09];
  const zoom = mapConfig?.map?.default_zoom ?? 13;
  const tileUrl = mapConfig?.map?.tile_url ?? 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  const attribution = mapConfig?.map?.attribution ?? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

  return (
    <div className={embedded ? '' : 'p-3 sm:p-4'}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        {!embedded && <h1 className="text-lg sm:text-xl font-semibold text-cyan-400">Map</h1>}
        {embedded && <h2 className="text-sm font-medium text-zinc-400">Map</h2>}
        <button type="button" onClick={refresh} className="touch-target px-3 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200" title="Reload sites and camera positions">Refresh</button>
      </div>
      {sites && sites.length > 1 && (
        <div className="mb-3">
          <label className="text-zinc-400 text-sm mr-2">Site:</label>
          <select
            value={siteId}
            onChange={(e) => setSiteId(e.target.value)}
            className="touch-target min-h-[44px] bg-zinc-800 border border-zinc-600 rounded px-3 py-2 text-zinc-200 text-sm"
          >
            {sites.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
      )}
      <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden relative min-h-[240px] sm:min-h-[320px]" style={{ aspectRatio: '16/10', maxHeight: '70vh' }}>
        {mapUrl ? (
          <div className="relative w-full h-full">
            <img src={mapUrl} alt="Site map" className="w-full h-full object-contain" />
            {(positions ?? []).map((pos) => (
              <div
                key={pos.camera_id}
                className="absolute w-6 h-6 rounded-full bg-cyan-500 border-2 border-white flex items-center justify-center text-xs font-bold text-black z-10"
                style={{ left: `${(pos.x ?? 0) * 100}%`, top: `${(pos.y ?? 0) * 100}%`, transform: 'translate(-50%, -50%)' }}
                title={pos.label ?? pos.camera_id}
              >
                {pos.camera_id}
              </div>
            ))}
            {showWorldHeatmap && worldHeatmap && worldHeatmap.cells.length > 0 && (
              <WorldHeatmapOverlay data={worldHeatmap} />
            )}
          </div>
        ) : useOsm ? (
          <MapContainer
            center={center}
            zoom={zoom}
            className="w-full h-full rounded-lg"
            style={{ height: '100%', minHeight: 300 }}
            scrollWheelZoom
          >
            <TileLayer url={tileUrl} attribution={attribution} />
            <Marker position={center}>
              <Popup>{currentSite?.name ?? 'Site'} — Cameras: {(positions ?? []).map((p) => p.label || p.camera_id).join(', ') || 'None'}</Popup>
            </Marker>
          </MapContainer>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-500 bg-zinc-800">
            No map image. Set map_url in backend sites table, or use OpenStreetMap (default) above.
          </div>
        )}
      </div>
      <p className="mt-2 text-zinc-500 text-sm">
        Cameras: {(positions ?? []).map((p) => p.label || p.camera_id).join(', ') || 'None'}
        {useOsm && ' · Map: OpenStreetMap'}
      </p>
      {!embedded && (
        <div className="mt-3 rounded-lg bg-zinc-900 border border-zinc-700 p-3">
          <button
            type="button"
            onClick={() => setShowHeatmap(!showHeatmap)}
            className="text-sm text-cyan-400 hover:text-cyan-300"
          >
            {showHeatmap ? '▼' : '▶'} Spatial heatmap overlay (camera view, last 7 days)
          </button>
          {showHeatmap && spatialHeatmap && (
            <div className="mt-2 flex items-start gap-3">
              <SpatialHeatmapOverlay data={spatialHeatmap} />
              <div className="text-xs text-zinc-500">
                Camera <span className="font-mono text-zinc-400">{firstCameraId}</span>. Where people appeared in frame (primary centroid). Hover cells for count.
              </div>
            </div>
          )}
          {showHeatmap && spatialHeatmap?.cells.length === 0 && (
            <p className="mt-2 text-zinc-500 text-sm">No centroid data for this period. Record with AI detail enabled to populate.</p>
          )}
          {mapUrl && (
            <>
              <button
                type="button"
                onClick={() => setShowWorldHeatmap(!showWorldHeatmap)}
                className="block mt-2 text-sm text-cyan-400 hover:text-cyan-300"
              >
                {showWorldHeatmap ? '▼' : '▶'} World heatmap (floor plan, last 7 days)
              </button>
              {showWorldHeatmap && worldHeatmap?.cells.length === 0 && (
                <p className="mt-2 text-zinc-500 text-sm">No world data. Configure homography.json and record to get world_x/world_y.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
