# SentinelMesh ML -- convenience targets. Run from ml/.
ifeq ($(OS),Windows_NT)
PY ?= .venv/Scripts/python
else
PY ?= .venv/bin/python
endif

.PHONY: field-model test-field-model

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
