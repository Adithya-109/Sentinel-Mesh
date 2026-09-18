# SentinelMesh ML -- convenience targets. Run from ml/.
ifeq ($(OS),Windows_NT)
PY ?= .venv/Scripts/python
else
PY ?= .venv/bin/python
endif

.PHONY: field-model test-field-model energygate test-energygate energygate-synthetic energygate-ablation test-feature-order test-fileguard redteam-fileguard

# Train the real on-device field model from data/traces/*.jsonl (Trace
# rows per contracts/CONTRACT.md) and export it to export/field_model.h.
# The single command phase 2 needs once real recordings exist.
field-model:
	$(PY) train_field_model.py

# Proves the pipeline (train -> C export -> gcc compile -> parity check)
# against synthetic SYNTH_-labelled data. Never a substitute for
# field-model -- see tests/test_field_model_pipeline.py's docstring.
test-field-model:
	$(PY) tests/test_field_model_pipeline.py

# Phase 3 (brief v4): train EnergyGate from data/traces/*.jsonl and export
# it to export/energygate.h. Same data as field-model, different target
# (spend/challenge/drop probability, not attack class).
energygate:
	$(PY) train_energygate.py

# Stopgap until real traces exist: train on SIMULATED traces, parity-check the C
# export, and copy it into firmware/ as energygate_model.h (SIMULATED banner
# inside). Replace by running `make energygate` once data/traces/ has real rows.
energygate-synthetic:
	$(PY) train_energygate_synthetic.py --firmware

# Guards against the firmware and the trainers disagreeing on which feature is
# at which index (the parity tests can't see that: they feed C and Python the
# same vector). Reads the order documented in firmware/.../field_model.h and
# energygate.h and compares it to FEATURE_ORDER.
test-feature-order:
	$(PY) tests/test_feature_order_matches_firmware.py

# Which of EnergyGate's 8 signals does the tree need? Retrains on feature
# subsets over the same SIMULATED data; writes
# reports/energygate_synthetic_ablation.json only.
energygate-ablation:
	$(PY) experiments/energygate_ablation.py

# Proves the EnergyGate pipeline against synthetic SYNTH_-labelled data.
# Never a substitute for energygate -- see
# tests/test_energygate_pipeline.py's docstring.
test-energygate:
	$(PY) tests/test_energygate_pipeline.py

# FileGuard explanations (SHAP additivity, parity with the shap library if
# installed, verdict-directed ranking) and the red-team library's physical-
# consistency invariants. Uses the committed model + demo rows; no dataset.
test-fileguard:
	$(PY) tests/test_fileguard_shap.py
	$(PY) tests/test_fileguard_redteam.py

# Red-team FileGuard in feature space (writes reports/fileguard_redteam.json).
# Add DATA=path/to/security for the full held-out test set instead of the 20 demo rows.
redteam-fileguard:
	$(PY) redteam_fileguard.py $(if $(DATA),--data "$(DATA)",)
