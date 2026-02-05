import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchRecordingStatus,
  fetchEvents,
  fetchStreams,
  fetchHealth,
  fetchSystemStatus,
  fetchCamerasDetect,
  type CameraStatusItem,
  type DetectedCamera,
} from '../api/client';
import { CardSkeleton } from '../components/Skeleton';
import { getSeverityLabel, getSeverityDescription } from '../labels';

function Card({
  title,
  value,
  sub,
  to,
  status,
}: {
  title: string;
  value: React.ReactNode;
  sub?: string;
  to?: string;
  status?: 'ok' | 'warn' | 'error';
}) {
  const content = (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-4 flex flex-col">
      <div className="text-xs font-medium text-zinc-500 uppercase tracking-wide">{title}</div>
      <div className="mt-1 text-2xl font-semibold text-zinc-100">{value}</div>
      {sub && <div className="text-sm text-zinc-500 mt-0.5">{sub}</div>}
      {status === 'warn' && <div className="mt-2 text-amber-400 text-xs">Attention</div>}
      {status === 'error' && <div className="mt-2 text-red-400 text-xs">Issue</div>}
    </div>
  );
  return to ? (
    <Link to={to} className="block hover:border-cyan-600/50 transition-colors rounded-lg">
      {content}
    </Link>
  ) : (
    content
  );
}

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { data: recording, isLoading: recordingLoading } = useQuery({ queryKey: ['recording'], queryFn: fetchRecordingStatus, refetchInterval: 5000 });
  useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 10000 });
  const { data: streams, isLoading: streamsLoading } = useQuery({ queryKey: ['streams'], queryFn: fetchStreams });
  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  const { data: eventsRecent } = useQuery({
    queryKey: ['events', 'recent', today],
    queryFn: () => fetchEvents({ limit: 500, date_from: today }),
  });
  const { data: eventsUnack } = useQuery({
    queryKey: ['events', 'unack'],
    queryFn: () => fetchEvents({ limit: 100, acknowledged: 'false' }),
  });

  const { data: systemStatus } = useQuery({
    queryKey: ['system_status'],
    queryFn: fetchSystemStatus,
    refetchInterval: 10000,
  });
  const { data: detectData, refetch: refetchDetect, isFetching: detectLoading } = useQuery({
    queryKey: ['cameras_detect'],
    queryFn: fetchCamerasDetect,
    enabled: false,
  });

  const unackCount = eventsUnack?.length ?? 0;
  const recentCount = eventsRecent?.length ?? 0;
  const bySeverity = eventsRecent
    ? {
        high: eventsRecent.filter((e) => (e.severity || 'medium') === 'high').length,
        medium: eventsRecent.filter((e) => (e.severity || 'medium') === 'medium').length,
        low: eventsRecent.filter((e) => (e.severity || 'medium') === 'low').length,
      }
    : { high: 0, medium: 0, low: 0 };

  const formatUptime = (sec: number) => {
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m`;
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h}h ${m}m`;
  };
  const formatStorage = (bytes: number) =>
    bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : bytes >= 1e3 ? `${(bytes / 1e3).toFixed(1)} KB` : `${bytes} B`;

  const cameraStatusBadge = (c: CameraStatusItem) => {
    const cls = c.status === 'ok' ? 'text-emerald-400' : c.status === 'no_signal' ? 'text-amber-400' : 'text-red-400';
    return <span className={cls}>{c.status === 'ok' ? 'Online' : c.status === 'no_signal' ? 'No signal' : 'Offline'}</span>;
  };

  const cardsLoading = streamsLoading || recordingLoading;

  const analyticsActive = [
    systemStatus?.feature_flags?.lpr !== false && 'LPR',
    systemStatus?.feature_flags?.emotion !== false && 'emotion',
    systemStatus?.feature_flags?.audio_capture && 'audio',
    systemStatus?.feature_flags?.wifi_sniff && 'Wi‑Fi',
  ].filter(Boolean);
  const analyticsLabel = analyticsActive.length > 0 ? analyticsActive.join(', ') : 'motion, loitering, line-cross';

  return (
    <div className="p-4">
      {(recording?.recording || systemStatus?.recording) && (
        <div className="mb-4 rounded-lg border border-cyan-500/50 bg-cyan-500/10 px-4 py-2 flex flex-wrap items-center gap-3">
          <span className="text-cyan-400 font-medium">● Recording in progress</span>
          <span className="text-zinc-400 text-sm">
            AI analytics: {analyticsLabel}. Ensure signage is displayed where required.
          </span>
        </div>
      )}
      <h1 className="text-xl font-semibold text-cyan-400 mb-2">Dashboard</h1>
      <p className="text-zinc-500 text-sm mb-4">
        At-a-glance status: recording, events, streams, system health. Use <strong>Activity</strong> for one place to view feed, events (acknowledge), log, and charts.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cardsLoading ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : (
        <>
        <Card
          title="Recording"
          value={recording?.recording ? '● Live' : '○ Stopped'}
          sub={recording?.recording ? 'Recording in progress' : 'Start from Live view'}
          to="/"
          status={recording?.recording ? 'ok' : undefined}
        />
        <Card
          title="Events today"
          value={recentCount}
          sub={`${today}`}
          to="/activity?view=feed"
        />
        <Card
          title="Unacknowledged"
          value={unackCount}
          sub={unackCount > 0 ? 'Requires attention' : 'All clear'}
          to="/activity?view=events"
          status={unackCount > 0 ? 'warn' : 'ok'}
        />
        <Card
          title="Streams"
          value={streams?.length ?? 0}
          sub="Cameras"
          to="/"
        />
        </>
        )}
      </div>

      <section className="mt-6 rounded-lg bg-zinc-900 border border-zinc-700 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 className="text-sm font-medium text-cyan-400 uppercase tracking-wide">System Status &amp; Network Health</h2>
          <button
            type="button"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['recording'] });
              queryClient.invalidateQueries({ queryKey: ['health'] });
              queryClient.invalidateQueries({ queryKey: ['streams'] });
              queryClient.invalidateQueries({ queryKey: ['events'] });
              queryClient.invalidateQueries({ queryKey: ['system_status'] });
            }}
            className="px-2 py-1 rounded text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200"
            title="Refresh status and counts"
          >
            Refresh
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-4 text-sm mb-3">
              <span>
                <span className="text-zinc-500">Overall:</span>{' '}
                <span className={systemStatus?.status === 'ok' ? 'text-emerald-400' : 'text-amber-400'}>
                  {systemStatus?.status === 'ok' ? 'OK' : 'Degraded'}
                </span>
              </span>
              <span>
                <span className="text-zinc-500">Database:</span>{' '}
                <span className={systemStatus?.db_ok ? 'text-emerald-400' : 'text-red-400'}>
                  {systemStatus?.db_ok ? 'Connected' : 'Error'}
                </span>
              </span>
              <span>
                <span className="text-zinc-500">Uptime:</span>{' '}
                <span className="text-zinc-300">{systemStatus?.uptime_seconds != null ? formatUptime(systemStatus.uptime_seconds) : '—'}</span>
              </span>
              {systemStatus?.storage_used_bytes != null && (
                <>
                  <span>
                    <span className="text-zinc-500">Storage:</span>{' '}
                    <span className="text-zinc-300" title="Recordings folder">{formatStorage(systemStatus.storage_used_bytes)}</span>
                  </span>
                  {systemStatus.storage_free_bytes != null && (
                    <span title="Free space on recordings drive">
                      <span className="text-zinc-500">Free:</span>{' '}
                      <span className="text-zinc-300">{formatStorage(systemStatus.storage_free_bytes)}</span>
                    </span>
                  )}
                  <span>
                    <span className="text-zinc-500">Recordings:</span>{' '}
                    <span className="text-zinc-300">{systemStatus.recording_count ?? 0}</span>
                  </span>
                  {systemStatus.retention_days != null && systemStatus.retention_days > 0 && (
                    <span>
                      <span className="text-zinc-500">Retention:</span>{' '}
                      <span className="text-zinc-300">{systemStatus.retention_days} days</span>
                    </span>
                  )}
                </>
              )}
            </div>
            {systemStatus?.storage_free_bytes != null &&
              (systemStatus.storage_free_bytes < 1e9 ||
                (systemStatus.storage_total_bytes != null &&
                  systemStatus.storage_total_bytes > 0 &&
                  systemStatus.storage_free_bytes / systemStatus.storage_total_bytes < 0.05)) && (
              <div className="mt-2 px-3 py-2 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-200 text-sm flex items-center gap-2" role="alert">
                <span className="font-medium">Low disk space</span>
                <span>Free: {formatStorage(systemStatus.storage_free_bytes)} on recordings drive. Free up space or increase retention pruning.</span>
              </div>
            )}
            <p className="text-zinc-500 text-xs mb-2">
              Integrated cameras: real-time status from connected streams. Use &quot;Detect cameras&quot; to scan for local devices.
            </p>
            <button
              type="button"
              onClick={() => refetchDetect()}
              disabled={detectLoading}
              className="px-2 py-1 rounded text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-300 disabled:opacity-50"
            >
              {detectLoading ? 'Scanning…' : 'Detect cameras'}
            </button>
            {detectData?.detected && detectData.detected.length > 0 && (
              <div className="mt-2 text-xs text-zinc-500 space-y-1">
                <span>Detected: {detectData.detected.filter((d: DetectedCamera) => d.opened).length} usable.</span>
                <ul className="list-disc list-inside">
                  {detectData.detected.filter((d: DetectedCamera) => d.opened).map((d: DetectedCamera, i: number) => (
                    <li key={i}>{d.name ?? d.path}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-zinc-500 border-b border-zinc-700">
                  <th className="py-1 pr-2">Camera</th>
                  <th className="py-1 pr-2">Status</th>
                  <th className="py-1 pr-2">Resolution</th>
                  <th className="py-1 pr-2">Last seen</th>
                  <th className="py-1 pr-2">Last offline</th>
                </tr>
              </thead>
              <tbody>
                {(systemStatus?.cameras ?? []).map((c) => (
                  <tr key={c.id} className="border-b border-zinc-800">
                    <td className="py-1 pr-2">
                      <Link to="/" className="text-cyan-400 hover:underline">{c.name}</Link>
                    </td>
                    <td className="py-1 pr-2">
                      <span className="inline-flex items-center gap-1">
                        {cameraStatusBadge(c)}
                        {c.flapping && <span className="text-amber-400 text-xs" title="Status changed 3+ times in last 10 min">⚠ flapping</span>}
                      </span>
                    </td>
                    <td className="py-1 pr-2 text-zinc-500">{c.resolution ?? '—'}</td>
                    <td className="py-1 pr-2 text-zinc-500" title={c.last_frame_utc ?? undefined}>
                      {c.last_frame_utc ? (() => {
                        const sec = Math.floor((Date.now() - new Date(c.last_frame_utc!).getTime()) / 1000);
                        if (sec < 60) return 'Just now';
                        if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
                        return `${Math.floor(sec / 3600)}h ago`;
                      })() : '—'}
                    </td>
                    <td className="py-1 pr-2 text-zinc-500" title={c.last_offline_utc ?? undefined}>
                      {c.last_offline_utc ? (() => {
                        const sec = Math.floor((Date.now() - new Date(c.last_offline_utc!).getTime()) / 1000);
                        if (c.status === 'ok') {
                          if (sec < 60) return 'Just now';
                          if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
                          return `${Math.floor(sec / 3600)}h ago`;
                        }
                        if (sec < 60) return 'Since just now';
                        if (sec < 3600) return `Since ${Math.floor(sec / 60)}m ago`;
                        return `Since ${Math.floor(sec / 3600)}h ago`;
                      })() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(!systemStatus?.cameras || systemStatus.cameras.length === 0) && (
              <p className="text-zinc-500 text-sm py-2">No camera status. Configure CAMERA_SOURCES and open Live view to start streams.</p>
            )}
          </div>
        </div>
      </section>

      <section className="mt-4 rounded-lg bg-zinc-900/50 border border-zinc-800 p-3">
        <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">Today</h2>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <span className="text-zinc-400">Events: <span className="text-zinc-200 font-medium">{recentCount}</span></span>
          <span className="text-red-400/90" title={getSeverityDescription('high')}>{getSeverityLabel('high')}: {bySeverity.high}</span>
          <span className="text-amber-400/90" title={getSeverityDescription('medium')}>{getSeverityLabel('medium')}: {bySeverity.medium}</span>
          <span className="text-zinc-400" title={getSeverityDescription('low')}>{getSeverityLabel('low')}: {bySeverity.low}</span>
          <Link to="/activity" className="text-cyan-400 hover:text-cyan-300 ml-auto">View all in Activity →</Link>
        </div>
      </section>
    </div>
  );
}
