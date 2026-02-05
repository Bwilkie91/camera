import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { usePlaybackAtMoment } from './PlaybackContext';
import type { EventRow } from './api/client';

/**
 * When the app is opened with ?playback_ts= and optionally ?playback_camera_id=
 * (e.g. from SOC dashboard "Play at moment" link), open the playback modal
 * with a synthetic event and clear the params from the URL.
 */
export default function PlaybackFromUrl() {
  const location = useLocation();
  const { openPlaybackAtMoment } = usePlaybackAtMoment() ?? {};

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const ts = params.get('playback_ts');
    if (!ts || !openPlaybackAtMoment) return;
    const cameraId = params.get('playback_camera_id');
    const synthetic: EventRow = {
      id: 0,
      event_type: 'event',
      camera_id: cameraId ?? null,
      timestamp: ts,
      metadata: null,
      severity: 'medium',
      acknowledged_by: null,
      acknowledged_at: null,
    };
    openPlaybackAtMoment(synthetic);
    const cleanUrl = location.pathname + (location.hash || '');
    window.history.replaceState({}, '', cleanUrl);
  }, [location.search, location.pathname, location.hash, openPlaybackAtMoment]);

  return null;
}
