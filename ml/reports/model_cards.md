# Model cards

Honest numbers and known limits for each model, in the same spirit as
brief section 12's Q&A prep. Exact metrics are in `reports/metrics.json`
(regenerate with `python build_all.py --data ...`); this file explains
what they mean and where they can mislead.

## MailGuard (email)

**What it is.** TF-IDF (1-2 word phrases, numbers/URLs/emails replaced
with placeholder tokens) + logistic regression, adversarially trained on
padded copies of malicious mail. Threshold tuned on held-out data for
<=2% false alarms.

**Data.** `CEAS_08`, `Enron`, `Ling`, `Nigerian_Fraud`, `SpamAssasin`
only -- `phishing_email.csv` and `emails.csv` are excluded because they
duplicate these five (confirmed by `audit_and_baselines.py`: 99.8% of
`emails.csv` is inside `Enron`). 75,631 deduplicated emails after dropping
exact duplicates.

**Honest metrics** (`email_random_split_final` vs
`email_leave_one_corpus_out` in `reports/metrics.json`):

| | accuracy | legit false alarm |
|---|---|---|
| Random 80/20 split | ~98% | ~1.8% |
| Held out: CEAS_08 | 92.0% | 6.9% |
| Held out: Enron | 87.6% | 9.4% |
| Held out: Ling | 94.5% | 4.4% |
| Held out: SpamAssasin | 93.9% | 6.2% |
| Held out: Nigerian_Fraud | recall 99.2%* | -- |

\* Nigerian_Fraud is 100% malicious, so it has no legit-mail rate to report.

The random split is the number that looks good; leave-one-corpus-out is
the one to quote, because it's the only one that tests generalization to
mail the model's vocabulary has never seen.

**Known limits.**
- **The emails are old.** Enron is 2000-2002 internal corporate mail;
  CEAS_08 is a 2008 spam challenge. None of this reflects 2026 phishing
  style, brand impersonation, or QR-code/attachment-based lures. The
  brief's suggested fix -- a small "2026 reality check" set of 20-30
  recent phishing emails from team inboxes -- has not been built yet.
- **The label is mostly "spam," not narrowly "phishing."** All five
  corpora collapse spam, scams, and phishing into one `label=1`. A model
  tuned on this may not weight credential-phishing cues the same way a
  phishing-specific dataset would.
- **The 2% false-alarm target does not transfer to a new email source.**
  With the threshold tuned the production way (<=2% false alarms on
  in-distribution validation data) and applied to a held-out corpus, false
  alarms are 9.2% (CEAS_08), 25.9% (Enron), 7.5% (Ling), 12.3%
  (SpamAssasin). Even with the threshold tuned on the new corpus itself,
  recall at 2% false alarms is only 67-87%
  (`reports/experiments.json`, `mailguard_loco_tuned_threshold`). The 1.8%
  in the table above holds for mail like the training mail only.
- **Red-team gap (padding).** Padding a malicious email with ordinary text
  dropped recall from 99.3% to 15.8% (append-only, at 0.5). Adversarial
  training now covers three layouts (append, sandwich before+after,
  interleaved) and recovers it to 88.6% on the append attack, 91.6% on
  sandwich, 79.7% on interleaved. On layouts it was **not** trained on:
  91.3% (6 chunks appended), 90.0% (6 prepended), **72.3% (interleaved into
  8 pieces)**. The un-hardened baseline scores 0.1-14% on all of these.
  Interleaving is the open gap. Caveats: the padding text is drawn from the
  same legit pool used in training, so this does not test unfamiliar padding
  content; and the price is a small drop in clean recall at the tuned
  threshold (98.7% -> 98.1% at the same 1.8% false alarms, AUC 0.9987 ->
  0.9974).
- **Character n-grams did not help and were not adopted.** A word+char
  model looked more robust (91% on the shipped append attack) only because
  its char branch read just the first 1,000 characters, so trailing padding
  never reached it; prepended padding collapsed it to 11%. The gain came
  from training on more padding layouts, not from the extra features (a
  word-only control trained the same way matched it). See
  `mailguard_char_ngrams_and_stronger_padding` in `reports/experiments.json`.
- **Per-corpus class imbalance varies a lot** (Nigerian_Fraud is 100%
  malicious; CEAS_08 is ~56%; SpamAssasin ~30%), which is part of why
  leave-one-corpus-out numbers swing as much as they do.

**Explanations.** Top-3 TF-IDF tokens by `|coefficient x tfidf weight|`,
converted to plain English by `sentinel_ml/reasons.py` (placeholder
tokens and a curated phishing-cue-word list; anything else falls back to
the raw word).

