// =============================================================================
// pages/admin.tsx — admin control surface
// =============================================================================

import { useState } from 'react';
import { useRouter } from 'next/router';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { adminService } from '@/services/adminService';
import { useUser } from '@/hooks/useUser';

type ActionState = { kind: 'idle' } | { kind: 'pending' } | { kind: 'ok'; message: string } | { kind: 'err'; message: string };

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
      setThresholdsState({
        kind: 'err',
        message: err instanceof Error ? err.message : 'failed',
      });
    }
  };

  const fetchModelInfo = async () => {
    setModelState({ kind: 'pending' });
    try {
      const info = await adminService.modelInfo();
      setModelInfo(info);
      setModelState({ kind: 'ok', message: 'fetched' });
    } catch (err) {
      setModelState({
        kind: 'err',
        message: err instanceof Error ? err.message : 'failed',
      });
    }
  };

  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      <section className="col-span-12 xl:col-span-6">
        <GlassCard className="h-full">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs uppercase tracking-[0.25em] text-muted">Detection Thresholds</p>
            <NeonBadge tone="violet">admin only</NeonBadge>
          </div>
          <p className="text-sm text-muted mb-3">
            Re-reads <span className="font-mono text-ink">detection_thresholds.yaml</span> on the
            backend without restarting the process. Recon / fusion / correlation thresholds
            pick up the new values on their next evaluation.
          </p>
          <button
            onClick={reloadThresholds}
            disabled={thresholdsState.kind === 'pending'}
            className="text-xs px-3 py-2 rounded border border-cyan/60 text-cyan hover:bg-cyan/10 disabled:opacity-40"
          >
            reload thresholds
          </button>
          {thresholdsState.kind === 'ok' && (
            <p className="text-xs text-emerald-300 mt-3">{thresholdsState.message}</p>
          )}
          {thresholdsState.kind === 'err' && (
            <p className="text-xs text-rose-300 mt-3">{thresholdsState.message}</p>
          )}
        </GlassCard>
      </section>

      <section className="col-span-12 xl:col-span-6">
        <GlassCard className="h-full">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs uppercase tracking-[0.25em] text-muted">Model Inventory</p>
            <NeonBadge tone="violet">admin only</NeonBadge>
          </div>
          <p className="text-sm text-muted mb-3">
            Reads the currently loaded TGNN artifact metadata. In this phase the inference
            adapter is a deterministic structural placeholder — a real trained model can
            be wired through ModelLoader without changing this surface.
          </p>
          <button
            onClick={fetchModelInfo}
            disabled={modelState.kind === 'pending'}
            className="text-xs px-3 py-2 rounded border border-cyan/60 text-cyan hover:bg-cyan/10 disabled:opacity-40"
          >
            fetch model info
          </button>
          {modelState.kind === 'err' && (
            <p className="text-xs text-rose-300 mt-3">{modelState.message}</p>
          )}
          {modelInfo !== null && (
            <pre className="mt-3 p-3 rounded border border-outline/40 bg-elevated/40 text-[11px] font-mono text-muted overflow-auto max-h-64">
              {JSON.stringify(modelInfo, null, 2)}
            </pre>
          )}
        </GlassCard>
      </section>
    </div>
  );
}
