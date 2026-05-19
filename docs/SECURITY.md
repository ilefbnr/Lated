# LateD — Security Posture

This document describes the security guarantees, trust boundaries, and hardening
practices that govern the LateD SOC platform. It is meant for both internal
auditors and SOC operators integrating the platform into their environment.

---

## 1. Trust boundaries

```
+--------------------+     untrusted    +--------------------+
|   Enterprise net   |  ─────────────►  |   Ingestion layer  |
|   (PCAP / Zeek /   |   (raw packets,  |   (parsing only,   |
|    NetFlow exports)|    raw logs)     |    NO AI logic)    |
+--------------------+                  +--------------------+
                                                  │
                                       canonical flows (validated)
                                                  ▼
+----------------------------------------------------------+
|     Internal trust zone (AI core + correlation + API)    |
+----------------------------------------------------------+
                                                  │
                                       signed events, REST/WS
                                                  ▼
+--------------------+
|     SOC analysts   |
+--------------------+
```

The **ingestion layer is the only component exposed to attacker-controlled
input**. All downstream modules consume validated canonical flows only.

---

## 2. Module isolation

- **Ingestion <-> Detection:** strict schema boundary
  (`common/schemas.py::CanonicalFlow`). Detection never parses raw packets.
- **TGNN <-> Recon:** completely independent code paths. They share no state.
  This is intentional — a poisoned TGNN cannot silence the heuristic detector.
- **Detection <-> Correlation:** correlation consumes scores, not raw graphs.
  This limits attack surface for crafted inputs.

---

## 3. Hardening checklist

- [x] All container images run as non-root.
- [x] Read-only root filesystem for ingestion containers.
- [x] Active discovery is opt-in (defaults to passive).
- [x] Model artifacts are signed and checksum-verified before load.
- [x] WebSocket channel uses bearer-token authentication.
- [x] REST endpoints enforce RBAC (analyst / supervisor / admin).
- [x] All logs are structured JSON; no PII in log lines.

---

## 4. Model-supply-chain integrity

- Training pipeline produces `tgnn_lm.pt` + `tgnn_lm.sig` (detached signature).
- Online detection refuses to load a model whose signature does not verify
  against the SOC platform's public key.
- Model metadata (training set hash, hyper-parameters, eval metrics) is
  embedded in the artifact and exposed at `/admin/model/info`.

---

## 5. Data retention

| Data class           | Retention | Storage         |
|----------------------|-----------|-----------------|
| Raw PCAP             | 7 days    | Cold storage    |
| Canonical flows      | 30 days   | Object store    |
| Snapshots            | 30 days   | Graph store     |
| Alerts               | 1 year    | Postgres        |
| Attack paths         | 1 year    | Postgres        |

---

## 6. Incident response hooks

- Every alert exposes a unique `alert_id` correlatable with upstream SIEMs.
- The correlation engine emits MITRE ATT&CK tactic/technique tags where
  applicable (TA0008 — Lateral Movement, TA0007 — Discovery).
- All explainability metadata is exportable as STIX 2.1 bundles.
