import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchMe, fetchAuditLog, fetchMfaStatus, mfaSetup, mfaConfirm, changePassword, fetchDevices, downloadAuditLogExport, fetchAuditLogVerify, fetchConfig, updateConfig, fetchUsers, fetchUserSites, updateUserSites, fetchSites, fetchWhatWeCollect, updateRecordingConfig, type AnalyticsConfig } from '../api/client';

function DevicesSection() {
  const { data, isLoading, error } = useQuery({ queryKey: ['devices'], queryFn: fetchDevices });
  if (isLoading) return <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4"><p className="text-zinc-500 text-sm">Loading devices…</p></section>;
  if (error) return <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4"><p className="text-red-400 text-sm">Could not load devices.</p></section>;
  const cameras = data?.cameras ?? [];
  const microphones = data?.microphones ?? [];
  return (
    <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
      <h2 className="text-sm font-medium text-zinc-400 mb-2">Detected devices</h2>
      <p className="text-zinc-500 text-sm mb-3">
        Cameras and microphones on this device are auto-detected. {data?.camera_sources_auto ? 'Camera sources: auto.' : 'Camera sources: from env.'} Audio: {data?.audio_enabled ? 'enabled' : 'disabled'}.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <h3 className="text-xs font-medium text-cyan-400/90 mb-1">Cameras ({cameras.length})</h3>
          <ul className="text-sm text-zinc-300 space-y-1">
            {cameras.length === 0 ? <li className="text-zinc-500">None detected</li> : cameras.map((c) => (
              <li key={String(c.index)}>{c.name ?? `Camera ${c.index}`} {c.resolution ? ` · ${c.resolution}` : ''}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-xs font-medium text-cyan-400/90 mb-1">Microphones ({microphones.length})</h3>
          <ul className="text-sm text-zinc-300 space-y-1">
            {microphones.length === 0 ? <li className="text-zinc-500">None detected (install pyaudio to list)</li> : microphones.map((m) => (
              <li key={m.index}>{m.name} · {m.sample_rate} Hz</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [mfaCode, setMfaCode] = useState('');
  const [mfaSecret, setMfaSecret] = useState<{ secret: string; provisioning_uri: string } | null>(null);
  const [pwCurrent, setPwCurrent] = useState('');
  const [pwNew, setPwNew] = useState('');
  const [pwConfirm, setPwConfirm] = useState('');
  const [auditExportLoading, setAuditExportLoading] = useState(false);
  const [auditExportError, setAuditExportError] = useState<string | null>(null);
  const [auditVerifyLoading, setAuditVerifyLoading] = useState(false);
  const [auditVerifyResult, setAuditVerifyResult] = useState<{ verified: number; mismatched: number; total: number } | null>(null);
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: fetchMe });
  const changePw = useMutation({
    mutationFn: () => changePassword(pwCurrent, pwNew),
    onSuccess: (data) => {
      if (data.success) {
        setPwCurrent('');
        setPwNew('');
        setPwConfirm('');
        queryClient.invalidateQueries({ queryKey: ['me'] });
      }
    },
  });
  const { data: mfaStatus } = useQuery({ queryKey: ['mfa_status'], queryFn: fetchMfaStatus });
  const { data: auditLog, error: auditError, isLoading: auditLoading } = useQuery({
    queryKey: ['audit_log'],
    queryFn: () => fetchAuditLog(50),
    enabled: me?.role === 'admin',
  });
  const { data: myAuditLog } = useQuery({
    queryKey: ['audit_log', 'mine'],
    queryFn: () => fetchAuditLog(50, true),
    enabled: !!me?.username && me?.role !== 'admin',
  });
  const { data: whatWeCollect } = useQuery({ queryKey: ['what_we_collect'], queryFn: fetchWhatWeCollect });
  const updateRecordingConfigMutation = useMutation({
    mutationFn: updateRecordingConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recording_config'] });
      queryClient.invalidateQueries({ queryKey: ['system_status'] });
      queryClient.invalidateQueries({ queryKey: ['what_we_collect'] });
    },
  });
  const setupMfa = useMutation({
    mutationFn: mfaSetup,
    onSuccess: (data) => setMfaSecret(data),
  });
  const confirmMfa = useMutation({
    mutationFn: (code: string) => mfaConfirm(code),
    onSuccess: () => {
      setMfaSecret(null);
      setMfaCode('');
      queryClient.invalidateQueries({ queryKey: ['mfa_status'] });
    },
  });
  const { data: analyticsConfig, isLoading: configLoading } = useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
    enabled: me?.role === 'admin',
  });
  const [configLoiterSeconds, setConfigLoiterSeconds] = useState<string>('');
  const [configZonesJson, setConfigZonesJson] = useState('');
  const [configLinesJson, setConfigLinesJson] = useState('');
  const [signageReminder, setSignageReminder] = useState('');
  const [privacyPolicyUrl, setPrivacyPolicyUrl] = useState('');
  const [configSaveError, setConfigSaveError] = useState<string | null>(null);
  const configSyncedRef = useRef(false);
  const configSave = useMutation({
    mutationFn: async (updates: Partial<AnalyticsConfig>) => {
      const res = await updateConfig(updates);
      if (!res.success) throw new Error(res.error);
    },
    onSuccess: () => {
      configSyncedRef.current = false;
      queryClient.invalidateQueries({ queryKey: ['config'] });
      setConfigSaveError(null);
    },
    onError: (e: Error) => setConfigSaveError(e.message),
  });
  const handleSaveConfig = () => {
    setConfigSaveError(null);
    const updates: Partial<AnalyticsConfig> = {};
    if (configLoiterSeconds !== '') {
      const n = parseInt(configLoiterSeconds, 10);
      if (Number.isNaN(n) || n < 1) {
        setConfigSaveError('Loiter seconds must be a positive integer');
        return;
      }
      updates.loiter_seconds = n;
    }
    if (configZonesJson.trim()) {
      try {
        updates.loiter_zones = JSON.parse(configZonesJson);
      } catch {
        setConfigSaveError('Invalid JSON for loiter zones');
        return;
      }
    }
    if (configLinesJson.trim()) {
      try {
        updates.crossing_lines = JSON.parse(configLinesJson);
      } catch {
        setConfigSaveError('Invalid JSON for crossing lines');
        return;
      }
    }
    if (Object.keys(updates).length === 0) return;
    configSave.mutate(updates);
  };
  useEffect(() => {
    if (!analyticsConfig || configSyncedRef.current) return;
    configSyncedRef.current = true;
    setConfigLoiterSeconds(String(analyticsConfig.loiter_seconds));
    setConfigZonesJson(JSON.stringify(analyticsConfig.loiter_zones, null, 2));
    setConfigLinesJson(JSON.stringify(analyticsConfig.crossing_lines, null, 2));
    setSignageReminder(analyticsConfig.recording_signage_reminder ?? '');
    setPrivacyPolicyUrl(analyticsConfig.privacy_policy_url ?? '');
  }, [analyticsConfig]);

  return (
    <div className="p-4 max-w-3xl">
      <h1 className="text-xl font-semibold text-cyan-400 mb-4">Settings</h1>
      <div className="space-y-6">
        <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
          <h2 className="text-sm font-medium text-zinc-400 mb-2">Current user</h2>
          <p className="text-zinc-200">
            {me?.username ?? '—'} <span className="text-zinc-500">({me?.role ?? '—'})</span>
          </p>
          {me?.password_expires_in_days != null && (
            <p className="text-amber-400/90 text-sm mt-2">
              Password expires in {me.password_expires_in_days} day{me.password_expires_in_days !== 1 ? 's' : ''}. Change it in the section below.
            </p>
          )}
          <p className="text-zinc-500 text-sm mt-2">
            Camera list, stream URLs, and retention are configured via backend env (see .env.example).
          </p>
        </section>
        <DevicesSection />
        <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
          <h2 className="text-sm font-medium text-cyan-400 mb-2">Privacy &amp; transparency</h2>
          <p className="text-zinc-500 text-xs mb-3">What this system records and analyzes. Use minimal preset to limit collection (civilian ethics).</p>
          {whatWeCollect && (
            <div className="mb-3 text-sm text-zinc-300">
              <strong className="text-zinc-400">What we collect:</strong>{' '}
              Video, motion, loitering, line-crossing
              {whatWeCollect.lpr && ', LPR'}
              {whatWeCollect.emotion_or_face && ', emotion/face'}
              {whatWeCollect.audio && ', audio'}
              {whatWeCollect.wifi_presence && ', Wi‑Fi presence'}
              {whatWeCollect.thermal && ', thermal'}
              . Retention: {whatWeCollect.retention_days > 0 ? `${whatWeCollect.retention_days} days` : 'unlimited'}.
            </div>
          )}
          {me?.role === 'admin' && analyticsConfig && (
            <>
              <div className="mb-2">
                <label className="block text-xs text-zinc-500 mb-1">Recording signage reminder (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Ensure signage is displayed where required"
                  value={signageReminder}
                  onChange={(e) => setSignageReminder(e.target.value)}
                  className="w-full px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
                />
              </div>
              <div className="mb-2">
                <label className="block text-xs text-zinc-500 mb-1">Privacy policy URL (optional)</label>
                <input
                  type="url"
                  placeholder="https://..."
                  value={privacyPolicyUrl}
                  onChange={(e) => setPrivacyPolicyUrl(e.target.value)}
                  className="w-full px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
                />
              </div>
              <div className="flex flex-wrap gap-2 mb-2">
                <button
                  type="button"
                  onClick={() => configSave.mutate({ recording_signage_reminder: signageReminder, privacy_policy_url: privacyPolicyUrl })}
                  disabled={configSave.isPending}
                  className="px-2 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-xs"
                >
                  Save reminder &amp; URL
                </button>
              </div>
              <div className="mb-2">
                <label className="block text-xs text-zinc-500 mb-1">Privacy preset</label>
                <select
                  value={analyticsConfig.privacy_preset ?? 'full'}
                  onChange={(e) => {
                    const v = e.target.value as 'minimal' | 'full';
                    configSave.mutate({ privacy_preset: v });
                    if (v === 'minimal') {
                      updateRecordingConfigMutation.mutate({
                        capture_audio: false,
                        capture_thermal: false,
                        capture_wifi: false,
                        ai_detail: 'minimal',
                      });
                    } else {
                      updateRecordingConfigMutation.mutate({ ai_detail: 'full' });
                    }
                  }}
                  className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
                >
                  <option value="minimal">Minimal (motion, loiter, line-cross only)</option>
                  <option value="full">Full (LPR, emotion, audio, Wi‑Fi when enabled)</option>
                </select>
              </div>
            </>
          )}
        </section>
        {!!me?.username && me?.role !== 'admin' && (
          <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
            <h2 className="text-sm font-medium text-cyan-400 mb-2">My access history</h2>
            <p className="text-zinc-500 text-xs mb-2">Your recent logins and exports (transparency).</p>
            {myAuditLog && myAuditLog.length > 0 ? (
              <ul className="text-sm text-zinc-300 space-y-1 max-h-48 overflow-y-auto">
                {myAuditLog.slice(0, 20).map((entry) => (
                  <li key={entry.id}>
                    {entry.timestamp?.slice(0, 19)} — {entry.action} {entry.resource ? `(${entry.resource})` : ''}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-zinc-500 text-sm">No entries yet.</p>
            )}
          </section>
        )}
        <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
          <h2 className="text-sm font-medium text-zinc-400 mb-2">Change password</h2>
          <div className="space-y-2">
            <input
              type="password"
              placeholder="Current password"
              value={pwCurrent}
              onChange={(e) => setPwCurrent(e.target.value)}
              className="w-full max-w-xs px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-white"
            />
            <input
              type="password"
              placeholder="New password"
              value={pwNew}
              onChange={(e) => setPwNew(e.target.value)}
              className="w-full max-w-xs px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-white block"
            />
            <input
              type="password"
              placeholder="Confirm new password"
              value={pwConfirm}
              onChange={(e) => setPwConfirm(e.target.value)}
              className="w-full max-w-xs px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-white block"
            />
            <button
              type="button"
              onClick={() => pwNew && pwNew === pwConfirm && pwCurrent && changePw.mutate()}
              disabled={!pwCurrent || !pwNew || pwNew !== pwConfirm || changePw.isPending}
              className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-black text-sm font-medium"
            >
              {changePw.isPending ? 'Changing…' : 'Change password'}
            </button>
            {changePw.data && !changePw.data.success && (
              <p className="text-red-400 text-sm">{changePw.data.error}</p>
            )}
          </div>
        </section>
        {mfaStatus?.available && (me?.role === 'operator' || me?.role === 'admin') && (
          <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-2">Two-factor authentication (MFA)</h2>
            <p className="text-zinc-400 text-sm mb-2">
              {mfaStatus.enabled ? 'MFA is enabled. You will be asked for a code when signing in.' : 'MFA is not enabled.'}
            </p>
            {!mfaStatus.enabled && !mfaSecret && (
              <button
                type="button"
                onClick={() => setupMfa.mutate()}
                disabled={setupMfa.isPending}
                className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium"
              >
                {setupMfa.isPending ? 'Setting up…' : 'Enable MFA'}
              </button>
            )}
            {mfaSecret && (
              <div className="mt-2 space-y-2">
                <p className="text-zinc-400 text-sm">
                  Add this secret to your authenticator app (Google Authenticator, Authy, etc.), or scan the provisioning URI in an app that supports it.
                </p>
                <p className="font-mono text-xs text-zinc-500 break-all">{mfaSecret.secret}</p>
                <p className="text-zinc-400 text-sm">Then enter the 6-digit code below to confirm and enable MFA.</p>
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="000000"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="w-32 px-2 py-1 rounded bg-zinc-800 border border-zinc-600 text-white font-mono"
                />
                <button
                  type="button"
                  onClick={() => mfaCode.length === 6 && confirmMfa.mutate(mfaCode)}
                  disabled={mfaCode.length !== 6 || confirmMfa.isPending}
                  className="ml-2 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm"
                >
                  {confirmMfa.isPending ? 'Verifying…' : 'Confirm'}
                </button>
                <button
                  type="button"
                  onClick={() => { setMfaSecret(null); setMfaCode(''); }}
                  className="ml-2 text-zinc-500 hover:text-white text-sm"
                >
                  Cancel
                </button>
              </div>
            )}
          </section>
        )}
        {me?.role === 'admin' && (
          <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
            <h2 className="text-sm font-medium text-cyan-400 mb-2">Analytics config (zones &amp; lines)</h2>
            <p className="text-zinc-500 text-xs mb-3">Loitering zones and crossing lines for AI analytics. Changes are audited.</p>
            {configLoading && <p className="text-zinc-500 text-sm">Loading config…</p>}
            {analyticsConfig && (
              <>
                <div className="mb-3">
                  <label className="block text-xs text-zinc-500 mb-1">Loiter seconds</label>
                  <input
                    type="number"
                    min={1}
                    value={configLoiterSeconds}
                    onChange={(e) => setConfigLoiterSeconds(e.target.value)}
                    className="w-24 px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
                  />
                </div>
                <div className="mb-3">
                  <label className="block text-xs text-zinc-500 mb-1">Loiter zones (JSON: array of polygons, each polygon array of [x,y] 0–1)</label>
                  <textarea
                    value={configZonesJson}
                    onChange={(e) => setConfigZonesJson(e.target.value)}
                    rows={4}
                    className="w-full px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs font-mono"
                    spellCheck={false}
                  />
                </div>
                <div className="mb-3">
                  <label className="block text-xs text-zinc-500 mb-1">Crossing lines (JSON: array of [x1,y1,x2,y2] 0–1)</label>
                  <textarea
                    value={configLinesJson}
                    onChange={(e) => setConfigLinesJson(e.target.value)}
                    rows={2}
                    className="w-full px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-xs font-mono"
                    spellCheck={false}
                  />
                </div>
                {configSaveError && <p className="text-red-400 text-sm mb-2">{configSaveError}</p>}
                <button
                  type="button"
                  onClick={handleSaveConfig}
                  disabled={configSave.isPending}
                  className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium disabled:opacity-50"
                >
                  {configSave.isPending ? 'Saving…' : 'Save config'}
                </button>
              </>
            )}
          </section>
        )}
        {me?.role === 'admin' && (
          <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-2">Audit log</h2>
            <p className="text-zinc-500 text-xs mb-2">Export includes SHA-256 for chain of custody. Verify integrity (NIST AU-9). Admin only.</p>
            <div className="flex flex-wrap gap-2 mb-2">
            <button
              type="button"
              onClick={async () => {
                setAuditExportError(null);
                setAuditExportLoading(true);
                try {
                  const blob = await downloadAuditLogExport();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `audit_log_${new Date().toISOString().slice(0, 10)}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                } catch (e) {
                  setAuditExportError((e as Error).message);
                } finally {
                  setAuditExportLoading(false);
                }
              }}
              disabled={auditExportLoading}
              className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium disabled:opacity-50"
            >
              {auditExportLoading ? 'Exporting…' : 'Export audit log (CSV)'}
            </button>
            <button
              type="button"
              title="Verify audit log integrity (detect tampering)"
              onClick={async () => {
                setAuditExportError(null);
                setAuditVerifyResult(null);
                setAuditVerifyLoading(true);
                try {
                  const res = await fetchAuditLogVerify();
                  setAuditVerifyResult(res);
                } catch (e) {
                  setAuditExportError((e as Error).message);
                } finally {
                  setAuditVerifyLoading(false);
                }
              }}
              disabled={auditVerifyLoading}
              className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm font-medium disabled:opacity-50"
            >
              {auditVerifyLoading ? 'Verifying…' : 'Verify audit log'}
            </button>
            </div>
            {auditVerifyResult !== null && (
              <div className="mb-2 p-2 rounded bg-zinc-800/80 text-sm">
                <span className="text-emerald-400">{auditVerifyResult.verified} verified</span>
                {auditVerifyResult.mismatched > 0 && <span className="text-red-400 ml-2">{auditVerifyResult.mismatched} mismatched</span>}
                <span className="text-zinc-500 ml-2">({auditVerifyResult.total} total rows)</span>
              </div>
            )}
            {auditExportError && <p className="text-red-400 text-sm mb-2">{auditExportError}</p>}
            {auditLoading && <p className="text-zinc-500">Loading…</p>}
            {auditError && <p className="text-red-400">{(auditError as Error).message}</p>}
            {auditLog && auditLog.length > 0 && (
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-zinc-400 border-b border-zinc-700">
                      <th className="py-1 pr-2">Time</th>
                      <th className="py-1 pr-2">User</th>
                      <th className="py-1 pr-2">Action</th>
                      <th className="py-1 pr-2">Resource</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLog.map((e) => (
                      <tr key={e.id} className="border-b border-zinc-800">
                        <td className="py-1 pr-2 font-mono text-zinc-500">{e.timestamp}</td>
                        <td className="py-1 pr-2">{e.user_id}</td>
                        <td className="py-1 pr-2">{e.action}</td>
                        <td className="py-1 pr-2 text-zinc-500">{e.resource ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {auditLog && auditLog.length === 0 && <p className="text-zinc-500">No audit entries yet.</p>}
          </section>
        )}
        {me?.role === 'admin' && (
          <UsersAndSitesSection />
        )}
      </div>
    </div>
  );
}

function UsersAndSitesSection() {
  const queryClient = useQueryClient();
  const { data: usersData, isLoading: usersLoading, error: usersError } = useQuery({ queryKey: ['users'], queryFn: fetchUsers });
  const { data: sites } = useQuery({ queryKey: ['sites'], queryFn: fetchSites });
  const [expandedUserId, setExpandedUserId] = useState<number | null>(null);
  const users = usersData?.users ?? [];
  const sitesList = sites ?? [];

  return (
    <section className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
      <h2 className="text-sm font-medium text-cyan-400 mb-2">Users &amp; site access</h2>
      <p className="text-zinc-500 text-xs mb-3">Assign which sites each user can access. Empty = no restrictions (all sites).</p>
      {usersLoading && <p className="text-zinc-500 text-sm">Loading users…</p>}
      {usersError && <p className="text-red-400 text-sm">{(usersError as Error).message}</p>}
      {users.length > 0 && (
        <ul className="space-y-2">
          {users.map((u) => (
            <li key={u.id} className="border border-zinc-800 rounded p-2">
              <button
                type="button"
                onClick={() => setExpandedUserId(expandedUserId === u.id ? null : u.id)}
                className="w-full text-left flex items-center justify-between text-zinc-200"
              >
                <span>{u.username} <span className="text-zinc-500">({u.role})</span></span>
                <span className="text-zinc-500">{expandedUserId === u.id ? '▼' : '▶'}</span>
              </button>
              {expandedUserId === u.id && (
                <UserSitesEditor userId={u.id} sitesList={sitesList} onSaved={() => queryClient.invalidateQueries({ queryKey: ['users'] })} />
              )}
            </li>
          ))}
        </ul>
      )}
      {!usersLoading && !usersError && users.length === 0 && <p className="text-zinc-500 text-sm">No users (backend-managed).</p>}
    </section>
  );
}

function UserSitesEditor({ userId, sitesList, onSaved }: { userId: number; sitesList: { id: string; name: string }[]; onSaved: () => void }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['user_sites', userId], queryFn: () => fetchUserSites(userId) });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const synced = useRef(false);

  useEffect(() => {
    synced.current = false;
  }, [userId]);
  useEffect(() => {
    if (!data || synced.current) return;
    synced.current = true;
    queueMicrotask(() => setSelected(new Set(data.site_ids ?? [])));
  }, [data]);

  const save = useMutation({
    mutationFn: (siteIds: string[]) => updateUserSites(userId, siteIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user_sites', userId] });
      onSaved();
    },
  });

  const toggle = (siteId: string) => {
    const next = new Set(selected);
    if (next.has(siteId)) next.delete(siteId);
    else next.add(siteId);
    setSelected(next);
  };

  if (isLoading || !data) return <p className="text-zinc-500 text-sm mt-2">Loading sites…</p>;

  return (
    <div className="mt-3 pl-2 border-l-2 border-zinc-700">
      <p className="text-xs text-zinc-500 mb-2">Allowed sites (empty = all):</p>
      <div className="flex flex-wrap gap-2 mb-2">
        {sitesList.map((s) => (
          <label key={s.id} className="flex items-center gap-1.5 text-sm text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={selected.has(s.id)}
              onChange={() => toggle(s.id)}
              className="rounded border-zinc-600 bg-zinc-800 text-cyan-500"
            />
            {s.name || s.id}
          </label>
        ))}
      </div>
      {sitesList.length === 0 && <p className="text-zinc-500 text-xs">No sites configured. Add sites via backend.</p>}
      <button
        type="button"
        onClick={() => save.mutate(Array.from(selected))}
        disabled={save.isPending}
        className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium disabled:opacity-50"
      >
        {save.isPending ? 'Saving…' : 'Save site access'}
      </button>
    </div>
  );
}
