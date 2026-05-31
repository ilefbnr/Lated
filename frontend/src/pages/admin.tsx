// =============================================================================
// pages/admin.tsx — admin control surface
// =============================================================================

import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { useUser } from '@/hooks/useUser';
import { adminService } from '@/services/adminService';
import { baselineService, type BaselineStatus } from '@/services/baselineService';

type ActionState =
  | { kind: 'idle' }
  | { kind: 'pending' }
  | { kind: 'ok'; message: string }
  | { kind: 'err'; message: string };

export default function AdminPage() {
  const router = useRouter();
  const { user, hasRole } = useUser();
  const [thresholdsState, setThresholdsState] = useState<ActionState>({ kind: 'idle' });
  const [modelState, setModelState] = useState<ActionState>({ kind: 'idle' });
  const [modelInfo, setModelInfo] = useState<Record<string, unknown> | null>(null);
  const [baseline, setBaseline] = useState<BaselineStatus | null>(null);
  const [baselineState, setBaselineState] = useState<ActionState>({ kind: 'idle' });

  useEffect(() => {
    baselineService
      .status()
      .then(setBaseline)
      .catch(() => setBaseline(null));
  }, []);

  if (user !== null && !hasRole('admin')) {
    void router.replace('/overview');
    return null;
  }

  const runBaseline = async (fn: () => Promise<BaselineStatus>, okMsg: string) => {
    setBaselineState({ kind: 'pending' });
    try {
      const status = await fn();
      setBaseline(status);
      setBaselineState({ kind: 'ok', message: okMsg });
    } catch (err) {
      setBaselineState({ kind: 'err', message: err instanceof Error ? err.message : 'failed' });
    }
  };

  const reloadThresholds = async () => {
    setThresholdsState({ kind: 'pending' });
    try {
      const { status } = await adminService.reloadThresholds();
      setThresholdsState({ kind: 'ok', message: `thresholds reloaded (${status})` });
    } catch (err) {
      setThresholdsState({ kind: 'err', message: err instanceof Error ? err.message : 'failed' });
    }
  };

  const fetchModelInfo = async () => {
    setModelState({ kind: 'pending' });
    try {
      const info = await adminService.modelInfo();
      setModelInfo(info);
      setModelState({ kind: 'ok', message: 'fetched' });
    } catch (err) {
      setModelState({ kind: 'err', message: err instanceof Error ? err.message : 'failed' });
    }
  };

  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      <section className="col-span-12 xl:col-span-6">
        <GlassCard className="h-full">
          <div className="mb-3 flex items-center justify-between">
            <p className="lated-eyebrow">Detection Thresholds</p>
            <NeonBadge tone="violet">admin only</NeonBadge>
          </div>
          <p className="mb-3 text-[13px] text-[rgb(var(--lated-muted))]">
            Re-reads <code className="rounded bg-elevated px-1.5 py-0.5 font-mono text-ink">detection_thresholds.yaml</code> on the backend without restarting the process. Recon / fusion / correlation thresholds pick up the new values on their next evaluation.
          </p>
          <button
            type="button"
            onClick={reloadThresholds}
            disabled={thresholdsState.kind === 'pending'}
            className="rounded border border-cyan/60 bg-cyan/10 px-3 py-2 text-xs text-cyan transition hover:bg-cyan/20 disabled:opacity-40"
          >
            {thresholdsState.kind === 'pending' ? 'reloading...' : 'reload thresholds'}
          </button>
          {thresholdsState.kind === 'ok' && <p className="mt-3 text-xs text-emerald-300">{thresholdsState.message}</p>}
          {thresholdsState.kind === 'err' && <p className="mt-3 text-xs text-rose-300">{thresholdsState.message}</p>}
        </GlassCard>
      </section>

      <section className="col-span-12 xl:col-span-6">
        <GlassCard className="h-full">
          <div className="mb-3 flex items-center justify-between">
            <p className="lated-eyebrow">Model Inventory</p>
            <NeonBadge tone="violet">admin only</NeonBadge>
          </div>
          <p className="mb-3 text-[13px] text-[rgb(var(--lated-muted))]">
            Reads the currently loaded TGNN artifact metadata. In this phase the inference adapter is a deterministic structural placeholder — a real trained model can be wired through ModelLoader without changing this surface.
          </p>
          <button
            type="button"
            onClick={fetchModelInfo}
            disabled={modelState.kind === 'pending'}
            className="rounded border border-cyan/60 bg-cyan/10 px-3 py-2 text-xs text-cyan transition hover:bg-cyan/20 disabled:opacity-40"
          >
            {modelState.kind === 'pending' ? 'fetching...' : 'fetch model info'}
          </button>
          {modelState.kind === 'err' && <p className="mt-3 text-xs text-rose-300">{modelState.message}</p>}
          {modelInfo !== null && (
            <pre className="mt-3 max-h-60 overflow-auto rounded-md border border-outline/70 bg-elevated p-3 font-mono text-[11px] text-[rgb(var(--lated-muted))]">
              {JSON.stringify(modelInfo, null, 2)}
            </pre>
          )}
        </GlassCard>
      </section>

      <section className="col-span-12">
        <GlassCard className="h-full">
          <div className="mb-3 flex items-center justify-between">
            <p className="lated-eyebrow">Rare-Edge Baseline</p>
            <NeonBadge tone={baseline?.mode === 'frozen' ? 'violet' : 'cyan'}>
              {baseline ? `${baseline.mode} · ${baseline.edge_count} edges` : 'loading...'}
            </NeonBadge>
          </div>
          <p className="mb-4 text-[13px] text-[rgb(var(--lated-muted))]">
            The rare-edge detector keeps a living baseline of <code className="rounded bg-elevated px-1.5 py-0.5 font-mono text-ink">host → host</code> relationships.
            <strong className="text-ink"> Learning</strong> records observed traffic as normal and stays silent;
            <strong className="text-ink"> Freeze</strong> locks the baseline so any unknown edge (e.g. an attacker pivot) is flagged on every occurrence.
            Fingerprint your network, then freeze before running the attack.
          </p>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => void runBaseline(() => baselineService.setMode('learning'), 'learning — baseline is recording normal traffic')}
              disabled={baselineState.kind === 'pending'}
              className="rounded border border-cyan/60 bg-cyan/10 px-3 py-2 text-xs text-cyan transition hover:bg-cyan/20 disabled:opacity-40"
            >
              start learning
            </button>
            <button
              type="button"
              onClick={() => void runBaseline(() => baselineService.setMode('frozen'), 'frozen — detection active, baseline persisted')}
              disabled={baselineState.kind === 'pending'}
              className="rounded border border-emerald-400/60 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-300 transition hover:bg-emerald-400/20 disabled:opacity-40"
            >
              freeze &amp; detect
            </button>
            <button
              type="button"
              onClick={() => void runBaseline(() => baselineService.reset(), 'baseline cleared — relearning from scratch')}
              disabled={baselineState.kind === 'pending'}
              className="rounded border border-rose-400/50 bg-rose-400/10 px-3 py-2 text-xs text-rose-300 transition hover:bg-rose-400/20 disabled:opacity-40"
            >
              reset
            </button>
            <span className="ml-auto font-mono text-[11px] text-[rgb(var(--lated-muted))]">
              {baseline ? `${baseline.edge_count} known edges` : ''}
            </span>
          </div>

          {baselineState.kind === 'ok' && <p className="mt-3 text-xs text-emerald-300">{baselineState.message}</p>}
          {baselineState.kind === 'err' && <p className="mt-3 text-xs text-rose-300">{baselineState.message}</p>}
        </GlassCard>
      </section>
    </div>
  );
}
