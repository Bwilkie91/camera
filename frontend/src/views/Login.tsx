import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth, getRedirectPath } from '../AuthContext';
import { login, verifyTotp, autoLogin } from '../api/client';

export default function Login() {
  const { refetchAuth } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [sessionMessage, setSessionMessage] = useState('');
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [autoSignInLoading, setAutoSignInLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  useEffect(() => {
    if (searchParams.get('timeout') === '1') setSessionMessage('Session expired. Please log in again.');
  }, [searchParams]);

  const handleAutoSignIn = async () => {
    setError('');
    setAutoSignInLoading(true);
    try {
      const result = await autoLogin();
      if (result?.success) {
        await refetchAuth();
        navigate(getRedirectPath(), { replace: true });
      } else {
        setError('Auto sign-in is disabled on this server.');
      }
    } catch {
      setError('Auto sign-in failed.');
    } finally {
      setAutoSignInLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const result = await login(username, password);
    setLoading(false);
    if (result.success && result.require_mfa && result.mfa_token) {
      setMfaToken(result.mfa_token);
    } else if (result.success) {
      await refetchAuth();
      navigate(getRedirectPath(), { replace: true });
    } else if (result.locked) {
      setError(result.locked_until_utc
        ? `Account locked. Try again after ${new Date(result.locked_until_utc).toLocaleString()}.`
        : 'Account temporarily locked due to too many failed attempts.');
    } else if (result.password_expired) {
      setError('Your password has expired. Contact an administrator to reset it.');
    } else {
      setError('Invalid username or password');
    }
  };

  const handleMfaSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mfaToken || !mfaCode.trim()) return;
    setError('');
    setLoading(true);
    const result = await verifyTotp(mfaToken, mfaCode.trim());
    setLoading(false);
    if (result.success) {
      await refetchAuth();
      navigate(getRedirectPath(), { replace: true });
    } else {
      setError('Invalid or expired code. Try again.');
    }
  };

  if (mfaToken) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0f0f0f]" role="main" aria-label="Two-factor authentication">
        <form onSubmit={handleMfaSubmit} className="rounded-lg bg-zinc-900 border border-zinc-700 p-6 w-full max-w-sm" aria-label="MFA verification">
          <h1 className="text-xl font-semibold text-cyan-400 mb-2">Two-factor authentication</h1>
          <p className="text-zinc-400 text-sm mb-4">Enter the 6-digit code from your authenticator app.</p>
          {error && <p className="text-red-400 text-sm mb-2" role="alert">{error}</p>}
          <label htmlFor="login-mfa-code" className="sr-only">Verification code</label>
          <input
            id="login-mfa-code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            className="w-full px-3 py-2 rounded bg-zinc-800 border border-zinc-600 text-white placeholder-zinc-500 mb-4 text-center font-mono text-lg tracking-widest"
            disabled={loading}
          />
          <button type="submit" className="w-full py-2 rounded bg-cyan-600 hover:bg-cyan-500 text-black font-medium disabled:opacity-50" disabled={loading}>
            {loading ? 'Verifying…' : 'Verify'}
          </button>
          <button
            type="button"
            onClick={() => { setMfaToken(null); setMfaCode(''); setError(''); }}
            className="w-full mt-2 py-2 text-zinc-400 hover:text-white text-sm"
          >
            Back to password
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0f0f0f]" role="main" aria-label="Sign in">
      <header className="border-b border-zinc-800 px-4 py-3 flex justify-between items-center shrink-0">
        <h1 className="text-lg font-bold tracking-tight">
          <span className="text-white">Vigil</span>
          <span className="text-cyan-400 font-semibold ml-1.5">|</span>
          <span className="text-zinc-400 font-normal text-sm ml-1.5 hidden sm:inline">Edge Video Security</span>
        </h1>
        <button
          type="button"
          onClick={handleAutoSignIn}
          disabled={autoSignInLoading}
          className="px-3 py-1.5 rounded text-sm font-medium bg-cyan-600 hover:bg-cyan-500 text-black disabled:opacity-50"
          title="Sign in as admin when server has AUTO_LOGIN=1 (dev/local)"
        >
          {autoSignInLoading ? 'Signing in…' : 'Auto sign-in'}
        </button>
      </header>
      <div className="flex-1 flex items-center justify-center p-4">
      <form
        onSubmit={handlePasswordSubmit}
        className="rounded-lg bg-zinc-900 border border-zinc-700 p-6 w-full max-w-sm shadow-xl"
        aria-label="Sign in form"
        noValidate
      >
        <h1 className="text-xl font-semibold text-cyan-400 mb-4 text-center">Sign in</h1>
        {sessionMessage && (
          <p className="text-amber-400 text-sm mb-2" role="alert">
            {sessionMessage}
          </p>
        )}
        {error && (
          <p id="login-error" className="text-red-400 text-sm mb-2" role="alert">
            {error}
          </p>
        )}
        <label htmlFor="login-username" className="sr-only">
          Username
        </label>
        <input
          id="login-username"
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full px-3 py-2 rounded bg-zinc-800 border border-zinc-600 text-white placeholder-zinc-500 mb-2"
          autoComplete="username"
          disabled={loading}
          aria-invalid={!!error}
          aria-describedby={error ? 'login-error' : undefined}
        />
        <label htmlFor="login-password" className="sr-only">
          Password
        </label>
        <input
          id="login-password"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2 rounded bg-zinc-800 border border-zinc-600 text-white placeholder-zinc-500 mb-4"
          autoComplete="current-password"
          disabled={loading}
          aria-invalid={!!error}
        />
        <button
          type="submit"
          className="w-full py-2 rounded bg-cyan-600 hover:bg-cyan-500 text-black font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={loading || !username.trim()}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      </div>
    </div>
  );
}
