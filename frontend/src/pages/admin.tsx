// =============================================================================
// pages/admin.tsx — admin control surface
// =============================================================================

import { useState } from 'react';
import { useRouter } from 'next/router';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { useUser } from '@/hooks/useUser';
import { adminService } from '@/services/adminService';

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

  if (user !== null && !hasRole('admin')) {
    void router.replace('/overview');
    return null;
  }

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
    </div>
  );
}
