"""Feature-space red-team for FileGuard.

FileGuard scores 54 PE header numbers, never the file's bytes. An attacker
cannot change the malicious code without changing what it does, but can change
plenty of the *description* of the file around it. This module models those
edits and asks: does detection survive?

Threat model. The attacker knows the feature set and can query the model (a
black box that returns a score). They can build or relink the binary, or wrap it
with a resource/section editor. They cannot make the malicious code smaller or
change its architecture. Edits are modelled with the constraints a real PE has:

  * header bytes -- copy plausible values from a real benign file
  * imports and sections can only be ADDED (counts never decrease); the derived
    section/resource statistics are recomputed exactly from what is added
  * resource statistics combine as a weighted mean / min / max of old + new

Every one of the 54 features is assigned below to exactly one class, so the
judgement calls are visible and testable rather than buried in code.

Two things this deliberately does NOT model, so results are an upper bound on an
attacker's *ease* only where noted in the report: (1) whether every edit combination
yields a binary that still runs -- checked for header edits on real benign files in
overlay_demo(), not for every tier; (2) appended "overlay" bytes, which change none
of the 54 features (there is no file-size or whole-file-entropy feature).
"""
import numpy as np
import pandas as pd

# -- which features an attacker can move, and how hard it is -----------------------------
HEADER_BYTES = [  # trivial: a few header bytes, no functional effect
    "MajorLinkerVersion", "MinorLinkerVersion", "MajorOperatingSystemVersion", "MinorOperatingSystemVersion",
    "MajorImageVersion", "MinorImageVersion", "MajorSubsystemVersion", "MinorSubsystemVersion",
    "CheckSum", "LoaderFlags", "SizeOfStackReserve", "SizeOfStackCommit", "SizeOfHeapReserve", "SizeOfHeapCommit",
]
BASE_FLAGS = ["ImageBase", "DllCharacteristics", "Subsystem"]  # moderate: linker option (/BASE, /SUBSYSTEM) or a wrapper
RESOURCES = [  # moderate: a resource editor can embed icon/manifest/version resources
    "ResourcesNb", "ResourcesMeanEntropy", "ResourcesMinEntropy", "ResourcesMaxEntropy",
    "ResourcesMeanSize", "ResourcesMinSize", "ResourcesMaxSize", "VersionInformationSize",
]
IMPORTS = ["ImportsNbDLL", "ImportsNb"]  # moderate, add-only: unused imports appended to the import table
SECTIONS = [  # moderate, add-only: extra sections (padding/data) appended
    "SectionsNb", "SectionsMeanEntropy", "SectionsMinEntropy", "SectionsMaxEntropy",
    "SectionsMeanRawsize", "SectionsMinRawsize", "SectionMaxRawsize",
    "SectionsMeanVirtualsize", "SectionsMinVirtualsize", "SectionMaxVirtualsize",
    "SizeOfImage", "SizeOfInitializedData",
]
NOT_MODELLED = [  # hard: tied to the code, the toolchain or the CPU architecture
    "Machine", "SizeOfOptionalHeader", "Characteristics", "SizeOfCode", "SizeOfUninitializedData",
    "AddressOfEntryPoint", "BaseOfCode", "BaseOfData", "SectionAlignment", "FileAlignment", "SizeOfHeaders",
    "NumberOfRvaAndSizes", "ImportsNbOrdinal", "ExportNb", "LoadConfigurationSize",
]
# Adding sections can only RAISE a maximum, never lower it (that needs different packing), so an
# attacker cannot use these to hide packed code -- they are not counted as attacker-controllable.
RAISE_ONLY = ["SectionsMaxEntropy", "SectionMaxRawsize", "SectionMaxVirtualsize"]
GROUPS = {"header_bytes": HEADER_BYTES, "base_flags": BASE_FLAGS, "resources": RESOURCES,
          "imports": IMPORTS, "sections": SECTIONS}
CONTROL_CLASS = {**{f: "trivial" for f in HEADER_BYTES},
                 **{f: "moderate" for f in BASE_FLAGS + RESOURCES + IMPORTS + SECTIONS},
                 **{f: "hard (not modelled)" for f in NOT_MODELLED},
                 **{f: "hard (can only be raised)" for f in RAISE_ONLY}}

