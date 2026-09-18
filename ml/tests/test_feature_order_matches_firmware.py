"""Guards the one silent failure the parity tests cannot see: the firmware and
the Python trainer disagreeing about which feature sits at which index.

A trained tree only knows "f[3] <= 41.2". If the firmware fills f[3] with a
different signal than the trainer saw at index 3, the C code compiles, runs, and
gives confident wrong answers -- and test_*_pipeline.py still passes, because it
feeds Python and C the *same* vector. This has already bitten once (the first
EnergyGate stand-in used its own order). So this test reads the order the
firmware documents in its headers and compares it, index for index, to
FEATURE_ORDER in sentinel_ml/.

    field_model  <-> firmware/.../sentinel_proto/field_model.h   (FIELD_MODEL_NUM_FEATURES)
    energygate   <-> firmware/.../sentinel_proto/energygate.h    (ENERGYGATE_NUM_FEATURES)

Run either way:
    python tests/test_feature_order_matches_firmware.py
    python -m pytest tests/test_feature_order_matches_firmware.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from sentinel_ml import energygate, field_model  # noqa: E402

PROTO = os.path.join(HERE, "..", "..", "firmware", "lib", "sentinel_proto", "include", "sentinel_proto")

# "//   f[3] = rssi_var   dBm^2"  ->  (3, "rssi_var")
_DOC_LINE = re.compile(r"^\s*//\s+f\[(\d+)\]\s*=\s*(\w+)")


def _read(name):
    with open(os.path.join(PROTO, name), encoding="utf-8") as f:
        return f.read()


def documented_order(header_text):
    """The `f[i] = name` lines from the header's comment, as a list ordered by i."""
    found = {}
    for line in header_text.splitlines():
        m = _DOC_LINE.match(line)
        if m:
            idx, name = int(m.group(1)), m.group(2)
            assert idx not in found, f"index f[{idx}] documented twice"
            found[idx] = name
    assert found, "no `f[i] = name` lines found -- did the header's comment format change?"
    assert sorted(found) == list(range(len(found))), f"documented indices are not 0..n-1: {sorted(found)}"
    return [found[i] for i in range(len(found))]


def declared_count(header_text, constant):
    m = re.search(rf"constexpr\s+int\s+{constant}\s*=\s*(\d+)\s*;", header_text)
    assert m, f"{constant} not found"
    return int(m.group(1))


def test_field_model_order_matches_firmware():
    text = _read("field_model.h")
    order = documented_order(text)
    assert order == field_model.FEATURE_ORDER, (
        f"firmware field_model.h documents {order}\n     but sentinel_ml/field_model.py trains on {field_model.FEATURE_ORDER}")
    assert declared_count(text, "FIELD_MODEL_NUM_FEATURES") == len(field_model.FEATURE_ORDER)


def test_energygate_order_matches_firmware():
    text = _read("energygate.h")
    order = documented_order(text)
    assert order == energygate.FEATURE_ORDER, (
        f"firmware energygate.h documents {order}\n     but sentinel_ml/energygate.py trains on {energygate.FEATURE_ORDER}")
    assert declared_count(text, "ENERGYGATE_NUM_FEATURES") == len(energygate.FEATURE_ORDER)


if __name__ == "__main__":
    test_field_model_order_matches_firmware()
    print(f"PASS: field_model.FEATURE_ORDER == firmware field_model.h ({len(field_model.FEATURE_ORDER)} features)")
    test_energygate_order_matches_firmware()
    print(f"PASS: energygate.FEATURE_ORDER == firmware energygate.h ({len(energygate.FEATURE_ORDER)} features)")
