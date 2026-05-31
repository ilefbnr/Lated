# =============================================================================
# lated.common.config_manager — layered configuration loader
# =============================================================================
#
# PURPOSE
# -------
# Loads configuration from a layered stack and exposes a single, typed,
# validated view to every other module.
#
# LAYERS (highest precedence first)
# ---------------------------------
#   1. Environment variables (LATED_*)
#   2. config/detection_thresholds.yaml  (hot-reloadable)
#   3. config/settings.yaml              (base)
#   4. Built-in defaults                 (last-resort safety net)
#
# OUTPUTS
# -------
#   - A merged `AppConfig` dataclass-like object accessible as `ConfigManager.get()`.
#   - Sub-views: `.api`, `.discovery`, `.ingestion`, `.graph`, `.detection`,
#     `.correlation`, `.supervision`.
#
# CYBERSECURITY REASONING
# -----------------------
# - Validation is FAIL-LOUD. Out-of-range thresholds (e.g. negative timeouts,
#   probabilities > 1) cause a startup-time ConfigError. Silent fallbacks
#   would be a SOC anti-pattern — operators must know exactly what's loaded.
# - Hot reload (SIGHUP / /admin/reload-thresholds) applies ONLY to
#   detection_thresholds.yaml. Core settings require a process restart
#   (preserves audit trail).
#
# INTERACTIONS
# ------------
# - main.py calls `ConfigManager.load()` at startup.
# - Every module reads its slice via `ConfigManager.get().graph` etc.
# =============================================================================

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lated.common.exceptions import ConfigError
from lated.common.network_topology import (
    NetworkTopology,
    ZoneEntry,
    parse_zone_entries,
)


# -----------------------------------------------------------------------------
# Sub-config dataclasses (one per module — mirrors settings.yaml)
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class ApiConfig:
    host: str
    port: int
    cors_origins: list[str]


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    format: str


@dataclass(frozen=True)
class NetworkTopologyConfig:
    """
    Parsed `network_topology` section. The `topology` attribute is the live
    classifier ready to use; `zone_entries` and `critical_assets` are kept
    available for diagnostics / API exposure (e.g. /health).
    """
    zone_entries: tuple[ZoneEntry, ...]
    critical_assets: tuple[str, ...]
    topology: NetworkTopology


@dataclass(frozen=True)
class DiscoveryConfig:
    mode: str                         # passive | active | hybrid
    passive_window_seconds: int
    active_scan_enabled: bool


@dataclass(frozen=True)
class IngestionConfig:
    mode: str                         # replay | live | replay_live
    source: str                       # pcap | zeek | netflow
    pcap_interface: str
    pcap_path: str
    zeek_log_dir: str
    netflow_port: int
    batch_size: int
    replay_speed: float               # used only in mode=replay_live
    zeek_log_types: list[str]         # which Zeek logs to tail in live/replay_live


@dataclass(frozen=True)
class GraphConfig:
    snapshot_window_seconds: int
    snapshot_overlap: bool
    max_in_memory_snapshots: int
    edge_feature_set: list[str]


@dataclass(frozen=True)
class TgnnConfig:
    model_path: str
    device: str
    batch_size: int
    node_mapping_path: str = ""


@dataclass(frozen=True)
class ReconConfig:
    window_seconds: int
    min_unique_dst: int


@dataclass(frozen=True)
class FusionConfig:
    weight_lm: float
    weight_recon: float
    weight_history: float


@dataclass(frozen=True)
class DetectionConfig:
    tgnn: TgnnConfig
    recon: ReconConfig
    fusion: FusionConfig


@dataclass(frozen=True)
class CorrelationConfig:
    temporal_continuity_seconds: int
    max_path_length: int
    enable_mitre_tags: bool


@dataclass(frozen=True)
class SupervisionConfig:
    alert_persistence: str
    alert_retention_days: int
    ws_heartbeat_seconds: int
    ws_auth_required: bool


@dataclass(frozen=True)
class TgnnThresholds:
    lm_alert_threshold: float
    lm_severity_high: float
    lm_severity_medium: float


@dataclass(frozen=True)
class ReconThresholds:
    fanout_threshold: int
    port_diversity_threshold: int
    burst_packets_per_sec: int
    low_bytes_per_connection: int
    sequential_probe_min_seq: int


@dataclass(frozen=True)
class FusionThresholds:
    suspicion_alert_threshold: float
    host_risk_decay_per_hour: float


