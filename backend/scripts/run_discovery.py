from pathlib import Path
from lated.common.config_manager import ConfigManager
from lated.discovery.discovery_service import DiscoveryService

config = ConfigManager.load(
    settings_path="config/settings.yaml",
    thresholds_path="config/detection_thresholds.yaml",
).discovery
service = DiscoveryService(
    config=config,
    source_path=Path("data/discovery_input/observations.json"),
    baseline_path=Path("data/baseline/latest.json"),
    registry_path=Path("data/discovery/host_registry.json"),
    env="development",                # secret HMAC dev auto-fourni
)
baseline = service.run()
print(f"Hosts: {len(baseline.nodes)}  Edges: {len(baseline.edges)}")
