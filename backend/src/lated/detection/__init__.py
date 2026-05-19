# =============================================================================
# lated.detection — Detection Core (AI)
# =============================================================================
#
# ROLE IN ARCHITECTURE
# --------------------
# Central intelligence layer. Contains THREE STRICTLY SEPARATED submodules:
#
#   tgnn/    — Temporal Graph Neural Network LM detector
#              * specialized for lateral movement ONLY
#              * pretrained self-supervised, fine-tuned on LANL redteam labels
#
#   recon/   — Heuristic / behavioral reconnaissance detector
#              * COMPLETELY INDEPENDENT from tgnn/
#              * no shared state, no shared imports
#
#   fusion/  — Suspicion fusion engine
#              * combines LM + recon + history into a final SuspicionScore
#              * lightweight, explainable, configurable weights
#
# CYBERSECURITY REASONING
# -----------------------
# The two detectors live in separate code paths on purpose:
#   - a poisoned / failing TGNN MUST NOT silence recon detection,
#   - a heuristic blind spot MUST NOT silence TGNN.
# Their scores fuse only at the very end, in fusion/.
# =============================================================================