# cumulative attacker capability, cheapest edits first
TIERS = [
    ("T1 header bytes", ["header_bytes"]),
    ("T2 + ImageBase/flags", ["header_bytes", "base_flags"]),
    ("T3 + resources", ["header_bytes", "base_flags", "resources"]),
    ("T4 + imports", ["header_bytes", "base_flags", "resources", "imports"]),
    ("T5 + sections", ["header_bytes", "base_flags", "resources", "imports", "sections"]),
]
# each edit group on its own, to see which one carries the evasion
SOLO = [(f"only {g}", [g]) for g in GROUPS]


def _arr(df, col):
    return df[col].to_numpy(dtype=float)


def _combine(n0, v0, n1, v1, how):
    """Statistic of (old items + added items). An absent group is 0, as the extractor writes it."""
    both = (n0 > 0) & (n1 > 0)
    if how == "mean":
        tot = np.maximum(n0 + n1, 1)
        return np.where(n0 + n1 > 0, (n0 * v0 + n1 * v1) / tot, 0.0)
    pick = np.minimum(v0, v1) if how == "min" else np.maximum(v0, v1)
    return np.where(both, pick, np.where(n0 > 0, v0, np.where(n1 > 0, v1, 0.0)))


def perturb(mal: pd.DataFrame, donor: pd.DataFrame, groups, k_sections=0) -> pd.DataFrame:
    """Apply the chosen edit groups to `mal`, borrowing plausible values from the aligned `donor` rows."""
    out = mal.copy()
    if "header_bytes" in groups:
        out[HEADER_BYTES] = donor[HEADER_BYTES].to_numpy()
    if "base_flags" in groups:
        out[BASE_FLAGS] = donor[BASE_FLAGS].to_numpy()
    if "resources" in groups:
        n0, n1 = _arr(mal, "ResourcesNb"), _arr(donor, "ResourcesNb")
        out["ResourcesNb"] = n0 + n1
        for stat in ("Entropy", "Size"):
            for kind, agg in [("Mean", "mean"), ("Min", "min"), ("Max", "max")]:
                col = f"Resources{kind}{stat}"
                out[col] = _combine(n0, _arr(mal, col), n1, _arr(donor, col), agg)
        out["VersionInformationSize"] = np.maximum(_arr(mal, "VersionInformationSize"), _arr(donor, "VersionInformationSize"))
    if "imports" in groups:
        out["ImportsNb"] = np.maximum(_arr(mal, "ImportsNb"), _arr(donor, "ImportsNb"))
        out["ImportsNbDLL"] = np.maximum(_arr(mal, "ImportsNbDLL"), _arr(donor, "ImportsNbDLL"))
    if "sections" in groups and k_sections > 0:
        k = float(k_sections)
        n0 = _arr(mal, "SectionsNb")
        n = n0 + k
        e_a, r_a, v_a = _arr(donor, "SectionsMeanEntropy"), _arr(donor, "SectionsMeanRawsize"), _arr(donor, "SectionsMeanVirtualsize")
        out["SectionsNb"] = n
        for name, add in [("Entropy", e_a), ("Rawsize", r_a), ("Virtualsize", v_a)]:
            mean_c, min_c = f"SectionsMean{name}", f"SectionsMin{name}"
            max_c = "SectionMaxRawsize" if name == "Rawsize" else "SectionMaxVirtualsize" if name == "Virtualsize" else "SectionsMaxEntropy"
            out[mean_c] = (n0 * _arr(mal, mean_c) + k * add) / n
            out[min_c] = np.minimum(_arr(mal, min_c), add)
            out[max_c] = np.maximum(_arr(mal, max_c), add)
        out["SizeOfImage"] = _arr(mal, "SizeOfImage") + k * v_a
        out["SizeOfInitializedData"] = _arr(mal, "SizeOfInitializedData") + k * r_a
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(float(max(0, c - h)), 4), round(float(min(1, c + h)), 4)]


def _rate(k, n):
    return {"detected": int(k), "n": int(n), "rate": round(k / n, 4) if n else None, "ci95": wilson(k, n)}


