import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchStreams, fetchRecordingStatus, toggleRecording, moveCamera, toggleMotion } from '../api/client';

const RECENT_FPS_WINDOW_MS = 1000;

function StreamTile({ stream }: { stream: { id: string; name: string; type: string; url: string } }) {
  const [imgError, setImgError] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fps, setFps] = useState<number | null>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
  const frameTimesRef = useRef<number[]>([]);
  const streamUrl = (import.meta.env.VITE_API_URL || '') + stream.url;

  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(!!(document.fullscreenElement && document.fullscreenElement === viewerRef.current));
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const cutoff = now - RECENT_FPS_WINDOW_MS;
      frameTimesRef.current = frameTimesRef.current.filter((t) => t >= cutoff);
      setFps(frameTimesRef.current.length);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const onFrameLoad = () => {
    frameTimesRef.current.push(Date.now());
    const cutoff = Date.now() - RECENT_FPS_WINDOW_MS;
    if (frameTimesRef.current.length > 60) {
      frameTimesRef.current = frameTimesRef.current.filter((t) => t >= cutoff);
    }
  };

  const toggleFullscreen = () => {
    if (!viewerRef.current) return;
    if (document.fullscreenElement === viewerRef.current) {
      document.exitFullscreen();
    } else {
      viewerRef.current.requestFullscreen();
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'f' || e.key === 'F') {
      e.preventDefault();
      toggleFullscreen();
    }
  };

  return (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
      <div className="p-2 text-sm font-medium text-cyan-400 border-b border-zinc-700 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-bold bg-red-500/20 text-red-400">LIVE</span>
          {stream.name}
        </span>
        {fps != null && (
          <span className="text-xs text-zinc-500 tabular-nums" title="Frames per second (MJPEG refresh)">~{fps} fps</span>
        )}
      </div>
      <div
        ref={viewerRef}
        role="region"
        tabIndex={0}
        aria-label={`${stream.name} stream. Press F for fullscreen.`}
        title="Focus and press F for fullscreen"
        className="aspect-video bg-black relative focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
        onKeyDown={onKeyDown}
      >
        {stream.type === 'mjpeg' ? (
          imgError ? (
            <div className="w-full h-full flex items-center justify-center text-zinc-500 text-sm">No signal</div>
          ) : (
            <img
              src={streamUrl}
              alt={stream.name}
              className="w-full h-full object-contain"
              onError={() => setImgError(true)}
              onLoad={onFrameLoad}
            />
          )
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-500">Unsupported type: {stream.type}</div>
        )}
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); toggleFullscreen(); }}
          className="touch-target absolute top-2 right-2 px-3 py-2 rounded text-sm font-medium bg-black/60 hover:bg-black/80 text-white border border-zinc-600"
          aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
        >
          {isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
        </button>
      </div>
    </div>
  );
}

