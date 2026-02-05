import { createContext, useContext, useState, useCallback } from 'react';
import type { EventRow } from './api/client';
import PlaybackAtMomentModal from './components/PlaybackAtMomentModal';

type PlaybackContextValue = {
  openPlaybackAtMoment: (event: EventRow) => void;
};

const PlaybackContext = createContext<PlaybackContextValue | null>(null);

/* eslint-disable-next-line react-refresh/only-export-components -- context hook */
export function usePlaybackAtMoment() {
  const ctx = useContext(PlaybackContext);
  return ctx;
}

export function PlaybackProvider({ children }: { children: React.ReactNode }) {
  const [event, setEvent] = useState<EventRow | null>(null);
  const openPlaybackAtMoment = useCallback((e: EventRow) => setEvent(e), []);
  return (
    <PlaybackContext.Provider value={{ openPlaybackAtMoment }}>
      {children}
      <PlaybackAtMomentModal event={event} onClose={() => setEvent(null)} />
    </PlaybackContext.Provider>
  );
}
