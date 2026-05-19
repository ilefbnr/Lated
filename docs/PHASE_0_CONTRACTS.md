# LateD — Phase 0 Contracts

This document freezes the minimum cross-module contracts required before
implementing runtime logic in phases 1 and 2.

## 1. Goals

- Freeze shared backend schemas.
- Align frontend types with backend payloads.
- Freeze REST endpoints and WebSocket event names.
- Freeze the runtime config shape expected by `ConfigManager`.

## 2. Shared schema rules

- All cross-module payloads come from `backend/src/lated/common/schemas.py`.
- `schema_version` is required on persisted and streamed domain objects.
- Timestamps are UTC ISO-8601.
- Scores are normalized in the `0..1` range.
- Backend payloads use `snake_case`.

## 3. Core domain objects

- `CanonicalFlow`
  - canonical network flow emitted by ingestion
  - stable fields: `flow_id`, `ts`, `src_host`, `dst_host`, `src_port`, `dst_port`, `protocol`, `duration`, `packet_count`, `byte_count`, `source_sensor`, `schema_version`
- `Host`
  - canonical host identity shared by discovery, ingestion, supervision, and UI
- `TemporalSnapshot`
  - non-overlapping graph window
  - `snapshot_id` is the stable identifier used in explainability and replay
- `LMScore`, `ReconScore`, `SuspicionScore`
  - outputs exchanged between detection and correlation
- `Alert`
  - atomic SOC alert exposed over REST and WebSocket
- `AttackPath`
  - chronological correlated path exposed over REST and used by graph/timeline UI
- `WSEvent`
  - canonical frame envelope for server-to-client WebSocket messages

## 4. REST contract target

The backend target surface for the supervision API is:

- `GET /health`
  - liveness + readiness summary
- `GET /metrics`
  - Prometheus metrics
- `GET /alerts`
  - returns `{ rows, total }`
- `GET /alerts/{alert_id}`
  - returns one `Alert`
- `POST /alerts/{alert_id}/ack`
- `POST /alerts/{alert_id}/close`
- `GET /hosts`
  - returns `Host[]`
- `GET /hosts/top-risky`
  - returns `HostRiskSummary[]`
- `GET /hosts/{host_id}`
  - returns one `Host`
- `GET /hosts/{host_id}/heatmap`
  - returns `HostHeatmapCell[]`
- `GET /graph/baseline`
  - returns `GraphPayload`
- `GET /graph/snapshot/latest`
  - returns `GraphPayload`
- `GET /graph/snapshot/{ts}`
  - returns `GraphPayload`
- `GET /graph/host/{host_id}`
  - returns `GraphPayload`
- `GET /flows`
  - returns `{ rows, total }`
- `GET /flows/{flow_id}`
  - returns one suspicious flow payload
- `GET /flows/by-host/{host_id}`
  - returns suspicious flows for a host
- `GET /paths`
  - returns `{ rows, total }` or a paginated path list
- `GET /paths/{path_id}`
  - returns one `AttackPath`
- `GET /paths/{path_id}/timeline`
  - returns the structured timeline for one path
- `GET /paths/{path_id}/graph`
  - returns `GraphPayload`

## 5. WebSocket contract target

### Channels

- `alerts`
- `graph`
- `hosts`
- `flows`
- `health`
- `timeline`

### Server event names

- `alert.new`
- `alert.update`
- `graph.update`
- `host.risk`
- `flow.new`
- `path.new`
- `health.heartbeat`

### Client frame types

The WebSocket server must accept these client actions:

- `subscribe`
- `unsubscribe`
- `pong`

### Server frame shape

```json
{
  "channel": "alerts",
  "event": "alert.new",
  "payload": {},
  "ts": "2026-05-15T10:15:00Z",
  "schema_version": "1.0.0"
}
```

## 6. Config contract target

`backend/config/settings.yaml` is the source of truth for runtime config.

Required sections:

- `env`
- `api`
- `logging`
- `discovery`
- `ingestion`
  - includes `mode: replay | live`
  - includes `source: pcap | zeek | netflow`
- `graph`
- `detection.tgnn`
- `detection.recon`
- `detection.fusion`
- `correlation`
- `supervision.alerts`
- `supervision.websocket`

Hot-reloadable config is limited to `backend/config/detection_thresholds.yaml`.

## 7. Frontend alignment rules

- Frontend types mirror backend payload names in `snake_case`.
- No implicit renaming in transport contracts.
- `frontend/src/types/*.ts` must stay aligned with `common/schemas.py`.
- Graph endpoints return Cytoscape-shaped payloads as defined in `frontend/src/types/graph.ts`.

## 8. Phase 1 entry criteria

Phase 1 can start once these are true:

- shared schemas are frozen
- config shape is frozen
- endpoint names are frozen
- WebSocket channel and event names are frozen
- frontend and backend no longer disagree on field naming