export default function Live() {
  const queryClient = useQueryClient();
  const { data: streams, isLoading, error } = useQuery({
    queryKey: ['streams'],
    queryFn: fetchStreams,
  });
  const { data: recordingStatus } = useQuery({
    queryKey: ['recording'],
    queryFn: fetchRecordingStatus,
    refetchInterval: 2000,
  });
  const recording = useMutation({
    mutationFn: toggleRecording,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['recording'] }),
  });
  const ptz = useMutation({ mutationFn: moveCamera });
  const [motionOn, setMotionOn] = useState(true);
  const motionMutation = useMutation({
    mutationFn: (enabled: boolean) => toggleMotion(enabled),
    onSuccess: (data) => setMotionOn(!!data.motion),
  });
  type GridPreset = '1' | '2' | '3';
  const [gridPreset, setGridPreset] = useState<GridPreset>('3');

  if (isLoading) return <div className="p-4 text-zinc-400">Loading streams...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {(error as Error).message}</div>;
  if (!streams?.length) return <div className="p-4 text-zinc-400">No streams configured.</div>;

  const primaryStream = streams[0];
  const gridClass =
    gridPreset === '1' ? 'grid-cols-1' : gridPreset === '2' ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3';

  return (
    <div className="p-3 sm:p-4">
      {/* Top container: live feed + what you're seeing / what's happening */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4 mb-4 sm:mb-6" aria-label="Live feed and overview">
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
          <div className="px-3 py-2 border-b border-zinc-700 flex items-center gap-2 text-sm font-medium text-cyan-400">
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-bold bg-red-500/20 text-red-400">LIVE</span>
            {primaryStream?.name ?? 'Live feed'}
          </div>
          <div className="aspect-video bg-black relative">
            {primaryStream && (
              <img
                src={(import.meta.env.VITE_API_URL || '') + primaryStream.url}
                alt={primaryStream.name + ' live feed'}
                className="w-full h-full object-contain"
              />
            )}
            {!primaryStream && (
              <div className="absolute inset-0 flex items-center justify-center text-zinc-500 text-sm p-4">No stream</div>
            )}
          </div>
        </div>
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
          <h2 className="text-sm font-semibold text-zinc-200 mb-2">What you're seeing</h2>
          <p className="text-zinc-400 text-sm mb-3">
            Real-time video from your configured camera. The feed above shows the primary stream; all streams and controls are below.
          </p>
          <h2 className="text-sm font-semibold text-zinc-200 mb-2">What's happening</h2>
          <p className="text-zinc-400 text-sm mb-2">
            AI analyzes the video for motion, loitering, and line crossing. Detected events appear in Activity (events, timeline, chart). You can start or stop recording, toggle motion, use PTZ, and export data from Export.
          </p>
          <ul className="text-zinc-500 text-xs list-disc list-inside space-y-1">
            <li>Motion — movement in the frame</li>
            <li>Loitering — person or object in a zone longer than the threshold</li>
            <li>Line cross — crossing a configured virtual line</li>
          </ul>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 sm:gap-4 mb-4">
        <h1 className="text-lg sm:text-xl font-semibold text-cyan-400">Live View</h1>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['streams'] })}
            className="touch-target px-3 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200"
            title="Reload stream list"
          >
            Refresh streams
          </button>
          <span className="text-zinc-500 text-sm">Grid:</span>
          {(['1', '2', '3'] as const).map((n) => (
            <button
              key={n}
              type="button"
              title={`${n}×${n} layout`}
              onClick={() => setGridPreset(n)}
              className={`touch-target px-3 py-2 rounded text-sm font-medium ${gridPreset === n ? 'bg-cyan-600 text-black' : 'bg-zinc-700 hover:bg-zinc-600 text-zinc-200'}`}
            >
              {n}×{n}
            </button>
          ))}
          <span className={recordingStatus?.recording ? 'text-red-400 text-sm font-medium' : 'text-zinc-500 text-sm'}>
            {recordingStatus?.recording ? '● Recording' : '○ Not recording'}
          </span>
          <button
            title="Start or stop recording (evidence saved as AVI in recordings list)"
            onClick={() => recording.mutate()}
            disabled={recording.isPending}
            className="touch-target px-3 py-2 rounded text-sm font-medium bg-red-600/80 hover:bg-red-500 text-white disabled:opacity-50"
          >
            {recording.isPending ? '…' : recordingStatus?.recording ? 'Stop Recording' : 'Start Recording'}
          </button>
          <button
            type="button"
            title="Toggle motion detection"
            onClick={() => motionMutation.mutate(!motionOn)}
            disabled={motionMutation.isPending}
            className="touch-target px-3 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50"
          >
            {motionMutation.isPending ? '…' : motionOn ? 'Motion on' : 'Motion off'}
          </button>
          <span className="text-zinc-500 text-sm" title="Pan-tilt-zoom: requires ONVIF or GPIO PTZ">PTZ:</span>
          <button title="Pan camera left" onClick={() => ptz.mutate('left')} disabled={ptz.isPending} className="touch-target px-2 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50">Left</button>
          <button title="Pan camera right" onClick={() => ptz.mutate('right')} disabled={ptz.isPending} className="touch-target px-2 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50">Right</button>
          <button title="Stop PTZ movement" onClick={() => ptz.mutate('stop')} disabled={ptz.isPending} className="touch-target px-2 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50">Stop</button>
          {ptz.isError && <span className="text-red-400 text-sm">{(ptz.error as Error).message}</span>}
        </div>
      </div>
      <div className={`grid ${gridClass} gap-3 sm:gap-4`}>
        {streams.map((s) => (
          <StreamTile key={s.id} stream={s} />
        ))}
      </div>
    </div>
  );
}