## FileGuard (file)

**What it is.** LightGBM on the 54 PE header features from `malware.csv`,
debiased with benign third-party Windows binaries (never the team's own
Program Files files -- see "Data" below) at sample weight 20. Threshold
tuned on held-out data for <=0.1% false alarms.

**Data.** `malware.csv`, 138,047 rows (~70% malicious), `|`-separated.
`Name` and `md5` are dropped from the features (`Name` leaks the label --
malware entries are `VirusShare*` 100% of the time). 35,856 rows
(~26%) share an identical feature vector with another row, so splits are
grouped by feature-vector hash, never by row, or the same sample can leak
across train/test.

**Honest metrics** (`malware_group_split_final` in `reports/metrics.json`):
group-split accuracy 99.2%, **detection at a 0.1% false-alarm rate
98.94%** (matches the brief's reported 98.9%) -- report this rate, not
plain accuracy, since accuracy alone hides how conservative the
threshold is.

**The third-party bias, measured and fixed.** The dataset's "benign"
class all comes from one Windows install, so the dataset-only model
flags real third-party software it's never seen as malware at a high
rate: **40.5%** of 1,566 benign binaries pulled from 198 real pip/npm
Windows packages, held out by whole package (mean of 5 random
package-level splits; `thirdparty_experiment_mean_of_5.dataset_only` in
`reports/metrics.json`). Adding those same binaries to training,
upweighted (sample weight 20), cuts that to **0.44%**
(`plus_thirdparty_benign`), with malware detection essentially unchanged
(99.65% -> 99.67%). See `reports/charts/malware_thirdparty.png`.

**Known limits.**
- **64-bit blind spot.** Only 68 of 96,724 malicious samples are 64-bit
  (`malware_x64_files_by_class` in metrics.json); the model has almost no
  exposure to 64-bit malware and should be assumed weak there. Fixing
  this needs external 64-bit samples in the same 54-feature format, which
  depends on what the event rules allow.
- **Re-implemented feature extractor.** `pe_features.py` (used to score
  real files live, and to build the benign third-party set) is a
  from-scratch re-implementation using `pefile`, not the original
  extractor behind `malware.csv`. Values should line up, but small
  differences in entropy/resource calculations between implementations
  are possible and untested against the original extractor.
- **The benign third-party set, while now 1,566 files across 198
  packages (pip `win_amd64` + `win32` wheels for ~107 popular packages,
  plus npm), is still narrow.** It's built from pip/npm packages and
  Windows system binaries, not the team's own Program Files -- see
  `ml/README.md`'s benign-set section. The false-alarm rate on truly
  novel legitimate software in the wild may differ from what the
  held-out-package test estimates.
- **`ImageBase` dominates the gain, but the model does not depend on it.**
  It accounts for 74% of LightGBM's gain and alone gives ~0.94 AUC, a sign
  the dataset's classes differ in incidental ways (how they were
  compiled/linked). We retrained without it, and without the top-5 gain
  columns: detection at 0.1% false alarms is essentially unchanged
  (98.5% -> 98.1%, 5 seeds). Other columns carry the same signal, so this
  is not a single fixable shortcut. Still worth stress-testing against
  adversarially-built binaries.
- **Unseen malware families are much harder than the headline number.**
  The shipped split groups only *identical* feature vectors, so
  near-duplicates (same family, rebuilt) can sit on both sides. Holding out
  whole clusters of similar files (k-means, k=300, 5 seeds) drops
  detection at 0.1% false alarms from 98.5% +/- 0.3% to **88.1% +/- 7.2%**
  (range 74.6-95.9%), while AUC stays ~0.999. Quote the 88% for
  "malware unlike anything in training". Clusters are a proxy for families,
  not real family labels (`fileguard_cluster_split`).
- **The in-sample third-party number.** `thirdparty_false_alarm: 0.0` in
  `malware_group_split_final` is measured on binaries the final model
  trained on. The honest figure is the held-out-package one: ~0.2% at the
  tuned threshold (3 package splits, `fileguard_shortcut_ablation`).

**Explanations.** Top-3 features by LightGBM `pred_contrib`, converted to
plain English by `sentinel_ml/reasons.py` (all 54 feature names are
mapped).

## FieldGuard (phase 2, on-device)

