import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { fetchMe, autoLogin, type Me } from './api/client';

export const REDIRECT_KEY = 'vigil_redirect_after_login';
/* eslint-disable-next-line react-refresh/only-export-components -- shared auth helpers */
export function getRedirectPath(): string {
  try {
    const s = sessionStorage.getItem(REDIRECT_KEY);
    sessionStorage.removeItem(REDIRECT_KEY);
    return s && s.startsWith('/') && s !== '/login' ? s : '/';
  } catch {
    return '/';
  }
}

type AuthContextValue = {
  auth: Me | null;
  setAuth: (me: Me | null) => void;
  refetchAuth: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuthState] = useState<Me | null>(null);

  const refetchAuth = useCallback(async () => {
    try {
      let me = await fetchMe();
      if (!me.authenticated) {
        const auto = await autoLogin();
        if (auto.success) me = await fetchMe();
      }
      setAuthState(me);
    } catch {
      setAuthState({ authenticated: false });
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => refetchAuth());
  }, [refetchAuth]);

  const setAuth = useCallback((me: Me | null) => {
    setAuthState(me);
  }, []);

  return (
    <AuthContext.Provider value={{ auth, setAuth, refetchAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

/* eslint-disable-next-line react-refresh/only-export-components -- context hook */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
