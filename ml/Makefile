# SentinelMesh ML -- convenience targets. Run from ml/.
ifeq ($(OS),Windows_NT)
PY ?= .venv/Scripts/python
else
PY ?= .venv/bin/python
endif

.PHONY: field-model test-field-model energygate test-energygate

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

# Proves the EnergyGate pipeline against synthetic SYNTH_-labelled data.
# Never a substitute for energygate -- see
# tests/test_energygate_pipeline.py's docstring.
test-energygate:
	$(PY) tests/test_energygate_pipeline.py
