# LateD — Lateral Movement Detection Platform

> Enterprise-grade SOC platform for real-time lateral movement detection
> powered by Temporal Graph Neural Networks (TGNN).

---

## 1. Overview

**LateD** is a SOC-oriented cyber security platform specialized in:

- Lateral Movement (LM) detection via Temporal Graph Neural Networks
- Internal reconnaissance detection (heuristic + behavioral)
- Attack path reconstruction
- Real-time SOC monitoring with a modern command-center UI

The platform operates in **two strictly separated phases**:

| Phase   | Purpose                                                              | Data                            |
|---------|----------------------------------------------------------------------|---------------------------------|
| OFFLINE | Train the TGNN model for lateral movement only                       | LANL flows + LANL redteam logs  |
| ONLINE  | Real-time detection on enterprise traffic                            | PCAP / Zeek / NetFlow streams   |

---

## 2. High-level architecture

```
+----------------------------------------------------------+
|                     SOC DASHBOARD (UI)                   |
|   Next.js + TypeScript + Tailwind + Framer + Cytoscape   |
+----------------------------------------------------------+
                ^                          ^
                | REST/JSON                | WebSocket (live)
                |                          |
+----------------------------------------------------------+
|              SUPERVISION LAYER (FastAPI)                 |
|  - REST API     - WebSocket server   - Alert engine      |
+----------------------------------------------------------+
                ^
+----------------------------------------------------------+
|                   CORRELATION ENGINE                     |
|  recon -> LM chaining   pivot detection   timelines      |
+----------------------------------------------------------+
                ^
+----------------------------------------------------------+
|                  DETECTION CORE (AI)                     |
|  +-------------------+   +---------------------------+   |
|  | TGNN LM Detector  |   | Reconnaissance Detector   |   |
|  +-------------------+   +---------------------------+   |
|              \             /                             |
|             +-------------------+                        |
|             | Suspicion Fusion  |                        |
|             +-------------------+                        |
+----------------------------------------------------------+
                ^
+----------------------------------------------------------+
|             TEMPORAL GRAPH MODELING                      |
|   snapshots   edge features   temporal statistics        |
+----------------------------------------------------------+
                ^
+----------------------------------------------------------+
|                    INGESTION LAYER                       |
|     PCAP parser    Zeek parser    NetFlow parser         |
|                Canonical flow schema                     |
+----------------------------------------------------------+
                ^
+----------------------------------------------------------+
|               NETWORK DISCOVERY (bootstrap)              |
|   passive / active / hybrid -> baseline topology graph   |
+----------------------------------------------------------+
```

---

## 3. Repository layout

```
LateD/
├── backend/         # Python services: ingestion, graph, AI core, API, WS
├── frontend/        # Next.js SOC dashboard
├── docs/            # Architecture and deployment documentation
├── docker-compose.yml
└── README.md
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full module breakdown.

---

## 4. Module index

| Module                  | Path                              | Responsibility                                  |
|-------------------------|-----------------------------------|-------------------------------------------------|
| Network Discovery       | `backend/src/lated/discovery`     | Bootstrap baseline topology                     |
| Ingestion               | `backend/src/lated/ingestion`     | Normalize PCAP / Zeek / NetFlow into canonical flows |
| Temporal Graph Modeling | `backend/src/lated/graph`         | Build temporal graph snapshots                  |
| Detection Core          | `backend/src/lated/detection`     | TGNN LM detector + Recon detector + Fusion     |
| Correlation             | `backend/src/lated/correlation`   | Recon→LM chaining, attack path reconstruction   |
| Supervision (SOC API)   | `backend/src/lated/supervision`   | REST API, WebSocket, alert engine, persistence  |
| Offline Pipeline        | `backend/src/lated/pipelines/offline` | LANL training pipeline                       |
| Online Pipeline         | `backend/src/lated/pipelines/online`  | Real-time streaming orchestration            |
| SOC Frontend            | `frontend/src`                    | React/Next.js operator console                  |

---

## 5. Running (dev)

```bash
# Backend
docker compose up backend

# Frontend
docker compose up frontend
```

Configuration is centralized in `backend/config/settings.yaml` and overridden by
environment variables — see `.env.example`.

---

## 6. Security posture

- Ingestion is **isolated** from AI logic — corrupted input cannot corrupt the model.
- Reconnaissance detection is **completely separate** from the TGNN — failure modes do not cascade.
- All scoring is **explainable** — every alert carries a metadata trail back to source flows.
- Active discovery is **opt-in** — passive mode is the safe default.

---

## 7. License

Proprietary — internal SOC platform.
