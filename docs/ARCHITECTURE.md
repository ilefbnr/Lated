# LateD — Architecture Reference

This document explains how the LateD platform is internally organized and how
each module interacts with the others. It is the authoritative map of the
codebase. Every directory in `backend/src/lated/` corresponds to a numbered
section below.

---

## 1. Design principles

1. **Strict module separation.** Ingestion never imports detection. Detection
   never imports correlation. Each module exposes a narrow contract.
2. **Two-phase architecture.** Offline (training) and online (inference) share
   only the *model artifact* and the *schema definitions* — nothing else.
3. **Failure isolation.** TGNN failure must not silence recon. Recon failure
   must not silence TGNN. Their scores fuse only at the very end.
4. **Explainability is non-negotiable.** Every alert carries: source flows,
   contributing scores, time window, and reasoning trail.
5. **Replayability.** Every detection can be re-run from stored canonical
   flows. This enables forensic re-investigation.

---

## 2. Phase A — Offline training

```
LANL raw data
    │
    ▼
[lanl_parser]  ──►  [weak_labeler]  ──►  [dataset_builder]
                                              │
                                              ▼
                            ┌──────────────────────────────┐
                            │  pretrain_ssl  (self-superv) │
                            └──────────────────────────────┘
                                              │
                                              ▼
                            ┌──────────────────────────────┐
                            │  finetune_lm   (semi-superv) │
                            └──────────────────────────────┘
                                              │
                                              ▼
                                       [evaluate]
                                              │
                                              ▼
                                     [export_model] ──► tgnn_lm.pt
```

The output is a single TGNN model trained **only** for lateral movement.
Reconnaissance is **not** part of the model — by design.

---

## 3. Phase B — Online detection

```
[discovery] ──► baseline graph
                    │
                    ▼
[ingestion] ──► canonical flows
                    │
                    ▼
[graph builder] ──► temporal snapshots
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
[TGNN LM detector]      [Recon detector]
        │                        │
        └────────┬───────────────┘
                 ▼
        [Suspicion fusion]
                 │
                 ▼
        [Correlation engine] ──► attack paths
                 │
                 ▼
        [Alert engine] ──► REST API + WebSocket ──► SOC UI
```

---

## 4. Module contracts

### 4.1 Discovery
- **In:**  passive traffic, ARP, DNS, optional active scan
- **Out:** `BaselineGraph` (host registry + initial topology)

### 4.2 Ingestion
- **In:**  PCAP / Zeek / NetFlow
- **Out:** stream of `CanonicalFlow` records

### 4.3 Temporal graph
- **In:**  `CanonicalFlow` stream
- **Out:** `TemporalSnapshot` objects with edge/node features

### 4.4 Detection — TGNN
- **In:**  `TemporalSnapshot`
- **Out:** `LMScore` per edge / per host

### 4.5 Detection — Recon
- **In:**  sliding window over `CanonicalFlow`
- **Out:** `ReconScore` per source host

### 4.6 Detection — Fusion
- **In:**  `LMScore` + `ReconScore` + host history
- **Out:** `SuspicionScore` + explainability metadata

### 4.7 Correlation
- **In:**  `SuspicionScore` stream
- **Out:** `AttackPath` objects (chronological, hosts + pivots)

### 4.8 Supervision
- **In:**  alerts, paths, host risk
- **Out:** REST endpoints + WebSocket events to the SOC UI

---

## 5. Data flow guarantees

- Every `CanonicalFlow` is **immutable** once persisted.
- Snapshots are **windowed** (default 30s) and never overlap.
- Scores are **monotone-explainable**: increasing input suspicion never
  decreases output suspicion.

---

## 6. Threat model

LateD assumes:
- Sensors are trusted (host of the ingestion pipeline is not the target).
- The training set may contain noise but is not actively poisoned.
- The attacker is **inside** the perimeter — lateral movement is the focus.

LateD does NOT address:
- Endpoint malware analysis (out of scope — SIEM/EDR territory).
- Perimeter intrusion detection (covered by upstream IDS).