Not trained on real data yet -- the provided dataset has no radio/IoT
traffic. `sentinel_ml/field_model.py` trains a small (max_depth ~6)
decision tree on recorded `Trace` rows and exports it to C
(`export/field_model.h`, `int classify_window(const float* f)`) once
`data/traces/*.jsonl` exists (`make field-model`). The pipeline itself
(train -> C export -> gcc compile -> parity check) is verified against
synthetic data in `ml/tests/` -- **that synthetic accuracy is not a real
result** and is never written to this file or to `reports/metrics.json`.

## EnergyGate (phase 3, on-device) -- SIMULATED, not a result

**What it is.** A small decision tree (depth 5, 15 leaves) over 8 cheap signals
(`hs_per_s, hs_fail, rssi_mean, rssi_var, loss_pct, dup_pct, frag_complete_pct,
battery_pct`) that outputs the probability a sender is real, exported to C and
compiled into field-1's firmware. The spend/challenge/drop policy, joule budget
and cookie live in firmware (`gate_policy.h`), not here.

**Data: simulated.** No real traces exist yet (`console/data/traces/` is empty),
so this was trained on `tests/generate_synthetic_traces.py --hard`: 30 sessions,
3,600 windows, 63% "real". Hard mode makes the classes overlap (attack windows
are interpolated toward normal by Beta(2, 1.2), so many are only weakly
abnormal), adds multiplicative measurement noise and 3% label noise (the
console's `LABEL` is set by a human, so windows straddling a switch are
mislabelled). Those settings were fixed in advance, not tuned to a result. It
is still our own assumptions about attacks, so **nothing below is a measured
result**. The header carries a SIMULATED banner and every JSON/chart it writes
is flagged SIMULATED.

**Held-out evaluation (leave-one-session-out, on simulated data).**

| depth | AUC | log loss | Brier | calibration error (ECE) | accuracy @0.5 |
|---|---|---|---|---|---|
| 3 | 0.934 | 0.180 | 0.044 | 0.006 | 95.1% |
| 4 | 0.941 | 0.175 | 0.042 | 0.008 | 95.0% |
| **5 (shipped)** | 0.947 | 0.171 | 0.040 | 0.010 | 95.5% |

Depth was chosen by held-out log loss, capped at 5 to keep the on-device claim
(loss was still falling at 5). Scores are graded, not binary (leaf
probabilities range 0.00-1.00 with several mid values) and well calibrated on
simulated data. That calibration is a property of the generator, not evidence
it holds on real traffic.

**Operating-point sweep** (`reports/energygate_synthetic_sweep.json`,
`reports/charts/energygate_sweep_SIMULATED.png`). With the firmware's default
thresholds (spend >= 0.7, challenge >= 0.4), on held-out simulated windows:
98.7% of legitimate senders connect (1.7% delayed by a challenge) and the
attacker makes the node spend 7.7% of the energy it would undefended; 2.1% of
windows fall in the challenge band. It assumes a cookie challenge costs 5% of a
handshake (ASSUMED, not measured), that legitimate senders pass it and attackers
do not, and it is per-window, not a time simulation. It shows the *shape* of the
trade-off the mechanism offers.

**What it uses.** `hs_fail` (56% of importance) and `dup_pct` (39%) do almost
all the work; `loss_pct`, `hs_per_s`, `rssi_mean` carry a little; `battery_pct`,
`rssi_var` and `frag_complete_pct` are unused. `battery_pct` being unused is the
sanity check that mattered: it is a per-session constant in the generator, and
with few sessions a tree can latch onto it as a stand-in for session identity.

**Verified.** The C export matches sklearn to 2e-7 on 500 boundary-stressing
rows (gcc parity check). Compiled with the ESP32 (Xtensa) toolchain the scoring
code is 423 bytes of flash and no static RAM (the rule-based stand-in is 307).
Inference *energy* is not estimated here; the INA219 rig has to measure it.
Firmware native tests pass with the model compiled in (288/288) and without it
(290/290).

**Known limits.**
- **Vantage-point caveat.** Training windows are recorded at the gateway, but the
  model scores at field-1 (see `contracts/CHANGELOG.md`). Irrelevant for
  simulated data, worth watching once real traces exist.
- **"Time since this sender's last attempt"** (a brief signal) has no Trace field;
  `hs_per_s` stands in for it and is not equivalent.
- **Weak signal plus failures is ambiguous by design.** A very weak link with many
  failed handshakes scores ~0.35 (undecided): a real weak link and an attacker
  look alike there, and that is what the challenge band is for.
- The hard-mode overlap is our guess at how messy real data is. Real recordings
  may be easier or much harder; only they can say.
