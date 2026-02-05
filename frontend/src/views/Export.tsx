import { useState, useMemo, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { downloadExportData, fetchRecordings, downloadRecordingExport, fetchAiDataVerify, fetchRecordingManifest, downloadAuditLogExport, fetchAuditLogVerify, fetchLegalHolds, addLegalHold, removeLegalHold, parseLog, parseLogFile, getSurveillanceAnalysisReportUrl, fetchIncidentBundle, fetchStorage, setStoragePath, fetchMe, type RecordingManifest, type ParseLogResponse, type IncidentBundleManifest } from '../api/client';
import Map from './Map';
import Analytics from './Analytics';

export default function Export() {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recordingLoading, setRecordingLoading] = useState<string | null>(null);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{ verified: number; mismatched: number; total: number } | null>(null);
  const [manifestFor, setManifestFor] = useState<string | null>(null);
  const [manifest, setManifest] = useState<RecordingManifest | null>(null);
  const [manifestLoading, setManifestLoading] = useState(false);
  const [auditExportLoading, setAuditExportLoading] = useState(false);
  const [auditVerifyLoading, setAuditVerifyLoading] = useState(false);
  const [auditVerifyResult, setAuditVerifyResult] = useState<{ verified: number; mismatched: number; total: number } | null>(null);
  const [recordingsFilter, setRecordingsFilter] = useState('');
  const [recordingsSort, setRecordingsSort] = useState<'date-desc' | 'date-asc' | 'name-asc' | 'name-desc' | 'size-desc' | 'size-asc'>('date-desc');
  const [logImportText, setLogImportText] = useState('');
  const [logImportFile, setLogImportFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<ParseLogResponse | null>(null);
  const [parseLoading, setParseLoading] = useState(false);
  const [incidentFrom, setIncidentFrom] = useState('');
  const [incidentTo, setIncidentTo] = useState('');
  const [incidentManifest, setIncidentManifest] = useState<IncidentBundleManifest | null>(null);
  const [incidentLoading, setIncidentLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const { data: recordingsData } = useQuery({
    queryKey: ['recordings'],
    queryFn: () => fetchRecordings(),
    retry: () => false,
  });
  const allRecordings = useMemo(() => recordingsData?.recordings ?? [], [recordingsData?.recordings]);
  const recordingsForbidden = recordingsData?.forbidden === true;
  const recordings = useMemo(() => {
    let list = allRecordings.slice();
    const q = recordingsFilter.trim().toLowerCase();
    if (q) list = list.filter((r) => (r.name ?? '').toLowerCase().includes(q));
    const sort = recordingsSort;
    if (sort === 'date-asc') list.sort((a, b) => (a.created_utc ?? '').localeCompare(b.created_utc ?? ''));
    else if (sort === 'date-desc') list.sort((a, b) => (b.created_utc ?? '').localeCompare(a.created_utc ?? ''));
    else if (sort === 'name-asc') list.sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''));
    else if (sort === 'name-desc') list.sort((a, b) => (b.name ?? '').localeCompare(a.name ?? ''));
    else if (sort === 'size-desc') list.sort((a, b) => (b.size_bytes ?? 0) - (a.size_bytes ?? 0));
    else if (sort === 'size-asc') list.sort((a, b) => (a.size_bytes ?? 0) - (b.size_bytes ?? 0));
    return list;
  }, [allRecordings, recordingsFilter, recordingsSort]);

  const handleExport = async () => {
    setError(null);
    setLoading(true);
    try {
      const blob = await downloadExportData();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ai_data_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleRecordingExport = async (name: string, asMp4 = false) => {
    setError(null);
    setRecordingLoading(name);
    try {
      const blob = await downloadRecordingExport(name, asMp4 ? 'mp4' : undefined);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = asMp4 ? name.replace(/\.avi$/i, '.mp4') : name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRecordingLoading(null);
    }
  };

  const formatSize = (n: number) =>
    n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : n >= 1e3 ? `${(n / 1e3).toFixed(1)} KB` : `${n} B`;

  const handleVerify = async () => {
    setError(null);
    setVerifyResult(null);
    setVerifyLoading(true);
    try {
      const res = await fetchAiDataVerify();
      setVerifyResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setVerifyLoading(false);
    }
  };

  const handleAuditExport = async () => {
    setError(null);
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
      setError((e as Error).message);
    } finally {
      setAuditExportLoading(false);
    }
  };

  const handleAuditVerify = async () => {
    setError(null);
    setAuditVerifyResult(null);
    setAuditVerifyLoading(true);
    try {
      const res = await fetchAuditLogVerify();
      setAuditVerifyResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAuditVerifyLoading(false);
    }
  };

  const handleParseLog = async () => {
    setError(null);
    setParseResult(null);
    setParseLoading(true);
    try {
      const res = logImportFile
        ? await parseLogFile(logImportFile)
        : await parseLog(logImportText.trim() || '');
      setParseResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setParseLoading(false);
    }
  };

  const downloadParsedCsv = () => {
    if (!parseResult?.rows?.length || !parseResult?.columns?.length) return;
    const cols = parseResult.columns;
    const escape = (v: unknown) => {
      const s = v == null ? '' : String(v);
      return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const header = cols.join(',');
    const body = parseResult.rows.map((r) => cols.map((c) => escape(r[c])).join(',')).join('\n');
    const blob = new Blob([header + '\n' + body], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cleaned_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleViewManifest = async (name: string) => {
    setError(null);
    setManifestFor(name);
    setManifest(null);
    setManifestLoading(true);
    try {
      const data = await fetchRecordingManifest(name);
      setManifest(data);
    } catch (e) {
      setError((e as Error).message);
      setManifestFor(null);
    } finally {
      setManifestLoading(false);
    }
  };

  const handleIncidentBundle = async () => {
    setError(null);
    setIncidentManifest(null);
    if (!incidentFrom || !incidentTo) {
      setError('Enter date range (from and to)');
      return;
    }
    setIncidentLoading(true);
    try {
      const { manifest } = await fetchIncidentBundle(incidentFrom, incidentTo);
      setIncidentManifest(manifest);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIncidentLoading(false);
    }
  };

  const downloadIncidentAiData = async () => {
    if (!incidentManifest) return;
    setError(null);
    setLoading(true);
    try {
      const blob = await downloadExportData(incidentManifest.date_from, incidentManifest.date_to);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ai_data_${incidentManifest.date_from}_to_${incidentManifest.date_to}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-3 sm:p-4 max-w-5xl">
      <h1 className="text-lg sm:text-xl font-semibold text-cyan-400 mb-2">Export &amp; data</h1>
      <p className="text-zinc-400 text-sm mb-4">Download AI data, verify integrity, recordings, and parse surveillance logs. Map and analytics below.</p>
      {error && <p className="text-red-400 mb-2 text-sm" role="alert">{error}</p>}
      <section className="mb-5 rounded-lg bg-zinc-900/50 border border-zinc-700 p-4" aria-labelledby="incident-heading">
        <h2 id="incident-heading" className="text-zinc-500 text-xs uppercase tracking-wide mb-2 font-medium">Incident export bundle</h2>
        <p className="text-zinc-400 text-sm mb-2">One-click manifest for a date range (recordings + AI data export). Chain of custody for insurance or LE.</p>
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <input
            type="date"
            value={incidentFrom}
            onChange={(e) => setIncidentFrom(e.target.value)}
            className="min-h-[44px] px-2 py-2 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
          />
          <span className="text-zinc-500">to</span>
          <input
            type="date"
            value={incidentTo}
            onChange={(e) => setIncidentTo(e.target.value)}
            className="min-h-[44px] px-2 py-2 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
          />
          <button
            type="button"
            onClick={handleIncidentBundle}
            disabled={incidentLoading}
            className="touch-target px-3 py-2 rounded text-sm font-medium bg-cyan-600 hover:bg-cyan-500 text-black disabled:opacity-50"
          >
            {incidentLoading ? 'Generating…' : 'Generate bundle'}
          </button>
        </div>
        {incidentManifest && (
          <div className="text-sm text-zinc-300 space-y-2">
            <p>Export UTC: {incidentManifest.export_utc} · Operator: {incidentManifest.operator} · Retention: {incidentManifest.retention_days} days</p>
            <button
              type="button"
              onClick={downloadIncidentAiData}
              disabled={loading}
              className="px-2 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-cyan-300"
            >
              {loading ? 'Downloading…' : 'Download AI data CSV for range'}
            </button>
            {incidentManifest.recordings?.length > 0 && (
              <p className="mt-2">Recordings in range: {incidentManifest.recordings.map((r) => r.name).join(', ')} — export from list below.</p>
            )}
          </div>
        )}
      </section>
      <section className="mb-5" aria-labelledby="export-data-heading">
        <h2 id="export-data-heading" className="text-zinc-500 text-xs uppercase tracking-wide mb-2 font-medium">Data export</h2>
        <div className="flex flex-wrap items-center gap-2">
        <button
          title="Download AI data as CSV (SHA-256, chain of custody)"
          onClick={handleExport}
          disabled={loading}
          className="touch-target px-3 py-2 rounded text-sm font-medium bg-cyan-600 hover:bg-cyan-500 text-black disabled:opacity-50"
        >
          {loading ? 'Exporting…' : 'AI data (CSV)'}
        </button>
        <button
          type="button"
          title="Verify AI detection log integrity"
          onClick={handleVerify}
          disabled={verifyLoading}
          className="touch-target px-3 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50"
        >
          {verifyLoading ? 'Verifying…' : 'Verify'}
        </button>
        <button
          type="button"
          title="Download audit log as CSV (admin)"
          onClick={handleAuditExport}
          disabled={auditExportLoading}
          className="touch-target px-3 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50"
        >
          {auditExportLoading ? 'Exporting…' : 'Audit log (CSV)'}
        </button>
        <button
          type="button"
          title="Verify audit log integrity (admin)"
          onClick={handleAuditVerify}
          disabled={auditVerifyLoading}
          className="touch-target px-3 py-2 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200 disabled:opacity-50"
        >
          {auditVerifyLoading ? 'Verifying…' : 'Verify audit'}
        </button>
        </div>
        {auditVerifyResult !== null && (
          <div className="mt-2 text-sm text-zinc-400">
            Audit: <span className="text-emerald-400">{auditVerifyResult.verified} verified</span>
            {auditVerifyResult.mismatched > 0 && <span className="text-red-400 ml-2">{auditVerifyResult.mismatched} mismatched</span>}
            <span className="text-zinc-500 ml-2">({auditVerifyResult.total} total)</span>
          </div>
        )}
        {verifyResult !== null && (
          <div className="mt-3 p-3 rounded-lg bg-zinc-900/80 border border-zinc-700 text-sm">
            <span className="text-zinc-400">Integrity check: </span>
            <span className="text-emerald-400">{verifyResult.verified} verified</span>
            {verifyResult.mismatched > 0 && <span className="text-red-400 ml-2">{verifyResult.mismatched} mismatched</span>}
            <span className="text-zinc-500 ml-2">({verifyResult.total} rows with hash)</span>
          </div>
        )}
      </section>

      <section className="mb-5" aria-labelledby="import-log-heading">
        <h2 id="import-log-heading" className="text-zinc-500 text-xs uppercase tracking-wide mb-2 font-medium">Import / parse surveillance log</h2>
        <p className="text-zinc-500 text-sm mb-3">Paste raw log text (YOLOv8/Frigate-style) or upload a file. Parsed data can be downloaded as cleaned CSV. Use the analysis report to interpret value, tracks, and anomalies.</p>
        <div className="flex flex-wrap items-end gap-3 mb-2">
          <div className="flex-1 min-w-[240px]">
            <label htmlFor="log-import-textarea" className="sr-only">Log text to parse</label>
            <textarea
              id="log-import-textarea"
              placeholder="Paste log lines (header + data)…"
              value={logImportText}
              onChange={(e) => { setLogImportText(e.target.value); setLogImportFile(null); }}
              rows={4}
              className="w-full px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm font-mono placeholder:text-zinc-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30"
              aria-label="Log text to parse"
              aria-describedby="log-import-hint"
            />
            <span id="log-import-hint" className="text-zinc-600 text-xs mt-1 block">Include header line and tab/comma-separated data.</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.log,.csv"
              className="hidden"
              aria-hidden="true"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) { setLogImportFile(f); setLogImportText(''); }
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-zinc-900"
              aria-label="Choose log file to upload"
            >
              Choose file
            </button>
            <button
              type="button"
              onClick={handleParseLog}
              disabled={parseLoading || (!logImportText.trim() && !logImportFile)}
              className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-zinc-900"
              aria-busy={parseLoading}
              aria-label={parseLoading ? 'Parsing log…' : 'Parse log'}
            >
              {parseLoading ? 'Parsing…' : 'Parse log'}
            </button>
            <a
              href={getSurveillanceAnalysisReportUrl()}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm inline-block focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-zinc-900"
              aria-label="View surveillance analysis report (opens in new tab; run parser script to generate)"
            >
              View analysis report
            </a>
          </div>
        </div>
        {logImportFile && <p className="text-zinc-500 text-xs mb-1">Selected file: {logImportFile.name}</p>}
        {parseResult !== null && (
          <div className="mt-3 p-3 rounded-lg bg-zinc-900/80 border border-zinc-700 text-sm" role="status">
            {(parseResult.summary?.rows ?? parseResult.rows.length) === 0 ? (
              <p className="text-amber-400/90">No rows parsed. Check log format (header + tab/comma-separated lines with timestamp and optional hash).</p>
            ) : (
              <>
                <span className="text-zinc-400">Parsed: </span>
                <span className="text-emerald-400">{parseResult.summary?.rows ?? parseResult.rows.length} rows</span>
                <span className="text-zinc-500 ml-2">({parseResult.columns?.length ?? 0} columns)</span>
                {typeof parseResult.summary?.hours_covered === 'number' && (
                  <span className="text-zinc-500 ml-2"> · {parseResult.summary.hours_covered.toFixed(1)} h covered</span>
                )}
                <button
                  type="button"
                  onClick={downloadParsedCsv}
                  className="ml-3 px-2 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-xs font-medium focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-zinc-900"
                >
                  Download cleaned CSV
                </button>
              </>
            )}
          </div>
        )}
      </section>
      <LegalHoldSection error={error} setError={setError} />

      <StorageLocationSection error={error} setError={setError} />
      <section className="mt-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-1">Recordings</h2>
        <p className="text-zinc-500 text-xs mb-2">AVI/MP4 with NISTIR 8161 metadata and SHA-256. Operator/admin.</p>
        {allRecordings.length > 0 && (
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <button type="button" onClick={() => queryClient.invalidateQueries({ queryKey: ['recordings'] })} className="px-2 py-1.5 rounded text-sm bg-zinc-700 hover:bg-zinc-600 text-zinc-200" title="Reload recordings list">Refresh</button>
            <label className="text-sm font-medium text-zinc-400">Filter:</label>
            <input
              type="search"
              placeholder="Search by filename…"
              value={recordingsFilter}
              onChange={(e) => setRecordingsFilter(e.target.value)}
              className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm min-w-[12rem] placeholder:text-zinc-500"
              aria-label="Filter recordings by filename"
            />
            <label className="text-sm font-medium text-zinc-400">Sort by:</label>
            <select
              value={recordingsSort}
              onChange={(e) => setRecordingsSort(e.target.value as typeof recordingsSort)}
              className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
              aria-label="Sort recordings"
            >
              <option value="date-desc">Date (newest first)</option>
              <option value="date-asc">Date (oldest first)</option>
              <option value="name-asc">Name (A–Z)</option>
              <option value="name-desc">Name (Z–A)</option>
              <option value="size-desc">Size (largest first)</option>
              <option value="size-asc">Size (smallest first)</option>
            </select>
            <span className="text-zinc-500 text-xs">
              {recordings.length}{allRecordings.length !== recordings.length ? ` of ${allRecordings.length}` : ''} recording(s)
            </span>
          </div>
        )}
        {recordings.length === 0 && (
          <p className="text-zinc-500 text-sm">
            {recordingsForbidden ? 'Sign in to view recordings.' : recordingsFilter.trim() ? 'No recordings match the filter.' : 'No recordings yet. Start recording from Live view.'}
          </p>
        )}
        <ul className="space-y-2 max-h-[320px] overflow-y-auto">
          {recordings.map((r) => (
            <li key={r.name} className="flex items-center gap-3 flex-wrap">
              <span className="font-mono text-zinc-300">{r.name}</span>
              <span className="text-zinc-500 text-sm">{r.created_utc}</span>
              <span className="text-zinc-500 text-sm">{formatSize(r.size_bytes)}</span>
              <button
                type="button"
                title="Download AVI with NISTIR 8161 metadata and SHA-256 (operator/admin)"
                onClick={() => handleRecordingExport(r.name, false)}
                disabled={recordingLoading !== null}
                className="min-h-[44px] px-3 py-2 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm disabled:opacity-50"
              >
                {recordingLoading === r.name ? 'Downloading…' : 'AVI'}
              </button>
              <button
                type="button"
                title="Download as MP4 when ffmpeg is available (operator/admin)"
                onClick={() => handleRecordingExport(r.name, true)}
                disabled={recordingLoading !== null}
                className="min-h-[44px] px-3 py-2 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm disabled:opacity-50"
              >
                MP4
              </button>
              <button
                type="button"
                title="View NISTIR 8161-style manifest (metadata + SHA-256)"
                onClick={() => handleViewManifest(r.name)}
                disabled={manifestLoading}
                className="min-h-[44px] px-3 py-2 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm disabled:opacity-50"
              >
                {manifestLoading && manifestFor === r.name ? 'Loading…' : 'View manifest'}
              </button>
            </li>
          ))}
        </ul>
        {manifestFor && manifest && (
          <div className="mt-4 p-4 rounded-lg bg-zinc-900 border border-zinc-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-zinc-400">Manifest: {manifestFor}</span>
              <button
                type="button"
                onClick={() => { setManifestFor(null); setManifest(null); }}
                className="text-zinc-500 hover:text-zinc-300 text-sm"
              >
                Close
              </button>
            </div>
            <pre className="text-xs text-zinc-300 overflow-auto max-h-48">{JSON.stringify(manifest, null, 2)}</pre>
          </div>
        )}
      </section>
      <section className="mt-8 pt-6 border-t border-zinc-800">
        <Map embedded />
      </section>
      <section className="mt-8 pt-6 border-t border-zinc-800">
        <Analytics embedded />
      </section>
    </div>
  );
}

function StorageLocationSection({ error, setError }: { error: string | null; setError: (s: string | null) => void }) {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: fetchMe });
  const { data: storage, isLoading: storageLoading, refetch: refetchStorage } = useQuery({
    queryKey: ['storage'],
    queryFn: fetchStorage,
  });
  const setPath = useMutation({
    mutationFn: (path: string | null) => setStoragePath(path),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['storage'] });
    },
    onError: (e: Error) => setError(e.message),
  });
  const isAdmin = me?.role === 'admin';
  const currentPath = storage?.recordings_path ?? storage?.path ?? '';
  const usedBytes = storage?.used_bytes ?? storage?.storage_used_bytes;
  const formatBytes = (n: number) =>
    n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : n >= 1e3 ? `${(n / 1e3).toFixed(1)} KB` : `${n} B`;
  const drives = storage?.available_drives ?? [];
  const [selectedPath, setSelectedPath] = useState<string>('');
  const [storageNotif, setStorageNotif] = useState<string | null>(null);
  const storageInitialized = useRef(false);
  useEffect(() => {
    if (storage && !storageInitialized.current) {
      storageInitialized.current = true;
      queueMicrotask(() => setSelectedPath(currentPath));
    }
  }, [storage, currentPath]);
  const applyPath = () => {
    const path = (selectedPath || '').trim();
    setPath.mutate(path || null, {
      onSuccess: (data) => {
        setStorageNotif(data?.message ?? 'Storage location updated. New recordings will save here.');
        refetchStorage();
        setTimeout(() => setStorageNotif(null), 5000);
      },
    });
  };
  return (
    <section className="mt-6 rounded-lg bg-zinc-900/50 border border-zinc-700 p-4" aria-labelledby="storage-heading">
      <h2 id="storage-heading" className="text-sm font-medium text-cyan-400 mb-2">Storage location</h2>
      <p className="text-zinc-500 text-xs mb-3">Choose where recordings and export files are saved. Use local disk or an external drive; changes apply to new recordings.</p>
      {error && <p className="text-red-400 text-sm mb-2" role="alert">{error}</p>}
      {storageNotif && <p className="text-emerald-400 text-sm mb-2" role="status">{storageNotif}</p>}
      {storageLoading ? (
        <p className="text-zinc-500 text-sm">Loading…</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-2 text-sm">
            <span className="text-zinc-500">Current path:</span>
            <code className="text-cyan-300 break-all font-mono text-xs">{currentPath || 'Default (app directory)'}</code>
            {storage?.can_write === false && (
              <span className="px-1.5 py-0.5 rounded bg-amber-900/60 text-amber-200 text-xs">No write access</span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3 mb-3 text-sm">
            <span className="text-zinc-500">Used: {usedBytes != null ? formatBytes(usedBytes) : '—'}</span>
            <span className="text-zinc-500">Recordings: {storage?.recording_count ?? '—'}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="storage-drive-select" className="text-sm font-medium text-zinc-400">Save to:</label>
            <select
              id="storage-drive-select"
              value={selectedPath || currentPath || ''}
              onChange={(e) => setSelectedPath(e.target.value)}
              className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm min-w-[12rem]"
              aria-label="Choose storage location"
            >
              <option value="">Default (app directory)</option>
              {drives.map((d) => (
                <option key={d.path} value={d.path}>
                  {d.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={applyPath}
              disabled={!isAdmin || setPath.isPending}
              title={!isAdmin ? 'Admin role required to change storage location' : 'Apply selected path'}
              className="px-3 py-1.5 rounded text-sm font-medium bg-cyan-600 hover:bg-cyan-500 text-black disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {setPath.isPending ? 'Applying…' : 'Use this location'}
            </button>
          </div>
          {!isAdmin && <p className="text-zinc-500 text-xs mt-2">Only an administrator can change the storage location.</p>}
        </>
      )}
    </section>
  );
}

function LegalHoldSection({ error, setError }: { error: string | null; setError: (s: string | null) => void }) {
  const queryClient = useQueryClient();
  const { data: holdsData, isLoading: holdsLoading } = useQuery({ queryKey: ['legal_holds'], queryFn: fetchLegalHolds });
  const [addType, setAddType] = useState<'event' | 'recording'>('event');
  const [addResourceId, setAddResourceId] = useState('');
  const [addReason, setAddReason] = useState('');
  const addHold = useMutation({
    mutationFn: () => addLegalHold(addType, addResourceId.trim(), addReason.trim() || undefined),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['legal_holds'] });
      setAddResourceId('');
      setAddReason('');
    },
    onError: (e: Error) => setError(e.message),
  });
  const removeHold = useMutation({
    mutationFn: (id: number) => removeLegalHold(id),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['legal_holds'] });
    },
    onError: (e: Error) => setError(e.message),
  });
  const holds = holdsData?.holds ?? [];

  const exportLegalHoldsCsv = () => {
    const headers = ['id', 'resource_type', 'resource_id', 'held_at', 'held_by', 'reason'];
    const rows = holds.map((h) => [h.id, h.resource_type, h.resource_id, h.held_at, h.held_by, (h.reason ?? '').replace(/"/g, '""')]);
    const csv = [headers.join(','), ...rows.map((r) => r.map((c) => `"${String(c)}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `legal_holds_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="mt-6 rounded-lg bg-zinc-900 border border-zinc-700 p-4">
      <h2 className="text-sm font-medium text-cyan-400 mb-2">Legal hold (evidence preservation)</h2>
      <p className="text-zinc-500 text-xs mb-3">Place holds on events or recordings to exclude them from retention deletion. Operator/admin.</p>
      {error && <p className="text-red-400 text-sm mb-2">{error}</p>}
      <div className="flex flex-wrap items-end gap-3 mb-3">
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Type</label>
          <select
            value={addType}
            onChange={(e) => setAddType(e.target.value as 'event' | 'recording')}
            className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm"
          >
            <option value="event">Event</option>
            <option value="recording">Recording</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Resource ID (event id or filename)</label>
          <input
            type="text"
            value={addResourceId}
            onChange={(e) => setAddResourceId(e.target.value)}
            placeholder={addType === 'event' ? 'e.g. 12345' : 'e.g. recording_123.avi'}
            className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm min-w-[12rem] placeholder:text-zinc-500"
          />
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Reason (optional)</label>
          <input
            type="text"
            value={addReason}
            onChange={(e) => setAddReason(e.target.value)}
            placeholder="Case or matter"
            className="px-2 py-1.5 rounded bg-zinc-800 border border-zinc-600 text-zinc-200 text-sm min-w-[10rem] placeholder:text-zinc-500"
          />
        </div>
        <button
          type="button"
          onClick={() => addResourceId.trim() && addHold.mutate()}
          disabled={!addResourceId.trim() || addHold.isPending}
          className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black text-sm font-medium disabled:opacity-50"
        >
          {addHold.isPending ? 'Adding…' : 'Add hold'}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <button
          type="button"
          onClick={exportLegalHoldsCsv}
          disabled={holds.length === 0}
          className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm disabled:opacity-50"
        >
          Export legal holds (CSV)
        </button>
      </div>
      {holdsLoading && <p className="text-zinc-500 text-sm">Loading holds…</p>}
      {holds.length > 0 && (
        <ul className="space-y-1.5 max-h-48 overflow-y-auto">
          {holds.map((h) => (
            <li key={h.id} className="flex items-center gap-2 flex-wrap text-sm">
              <span className="font-mono text-zinc-300">{h.resource_type}/{h.resource_id}</span>
              <span className="text-zinc-500">{h.held_at}</span>
              {h.reason && <span className="text-zinc-500">— {h.reason}</span>}
              <button
                type="button"
                onClick={() => removeHold.mutate(h.id)}
                disabled={removeHold.isPending}
                className="px-2 py-0.5 rounded bg-red-900/60 hover:bg-red-800/60 text-red-200 text-xs disabled:opacity-50"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      {!holdsLoading && holds.length === 0 && <p className="text-zinc-500 text-sm">No legal holds.</p>}
    </section>
  );
}
