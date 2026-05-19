# LateD — Deployment Guide

## 1. Environments

| Environment | Purpose                          | Notes                                   |
|-------------|----------------------------------|-----------------------------------------|
| dev         | Local laptop, mocked sensors     | Uses sample PCAP / synthetic flows      |
| staging     | Pre-prod, mirrored SOC traffic   | Connected to a TAP/SPAN port            |
| production  | Live SOC                         | Hardened, sealed model artifact         |

## 2. Bootstrap sequence

1. Run **Network Discovery** in passive mode for ≥24h to build a baseline graph.
2. Load the trained TGNN artifact (`tgnn_lm.pt`) into the detection container.
3. Switch ingestion from `replay` to `live`.
4. Verify the SOC dashboard receives `health.ok` heartbeat over WebSocket.

## 3. Operational notes

- **Model refresh:** offline pipeline produces a new artifact monthly. Operators
  swap it via the `/admin/model` API endpoint (atomic hot-reload).
- **Threshold tuning:** all detection thresholds live in
  `backend/config/detection_thresholds.yaml` — no code change required.
- **Replay mode:** any historical incident can be replayed by pointing the
  ingestion service to stored canonical flows.

## 4. Capacity sizing (indicative)

| Component       | Per 10k hosts          | Per 100k hosts         |
|-----------------|------------------------|------------------------|
| TGNN inference  | 1 GPU (T4-class)       | 4 GPUs (A10-class)     |
| Graph store     | 8 GB RAM               | 64 GB RAM              |
| API + WS        | 2 cores                | 8 cores                |

## 5. Observability

- Structured JSON logs (`backend/config/logging.yaml`).
- `/health` endpoint reports per-module status.
- Prometheus metrics exposed at `/metrics`.