def evaluate(model, cols, thr, mal, donors, k_donors=25, section_ks=(1, 2, 4, 8), fixed_k=4, seed=0):
    """Detection rate under each attacker capability.

    adaptive     the attacker tries `k_donors` benign donor files (and every section
                 count in `section_ks`) per malware sample and keeps the best -- a black-box
                 query attacker. Counts a sample as detected only if EVERY variant is caught.
    single_shot  one random donor, one fixed edit, no querying: a naive attacker. Averaged
                 over all donors drawn.
    Malware and donors are matched by CPU architecture (Machine).
    """
    rng = np.random.default_rng(seed)
    mal = mal.reset_index(drop=True)
    donors = donors.reset_index(drop=True)
    variants = TIERS + SOLO
    adaptive = {name: [] for name, _ in variants}
    single = {name: [] for name, _ in variants}
    single_feat = {f: [] for f in HEADER_BYTES + BASE_FLAGS}
    clean_scores = model.predict_proba(mal[cols])[:, 1]

    for machine, sub in mal.groupby("Machine"):
        pool = donors[donors.Machine == machine]
        if pool.empty:
            raise ValueError(f"no benign donors with Machine={machine:#x}")
        n = len(sub)
        idx = rng.integers(0, len(pool), size=(n, k_donors))
        rep = sub.loc[np.repeat(sub.index.to_numpy(), k_donors)].reset_index(drop=True)
        don = pool.iloc[idx.ravel()].reset_index(drop=True)

        for name, groups in variants:
            ks = section_ks if "sections" in groups else (0,)
            S = np.stack([model.predict_proba(perturb(rep, don, groups, k)[cols])[:, 1].reshape(n, k_donors) for k in ks])
            adaptive[name].append(S.min(axis=(0, 2)))
            fixed = ks.index(fixed_k) if fixed_k in ks else 0
            single[name].append((S[fixed] >= thr).reshape(-1))
        for f in single_feat:
            X = rep.copy()
            X[f] = don[f].to_numpy()
            s = model.predict_proba(X[cols])[:, 1].reshape(n, k_donors).min(axis=1)
            single_feat[f].append(s)

    n_total = len(mal)
    res = {"clean": _rate(int((clean_scores >= thr).sum()), n_total), "tiers": [], "solo": [], "single_feature": {}}
    for bucket, names in [("tiers", [t for t, _ in TIERS]), ("solo", [s for s, _ in SOLO])]:
        for name in names:
            a = np.concatenate(adaptive[name])
            ss = np.concatenate(single[name])
            res[bucket].append({
                "name": name,
                "adaptive": _rate(int((a >= thr).sum()), n_total),
                "single_shot_detection_rate": round(float(ss.mean()), 4),
            })
    for f, parts in single_feat.items():
        s = np.concatenate(parts)
        evaded = int((s < thr).sum())
        if evaded:
            res["single_feature"][f] = {"class": CONTROL_CLASS[f], "samples_evaded": evaded, "of": n_total}
    return res


def sensitivity(model, cols, thr, mal, pools, efforts=(1, 5, 25, 100), seed=1):
    """Adaptive detection under the two cheapest tiers, by donor pool and by how many donors the attacker tries.

    Guards against the headline depending on one lucky donor pool or one attacker budget.
    """
    out = {}
    for name, pool in pools.items():
        out[name] = {}
        for k in efforts:
            r = evaluate(model, cols, thr, mal, pool, k_donors=k, seed=seed)
            out[name][f"K={k}"] = {"T1_header_bytes_detected": r["tiers"][0]["adaptive"]["detected"],
                                   "T2_plus_imagebase_flags_detected": r["tiers"][1]["adaptive"]["detected"],
                                   "of": len(mal)}
    return out


def evidence_by_control_class(shap_matrix, cols):
    """Share of the model's toward-malicious SHAP evidence that sits on features of each control class."""
    pos = np.clip(np.asarray(shap_matrix, dtype=float), 0, None).mean(axis=0)
    total = float(pos.sum()) or 1.0
    by = {}
    for f, v in zip(cols, pos):
        by[CONTROL_CLASS[f]] = by.get(CONTROL_CLASS[f], 0.0) + float(v)
    top = sorted(zip(cols, pos), key=lambda kv: -kv[1])[:8]
    return {"share_of_malicious_evidence": {c: round(v / total, 4) for c, v in sorted(by.items(), key=lambda kv: -kv[1])},
            "top_features": [{"feature": f, "share": round(float(v) / total, 4), "class": CONTROL_CLASS[f]} for f, v in top]}
