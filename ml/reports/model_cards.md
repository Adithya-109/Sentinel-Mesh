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
- **Red-team gap.** Padding a malicious email with ordinary text dropped
  recall from 99.3% to 16.1%; adversarial training recovered it to 79.4%,
  at a small false-alarm cost (1.0% -> 1.3%). The remaining ~20-point gap
  is real evasion headroom, not fully closed.
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
- **`ImageBase` dominates.** It alone accounts for the large majority of
  the model's gain (`malware_top_gain_share`, `ImageBase_single_feature_auc`
  ~0.94) -- a single-feature shortcut this strong is a sign the dataset's
  malicious/benign split correlates with something incidental (e.g. how
  the two classes were compiled/linked), not necessarily with malicious
  *behavior*. Worth stress-testing before trusting it against
  adversarially-built binaries.
- **Red-team gap (measured in feature space, 2026-09-18).** FileGuard scores
  54 header numbers, so an attacker who never touches the malicious code can
  still edit most of them (`sentinel_ml/redteam.py` classifies every feature;
  results in `reports/fileguard_redteam.json`, chart
  `charts/fileguard_red_team.png`). On the 20 held-out demo malware rows --
  **a probe, not a full-test-set result** -- detection fell from 20/20 to
  **4/20** (adaptive attacker, 95% CI 8-42%; 48% for a naive one) after copying
  14 header bytes (linker/OS/image/subsystem versions, checksum, stack/heap
  sizes) from real benign files, and to **0/20** (CI 0-16%) after also changing
  ImageBase, DllCharacteristics and Subsystem. It holds across donor pools and
  attacker effort. About 76% of the model's evidence for "malicious" sits on
  features an attacker can change, ImageBase alone 32% -- the shortcut the
  bullet above warned about, now measured. Appended junk ("inflate size, dilute
  entropy") does nothing: there is no file-size or whole-file-entropy feature.
  Caveats: feature space only (header edits were shown to apply on a real
  benign file, not built into working malware), and rebasing a pre-built
  no-relocation binary needs a relinker or wrapper. **Not yet fixed:**
  adversarial retraining needs the malware dataset, which is not in the repo.
- **Real-world false alarms on unseen benign software.** On 3,056 real
  Windows and installed-app binaries from one machine, none in training
  (`reports/fileguard_realworld_fp.json`), the production model flags 6 =
  **0.20%** (CI 0.09-0.43%). That headline is flattered by Windows system files
  (0 of 1,898), which resemble the dataset's own benign class. Installed apps
  only: **0.52%** (6/1,158, CI 0.24-1.13%); 32-bit apps **1.10%** (4/364, CI
  0.43-2.79%). Consistent with the 0.44% held-out-package figure above. The
  files are assumed benign, not verified, and come from one machine.

**Explanations.** Exact SHAP values (LightGBM's `pred_contrib` is TreeSHAP;
`tests/test_fileguard_shap.py` checks additivity and, where the `shap` library
is installed, parity with it). The top-3 reasons are the features pushing
hardest **toward the verdict** -- toward malicious for a malicious call, toward
benign for a clean one -- converted to plain English by
`sentinel_ml/reasons.py` (all 54 feature names are mapped). Before 2026-09-18
the ranking was by absolute size, and 5 of the 20 demo malicious verdicts led
with a reason pointing at *benign*. `/score/file` also returns the structured
top-5 in `details.shap` (`base_value`, `margin`, `probability`, and per feature
the value, its SHAP contribution and which way it pushes). Note the model
leans heavily on `ImageBase` (see "Known limits"), so that reason is worded
as a caution, not as evidence of behaviour.

## FieldGuard (phase 2, on-device)

Not trained on real data yet -- the provided dataset has no radio/IoT
traffic. `sentinel_ml/field_model.py` trains a small (max_depth ~6)
decision tree on recorded `Trace` rows and exports it to C
(`export/field_model.h`, `int classify_window(const float* f)`) once
`data/traces/*.jsonl` exists (`make field-model`). The pipeline itself
(train -> C export -> gcc compile -> parity check) is verified against
synthetic data in `ml/tests/` -- **that synthetic accuracy is not a real
result** and is never written to this file or to `reports/metrics.json`.
