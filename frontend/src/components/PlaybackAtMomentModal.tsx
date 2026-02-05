import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchRecordings, findRecordingAtMoment, fetchRecordingPlayBlob, type EventRow } from '../api/client';

export default function PlaybackAtMomentModal({
  event,
  onClose,
}: {
  event: EventRow | null;
  onClose: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { data: recordingsData } = useQuery({
    queryKey: ['recordings'],
    queryFn: () => fetchRecordings(),
    enabled: !!event,
  });
  const recordings = recordingsData?.recordings ?? [];
  const match = event ? findRecordingAtMoment(recordings, event.timestamp) : null;

  useEffect(() => {
    queueMicrotask(() => {
      setVideoError(null);
      setBlobUrl(null);
    });
  }, [match]);

  useEffect(() => {
    if (!match) return;
    let revoked = false;
    queueMicrotask(() => {
      setLoading(true);
      setVideoError(null);
    });
    fetchRecordingPlayBlob(match.name, true)
      .then((blob) => {
        if (revoked) return;
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
        setLoading(false);
      })
      .catch((err) => {
        if (revoked) return;
        setVideoError(err instanceof Error ? err.message : 'Playback failed.');
        setLoading(false);
      });
    return () => {
      revoked = true;
      setBlobUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [match]);

  useEffect(() => {
    if (!event || !match || !videoRef.current) return;
    const v = videoRef.current;
    const seek = () => {
      if (match.offsetSeconds > 0 && v.duration && !Number.isNaN(v.duration)) {
        v.currentTime = Math.min(match.offsetSeconds, v.duration * 0.99);
      }
    };
    v.addEventListener('loadedmetadata', seek);
    v.addEventListener('loadeddata', seek);
    v.addEventListener('canplay', seek);
    return () => {
      v.removeEventListener('loadedmetadata', seek);
      v.removeEventListener('loadeddata', seek);
      v.removeEventListener('canplay', seek);
    };
  }, [event, match]);

  useEffect(() => {
    const onEscape = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    if (event) window.addEventListener('keydown', onEscape);
    return () => window.removeEventListener('keydown', onEscape);
  }, [event, onClose]);

  if (!event) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
      role="dialog"
      aria-label="Playback at key moment"
    >
      <div
        className="bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2 p-3 border-b border-zinc-700">
          <h2 className="text-lg font-semibold text-cyan-400">
            Playback at key moment — {event.timestamp}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-zinc-700"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="p-3 flex flex-wrap items-center gap-2 border-b border-zinc-800">
          <span className="text-sm text-zinc-400">{event.event_type}</span>
          {event.camera_id && (
            <span className="text-sm text-zinc-500">Camera {event.camera_id}</span>
          )}
          <Link
            to="/"
            className="ml-auto px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium"
          >
            Go to Live view
          </Link>
        </div>
        <div className="flex-1 overflow-auto p-4">
          {match ? (
            <div className="space-y-2">
              <p className="text-xs text-zinc-500">
                Playing recording at event time (offset {match.offsetSeconds}s)
              </p>
              {loading && (
                <p className="text-zinc-400 text-sm">Loading recording…</p>
              )}
              {videoError && (
                <p className="text-amber-400 text-sm">
                  {videoError} You can still download the recording below from Export.
                </p>
              )}
              <video
                ref={videoRef}
                src={blobUrl ?? undefined}
                controls
                className="w-full rounded border border-zinc-700 bg-black aspect-video"
                preload="metadata"
                playsInline
                onError={() => setVideoError((prev) => prev || 'Playback failed. Try downloading from Export.')}
                onLoadedData={() => setVideoError(null)}
              >
                Your browser does not support video playback.
              </video>
            </div>
          ) : (
            <div className="rounded-lg bg-zinc-800/50 border border-zinc-700 p-6 text-center">
              <p className="text-zinc-400">
                No recording found that contains this event time.
              </p>
              <p className="text-zinc-500 text-sm mt-1">
                Recordings are created when you start recording from Live view. Go to Live and start
                recording to capture key moments.
              </p>
              <Link
                to="/"
                className="inline-block mt-3 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium"
              >
                Go to Live view
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