@dataclass(frozen=True)
class CorrelationThresholds:
    recon_to_lm_max_gap_seconds: int
    min_path_confidence: float
    pivot_min_neighbors: int


@dataclass(frozen=True)
class ThresholdsConfig:
    tgnn: TgnnThresholds
    recon: ReconThresholds
    fusion: FusionThresholds
    correlation: CorrelationThresholds


@dataclass(frozen=True)
class AppConfig:
    """Aggregate view returned by ConfigManager.get()."""
    env: str
    api: ApiConfig
    logging: LoggingConfig
    network_topology: NetworkTopologyConfig
    discovery: DiscoveryConfig
    ingestion: IngestionConfig
    graph: GraphConfig
    detection: DetectionConfig
    correlation: CorrelationConfig
    supervision: SupervisionConfig
    thresholds: ThresholdsConfig


# -----------------------------------------------------------------------------
# Loader
# -----------------------------------------------------------------------------
class ConfigManager:
    """
    Layered configuration loader. Singleton-ish via class methods.

    Lifecycle
    ---------
      ConfigManager.load(settings_path, thresholds_path)
      ConfigManager.get() -> AppConfig
      ConfigManager.reload_thresholds()    # SIGHUP / admin endpoint

    Internal logic
    --------------
    1. Read YAML files into raw dicts.
    2. Overlay env vars (LATED_*) using a flat key mapping.
    3. Validate each section against the @dataclass fields (range + type).
    4. Build the immutable AppConfig.
    5. Cache the result; expose via .get().

    Reload semantics
    ----------------
    Only the `detection_thresholds.yaml` section may be hot-reloaded. Reloading
    settings.yaml would change ingestion sources, ports, etc. — those changes
    require a clean restart for audit purposes.
    """

    _config: AppConfig | None = None
    _settings_path: Path | None = None
    _thresholds_path: Path | None = None
    _settings_raw: dict[str, Any] | None = None

    @classmethod
    def load(cls, settings_path: str, thresholds_path: str) -> AppConfig:
        cls._settings_path = Path(settings_path)
        cls._thresholds_path = Path(thresholds_path)
        settings_raw = cls._load_yaml(cls._settings_path)
        thresholds_raw = cls._load_yaml(cls._thresholds_path)
        cls._apply_env_overrides(settings_raw)
        cls._settings_raw = deepcopy(settings_raw)
        cls._config = cls._build_config(settings_raw, thresholds_raw)
        return cls._config

    @classmethod
    def get(cls) -> AppConfig:
        if cls._config is None:
            raise ConfigError("ConfigManager.get() called before ConfigManager.load().")
        return cls._config

    @classmethod
    def reload_thresholds(cls) -> None:
        if cls._settings_raw is None or cls._thresholds_path is None:
            raise ConfigError("ConfigManager.reload_thresholds() called before load().")

        thresholds_raw = cls._load_yaml(cls._thresholds_path)
        cls._config = cls._build_config(deepcopy(cls._settings_raw), thresholds_raw)

    @classmethod
    def _load_yaml(cls, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ConfigError(f"Configuration file not found: {path}")

        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}

        if not isinstance(payload, dict):
            raise ConfigError(f"Configuration file must contain a mapping: {path}")
        return payload

    @classmethod
    def _apply_env_overrides(cls, payload: dict[str, Any], prefix: tuple[str, ...] = ()) -> None:
        for key, value in payload.items():
            path = prefix + (key,)
            if isinstance(value, dict):
                cls._apply_env_overrides(value, path)
                continue

            env_name = "LATED_" + "_".join(part.upper() for part in path)
            if env_name not in os.environ:
                continue

            payload[key] = cls._parse_env_value(os.environ[env_name], value)

    @staticmethod
    def _parse_env_value(raw: str, current: Any) -> Any:
        if isinstance(current, bool):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(current, int) and not isinstance(current, bool):
            return int(raw)
        if isinstance(current, float):
            return float(raw)
        if isinstance(current, list):
            return [item.strip() for item in raw.split(",") if item.strip()]
        return raw

    @classmethod
    def _build_config(
        cls,
        settings_raw: dict[str, Any],
        thresholds_raw: dict[str, Any],
    ) -> AppConfig:
        api_raw = cls._require_dict(settings_raw, "api")
        logging_raw = cls._require_dict(settings_raw, "logging")
        network_topology_raw = settings_raw.get("network_topology") or {}
        if not isinstance(network_topology_raw, dict):
            raise ConfigError("Configuration section 'network_topology' must be a mapping.")
        discovery_raw = cls._require_dict(settings_raw, "discovery")
        ingestion_raw = cls._require_dict(settings_raw, "ingestion")
        graph_raw = cls._require_dict(settings_raw, "graph")
        detection_raw = cls._require_dict(settings_raw, "detection")
        correlation_raw = cls._require_dict(settings_raw, "correlation")
        supervision_raw = cls._require_dict(settings_raw, "supervision")

        supervision_alerts_raw = cls._require_dict(supervision_raw, "alerts")
        supervision_ws_raw = cls._require_dict(supervision_raw, "websocket")

        thresholds = cls._build_thresholds(thresholds_raw)

        env = str(settings_raw.get("env", "development"))
        cls._ensure(env in {"development", "staging", "production"}, "Invalid env value.")

        api = ApiConfig(
            host=str(api_raw.get("host", "0.0.0.0")),
            port=cls._as_int(api_raw.get("port"), "api.port", minimum=1, maximum=65535),
            cors_origins=cls._as_str_list(api_raw.get("cors_origins", []), "api.cors_origins"),
        )

        logging = LoggingConfig(
            level=cls._as_log_level(logging_raw.get("level"), "logging.level"),
            format=cls._as_choice(logging_raw.get("format"), "logging.format", {"json", "console"}),
        )

        network_topology = cls._build_network_topology(network_topology_raw)

        discovery = DiscoveryConfig(
            mode=cls._as_choice(discovery_raw.get("mode"), "discovery.mode", {"passive", "active", "hybrid"}),
            passive_window_seconds=cls._as_int(
                discovery_raw.get("passive_window_seconds"),
                "discovery.passive_window_seconds",
                minimum=1,
            ),
            active_scan_enabled=cls._as_bool(
                discovery_raw.get("active_scan_enabled"),
                "discovery.active_scan_enabled",
            ),
        )

        ingestion = IngestionConfig(
            mode=cls._as_choice(ingestion_raw.get("mode"), "ingestion.mode", {"replay", "live", "replay_live"}),
            source=cls._as_choice(ingestion_raw.get("source"), "ingestion.source", {"pcap", "zeek", "netflow"}),
            pcap_interface=str(ingestion_raw.get("pcap_interface", "")),
            pcap_path=str(ingestion_raw.get("pcap_path", "")),
            zeek_log_dir=str(ingestion_raw.get("zeek_log_dir", "")),
            netflow_port=cls._as_int(
                ingestion_raw.get("netflow_port"),
                "ingestion.netflow_port",
                minimum=1,
                maximum=65535,
            ),
            batch_size=cls._as_int(ingestion_raw.get("batch_size"), "ingestion.batch_size", minimum=1),
            replay_speed=cls._as_float(
                ingestion_raw.get("replay_speed", 1.0),
                "ingestion.replay_speed",
                minimum=0.1,
                maximum=10000.0,
            ),
            zeek_log_types=cls._as_str_list(
                ingestion_raw.get(
                    "zeek_log_types",
                    ["conn", "smb_files", "smb_mapping", "dce_rpc", "ntlm", "kerberos"],
                ),
                "ingestion.zeek_log_types",
            ),
        )

        graph = GraphConfig(
            snapshot_window_seconds=cls._as_int(
                graph_raw.get("snapshot_window_seconds"),
                "graph.snapshot_window_seconds",
                minimum=1,
            ),
            snapshot_overlap=cls._as_bool(graph_raw.get("snapshot_overlap"), "graph.snapshot_overlap"),
            max_in_memory_snapshots=cls._as_int(
                graph_raw.get("max_in_memory_snapshots"),
                "graph.max_in_memory_snapshots",
                minimum=1,
            ),
            edge_feature_set=cls._as_str_list(
                graph_raw.get("edge_feature_set", []),
                "graph.edge_feature_set",
            ),
        )
        cls._ensure(not graph.snapshot_overlap, "graph.snapshot_overlap must remain false.")

        detection_tgnn_raw = cls._require_dict(detection_raw, "tgnn")
        detection_recon_raw = cls._require_dict(detection_raw, "recon")
        detection_fusion_raw = cls._require_dict(detection_raw, "fusion")

        detection = DetectionConfig(
            tgnn=TgnnConfig(
                model_path=str(detection_tgnn_raw.get("model_path", "")),
                device=cls._as_choice(detection_tgnn_raw.get("device"), "detection.tgnn.device", {"cpu", "cuda"}),
                batch_size=cls._as_int(
                    detection_tgnn_raw.get("batch_size"),
                    "detection.tgnn.batch_size",
                    minimum=1,
                ),
                node_mapping_path=str(detection_tgnn_raw.get("node_mapping_path", "")),
            ),
            recon=ReconConfig(
                window_seconds=cls._as_int(
                    detection_recon_raw.get("window_seconds"),
                    "detection.recon.window_seconds",
                    minimum=1,
                ),
                min_unique_dst=cls._as_int(
                    detection_recon_raw.get("min_unique_dst"),
                    "detection.recon.min_unique_dst",
                    minimum=1,
                ),
            ),
            fusion=FusionConfig(
                weight_lm=cls._as_float(
                    detection_fusion_raw.get("weight_lm"),
                    "detection.fusion.weight_lm",
                    minimum=0,
                    maximum=1,
                ),
                weight_recon=cls._as_float(
                    detection_fusion_raw.get("weight_recon"),
                    "detection.fusion.weight_recon",
                    minimum=0,
                    maximum=1,
                ),
                weight_history=cls._as_float(
                    detection_fusion_raw.get("weight_history"),
                    "detection.fusion.weight_history",
                    minimum=0,
                    maximum=1,
                ),
            ),
        )
        cls._ensure(
            round(
                detection.fusion.weight_lm
                + detection.fusion.weight_recon
                + detection.fusion.weight_history,
                8,
            )
            == 1.0,
            "detection.fusion weights must sum to 1.0.",
        )

        correlation = CorrelationConfig(
            temporal_continuity_seconds=cls._as_int(
                correlation_raw.get("temporal_continuity_seconds"),
                "correlation.temporal_continuity_seconds",
                minimum=1,
            ),
            max_path_length=cls._as_int(
                correlation_raw.get("max_path_length"),
                "correlation.max_path_length",
                minimum=1,
            ),
            enable_mitre_tags=cls._as_bool(
                correlation_raw.get("enable_mitre_tags"),
                "correlation.enable_mitre_tags",
            ),
        )

        supervision = SupervisionConfig(
            alert_persistence=str(supervision_alerts_raw.get("persistence", "memory")),
            alert_retention_days=cls._as_int(
                supervision_alerts_raw.get("retention_days"),
                "supervision.alerts.retention_days",
                minimum=1,
            ),
            ws_heartbeat_seconds=cls._as_int(
                supervision_ws_raw.get("heartbeat_seconds"),
                "supervision.websocket.heartbeat_seconds",
                minimum=1,
            ),
            ws_auth_required=cls._as_bool(
                supervision_ws_raw.get("auth_required"),
                "supervision.websocket.auth_required",
            ),
        )

        return AppConfig(
            env=env,
            api=api,
            logging=logging,
            network_topology=network_topology,
            discovery=discovery,
            ingestion=ingestion,
            graph=graph,
            detection=detection,
            correlation=correlation,
            supervision=supervision,
            thresholds=thresholds,
        )

    @classmethod
    def _build_network_topology(cls, raw: dict[str, Any]) -> NetworkTopologyConfig:
        zones_raw = raw.get("zones", []) or []
        if not isinstance(zones_raw, list):
            raise ConfigError("Configuration value 'network_topology.zones' must be a list.")

        critical_raw = raw.get("critical_assets", []) or []
        if not isinstance(critical_raw, list) or any(
            not isinstance(item, str) for item in critical_raw
        ):
            raise ConfigError(
                "Configuration value 'network_topology.critical_assets' must be a list of strings."
            )

        try:
            entries = parse_zone_entries(zones_raw)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

        topology = NetworkTopology(entries=entries, critical_assets=critical_raw)
        return NetworkTopologyConfig(
            zone_entries=tuple(entries),
            critical_assets=tuple(critical_raw),
            topology=topology,
        )

    @classmethod
    def _build_thresholds(cls, raw: dict[str, Any]) -> ThresholdsConfig:
        tgnn_raw = cls._require_dict(raw, "tgnn")
        recon_raw = cls._require_dict(raw, "recon")
        fusion_raw = cls._require_dict(raw, "fusion")
        correlation_raw = cls._require_dict(raw, "correlation")

        return ThresholdsConfig(
            tgnn=TgnnThresholds(
                lm_alert_threshold=cls._as_float(
                    tgnn_raw.get("lm_alert_threshold"),
                    "thresholds.tgnn.lm_alert_threshold",
                    minimum=0,
                    maximum=1,
                ),
                lm_severity_high=cls._as_float(
                    tgnn_raw.get("lm_severity_high"),
                    "thresholds.tgnn.lm_severity_high",
                    minimum=0,
                    maximum=1,
                ),
                lm_severity_medium=cls._as_float(
                    tgnn_raw.get("lm_severity_medium"),
                    "thresholds.tgnn.lm_severity_medium",
                    minimum=0,
                    maximum=1,
                ),
            ),
            recon=ReconThresholds(
                fanout_threshold=cls._as_int(
                    recon_raw.get("fanout_threshold"),
                    "thresholds.recon.fanout_threshold",
                    minimum=1,
                ),
                port_diversity_threshold=cls._as_int(
                    recon_raw.get("port_diversity_threshold"),
                    "thresholds.recon.port_diversity_threshold",
                    minimum=1,
                ),
                burst_packets_per_sec=cls._as_int(
                    recon_raw.get("burst_packets_per_sec"),
                    "thresholds.recon.burst_packets_per_sec",
                    minimum=1,
                ),
                low_bytes_per_connection=cls._as_int(
                    recon_raw.get("low_bytes_per_connection"),
                    "thresholds.recon.low_bytes_per_connection",
                    minimum=0,
                ),
                sequential_probe_min_seq=cls._as_int(
                    recon_raw.get("sequential_probe_min_seq"),
                    "thresholds.recon.sequential_probe_min_seq",
                    minimum=1,
                ),
            ),
            fusion=FusionThresholds(
                suspicion_alert_threshold=cls._as_float(
                    fusion_raw.get("suspicion_alert_threshold"),
                    "thresholds.fusion.suspicion_alert_threshold",
                    minimum=0,
                    maximum=1,
                ),
                host_risk_decay_per_hour=cls._as_float(
                    fusion_raw.get("host_risk_decay_per_hour"),
                    "thresholds.fusion.host_risk_decay_per_hour",
                    minimum=0,
                    maximum=1,
                ),
            ),
            correlation=CorrelationThresholds(
                recon_to_lm_max_gap_seconds=cls._as_int(
                    correlation_raw.get("recon_to_lm_max_gap_seconds"),
                    "thresholds.correlation.recon_to_lm_max_gap_seconds",
                    minimum=1,
                ),
                min_path_confidence=cls._as_float(
                    correlation_raw.get("min_path_confidence"),
                    "thresholds.correlation.min_path_confidence",
                    minimum=0,
                    maximum=1,
                ),
                pivot_min_neighbors=cls._as_int(
                    correlation_raw.get("pivot_min_neighbors"),
                    "thresholds.correlation.pivot_min_neighbors",
                    minimum=1,
                ),
            ),
        )

    @staticmethod
    def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise ConfigError(f"Configuration section '{key}' must be a mapping.")
        return value

    @staticmethod
    def _ensure(condition: bool, message: str) -> None:
        if not condition:
            raise ConfigError(message)

    @classmethod
    def _as_choice(cls, value: Any, key: str, allowed: set[str]) -> str:
        text = str(value)
        cls._ensure(text in allowed, f"Configuration value '{key}' must be one of {sorted(allowed)}.")
        return text

    @classmethod
    def _as_log_level(cls, value: Any, key: str) -> str:
        level = str(value).upper()
        cls._ensure(level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}, f"Invalid {key} value.")
        return level

    @classmethod
    def _as_bool(cls, value: Any, key: str) -> bool:
        if not isinstance(value, bool):
            raise ConfigError(f"Configuration value '{key}' must be a boolean.")
        return value

    @classmethod
    def _as_int(
        cls,
        value: Any,
        key: str,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigError(f"Configuration value '{key}' must be an integer.")
        if minimum is not None and value < minimum:
            raise ConfigError(f"Configuration value '{key}' must be >= {minimum}.")
        if maximum is not None and value > maximum:
            raise ConfigError(f"Configuration value '{key}' must be <= {maximum}.")
        return value

    @classmethod
    def _as_float(
        cls,
        value: Any,
        key: str,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ConfigError(f"Configuration value '{key}' must be numeric.")
        result = float(value)
        if minimum is not None and result < minimum:
            raise ConfigError(f"Configuration value '{key}' must be >= {minimum}.")
        if maximum is not None and result > maximum:
            raise ConfigError(f"Configuration value '{key}' must be <= {maximum}.")
        return result

    @classmethod
    def _as_str_list(cls, value: Any, key: str) -> list[str]:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ConfigError(f"Configuration value '{key}' must be a list of strings.")
        return value
