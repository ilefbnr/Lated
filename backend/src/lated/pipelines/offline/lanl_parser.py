# =============================================================================
# lated.pipelines.offline.lanl_parser — LANL dataset parser
# =============================================================================
#
# PURPOSE
# -------
# Parses the Los Alamos National Laboratory cyber security dataset:
#   - flows.txt   : per-flow records (time, duration, src/dst, proto, ports, bytes)
#   - redteam.txt : ground-truth redteam authentication events
#
# Converts them into CanonicalFlow-shaped records compatible with the rest
# of the pipeline (graph builder, feature engineering).
#
# INPUTS  : path to LANL data directory
# OUTPUTS : iterators of CanonicalFlow + RedteamEvent objects
#
# INTERACTIONS
# ------------
#   - dataset_builder  : consumer.
#   - weak_labeler     : consumer (uses redteam events).
#
# CYBERSECURITY REASONING
# -----------------------
# LANL is the canonical academic benchmark for LM detection — using it lets
# us compare against published baselines. The parser is intentionally
# tolerant of malformed lines (skip + log) since the dataset is large and
# occasionally noisy.
# =============================================================================

from __future__ import annotations


class LANLParser:
    """Iterators over LANL flows and redteam events."""

    def __init__(self, data_dir: str):
        ...

    def iter_flows(self):
        raise NotImplementedError("Architecture skeleton.")

    def iter_redteam(self):
        raise NotImplementedError("Architecture skeleton.")
