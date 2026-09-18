"""Generates transformer_mailguard.ipynb. Run this to regenerate the
notebook after editing the cell source below -- keeps the notebook's
JSON valid without hand-editing it.

    python _build_transformer_notebook.py
"""
import os

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "transformer_mailguard.ipynb")

nb = nbf.v4.new_notebook()
cells = []


def md(src):
    cells.append(nbf.v4.new_markdown_cell(src))


def code(src):
    cells.append(nbf.v4.new_code_cell(src))


md(r"""# MailGuard: DistilBERT vs. TF-IDF

Brief section 5's "strengthen at the event" list: *fine-tune a small
transformer (e.g. DistilBERT) on a free GPU notebook; adopt it only if it
beats TF-IDF on the held-out-collection test.*

This notebook is meant to run on a **free Colab or Kaggle GPU** (Runtime
-> Change runtime type -> GPU). It:

1. Loads the same 5 deduplicated email corpora MailGuard's TF-IDF model
   uses (`sentinel_ml/data.py`'s rules -- CEAS_08, Enron, Ling,
   Nigerian_Fraud, SpamAssasin only).
2. Fine-tunes DistilBERT for binary classification.
3. Evaluates it with **the same protocol** as the shipped model: a random
   split, leave-one-corpus-out (the honest generalization number), and
   the padding red-team test.
4. Prints a comparison table against TF-IDF and a recommendation --
   **switch only if DistilBERT wins on held-out (leave-one-corpus-out)
   false alarms**, not on the random split (which flatters every model).
""")

code(r"""# 1. Setup
!pip install -q transformers datasets accelerate torch scikit-learn pandas

import torch
print("CUDA available:", torch.cuda.is_available())
""")

md(r"""## 2. Get the data and the TF-IDF baseline code

Clone the repo so we reuse the exact same data rules, split seed and
padding function the shipped MailGuard model was built with -- this is
what makes the comparison apples-to-apples rather than two different
experiments.

Upload the club's `security/` folder (zipped) to this Colab session, or
mount Drive, and set `DATA_ROOT` below.
""")

code(r"""import os, sys, subprocess

REPO_URL = "https://github.com/ramkirangaruda/Sentinel-Mesh.git"
if not os.path.exists("Sentinel-Mesh"):
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL], check=True)
sys.path.insert(0, os.path.join("Sentinel-Mesh", "ml"))

# Point this at your unzipped 'security' folder (upload it to Colab, or
# mount Drive and set the Drive path here).
DATA_ROOT = "/content/security"
assert os.path.isdir(DATA_ROOT), f"upload/unzip the security folder to {DATA_ROOT} first"
""")

code(r"""from sentinel_ml.data import EMAIL_CORPORA, load_emails
from sentinel_ml.mailguard import SEED, pad_with_legit
from sklearn.model_selection import train_test_split
import numpy as np, pandas as pd

em = load_emails(DATA_ROOT)
em["t"] = em["text"].str.slice(0, 3000)
print(f"{len(em)} deduplicated emails across {em.source.nunique()} corpora")

tr, rest = train_test_split(em, test_size=0.3, stratify=em.label, random_state=SEED)
val, te = train_test_split(rest, test_size=0.5, stratify=rest.label, random_state=SEED)
print(f"train={len(tr)} val={len(val)} test={len(te)}")
""")

md("## 3. TF-IDF baseline (for comparison, trained here so both models see identical data)")

code(r"""from sentinel_ml import mailguard

v_tfidf, m_tfidf, thr_tfidf, tfidf_metrics = mailguard.train(DATA_ROOT, max_false_alarm=0.02)
print(tfidf_metrics["email_random_split_final"])
""")

md(r"""## 4. Fine-tune DistilBERT

A few epochs is plenty for this task/size; increase `EPOCHS` if you have
GPU time to spare. Uses `distilbert-base-uncased`.
""")

code(r"""from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification, Trainer, TrainingArguments
import torch
from torch.utils.data import Dataset

MODEL_NAME = "distilbert-base-uncased"
MAX_LEN = 256
EPOCHS = 2
BATCH_SIZE = 16

tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)

class EmailDataset(Dataset):
    def __init__(self, texts, labels):
        self.enc = tokenizer(list(texts), truncation=True, padding=True, max_length=MAX_LEN)
        self.labels = list(labels)
    def __len__(self):
        return len(self.labels)
    def __getitem__(self, i):
        item = {k: torch.tensor(v[i]) for k, v in self.enc.items()}
        item["labels"] = torch.tensor(self.labels[i])
        return item

def fit_distilbert(train_texts, train_labels, epochs=EPOCHS):
    model = DistilBertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    args = TrainingArguments(
        output_dir="/content/distilbert_mailguard",
        num_train_epochs=epochs,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        logging_steps=50,
        save_strategy="no",
        report_to=[],
        fp16=torch.cuda.is_available(),
    )
    trainer = Trainer(model=model, args=args, train_dataset=EmailDataset(train_texts, train_labels))
    trainer.train()
    return trainer, model

def distilbert_scores(trainer, texts):
    ds = EmailDataset(texts, [0] * len(texts))
    logits = trainer.predict(ds).predictions
    probs = torch.softmax(torch.tensor(logits), dim=1)[:, 1].numpy()
    return probs

trainer, model = fit_distilbert(tr.t, tr.label)
""")

md("## 5. Evaluate: random split (same test set as the TF-IDF baseline)")

code(r"""from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, roc_curve

def tpr_at_fpr(y, s, target):
    f, t, _ = roc_curve(y, s)
    return float(np.interp(target, f, t))

def threshold_for_max_fpr(y, s, max_fpr):
    f, t, thr = roc_curve(y, s)
    ok = f <= max_fpr
    return float(thr[np.argmax(np.where(ok, t, -1))]) if ok.any() else float(thr[np.argmin(f)])

s_val = distilbert_scores(trainer, val.t)
thr_bert = threshold_for_max_fpr(val.label.values, s_val, 0.02)

s_te = distilbert_scores(trainer, te.t)
p_te = s_te >= thr_bert
bert_random_split = dict(
    threshold=round(thr_bert, 4),
    acc=round(accuracy_score(te.label, p_te), 4),
    f1=round(f1_score(te.label, p_te), 4),
    auc=round(roc_auc_score(te.label, s_te), 4),
    legit_false_alarm=round(float(p_te[te.label.values == 0].mean()), 4),
    malicious_recall=round(float(p_te[te.label.values == 1].mean()), 4),
)
print(bert_random_split)
""")

md(r"""## 6. Evaluate: leave-one-corpus-out (the honest number)

Retrains DistilBERT once per held-out corpus -- this is the expensive
part; each pass is a full fine-tune on ~4 corpora's worth of data.
""")

code(r"""bert_loco = {}
for src in EMAIL_CORPORA:
    a, b = em[em.source != src], em[em.source == src]
    trainer_i, _ = fit_distilbert(a.t, a.label, epochs=EPOCHS)
    sb = distilbert_scores(trainer_i, b.t)
    pb = sb >= 0.5
    r = dict(malicious_recall=round(float(pb[b.label.values == 1].mean()), 4))
    if b.label.nunique() > 1:
        r.update(
            acc=round(accuracy_score(b.label, pb), 4),
            auc=round(roc_auc_score(b.label, sb), 4),
            legit_false_alarm=round(float(pb[b.label.values == 0].mean()), 4),
        )
    bert_loco[src] = r
    print(src, r)
""")

md("## 7. Red-team test: DistilBERT vs. the padding attack")

code(r"""rng = np.random.default_rng(0)
legit_pool = tr[tr.label == 0].t.str.slice(0, 600).values
n_mal = min(3000, (te.label == 1).sum())
mal = te[te.label == 1].sample(n_mal, random_state=0).t.values
padded = pad_with_legit(mal, legit_pool, rng)
legit = te[te.label == 0].t.values

def redteam_report(score_fn):
    sc = lambda X: score_fn(X) >= 0.5
    return dict(
        legit_false_alarm=round(float(sc(legit).mean()), 4),
        recall_clean=round(float(sc(mal).mean()), 4),
        recall_padded=round(float(sc(padded).mean()), 4),
    )

bert_redteam = redteam_report(lambda X: distilbert_scores(trainer, X))
print("DistilBERT (not adversarially trained):", bert_redteam)
print("TF-IDF (adversarially trained, from build_all.py):", tfidf_metrics["email_red_team_padding"]["adversarially_trained"])
""")

md("## 8. Comparison table and recommendation")

code(r"""tfidf_loco = tfidf_metrics["email_leave_one_corpus_out"]
tfidf_loco_fa = np.mean([v["legit_false_alarm"] for v in tfidf_loco.values() if "legit_false_alarm" in v])
bert_loco_fa = np.mean([v["legit_false_alarm"] for v in bert_loco.values() if "legit_false_alarm" in v])

comparison = pd.DataFrame([
    dict(model="TF-IDF + LogisticRegression",
         random_split_acc=tfidf_metrics["email_random_split_final"]["acc"],
         random_split_false_alarm=tfidf_metrics["email_random_split_final"]["legit_false_alarm"],
         loco_mean_false_alarm=round(float(tfidf_loco_fa), 4),
         red_team_recall_padded=tfidf_metrics["email_red_team_padding"]["adversarially_trained"]["recall_padded"]),
    dict(model="DistilBERT",
         random_split_acc=bert_random_split["acc"],
         random_split_false_alarm=bert_random_split["legit_false_alarm"],
         loco_mean_false_alarm=round(float(bert_loco_fa), 4),
         red_team_recall_padded=bert_redteam["recall_padded"]),
])
print(comparison.to_string(index=False))

if bert_loco_fa < tfidf_loco_fa:
    print(f"\nRECOMMENDATION: switch to DistilBERT -- held-out false alarms "
          f"{bert_loco_fa:.1%} beats TF-IDF's {tfidf_loco_fa:.1%}.")
else:
    print(f"\nRECOMMENDATION: keep TF-IDF -- it wins (or ties) on the held-out "
          f"false-alarm rate ({tfidf_loco_fa:.1%} vs DistilBERT's {bert_loco_fa:.1%}), "
          f"and it's ~1000x cheaper to train and serve. The random-split numbers alone "
          f"would have been misleading here (brief section 5's whole point).")
""")

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    "accelerator": "GPU",
}

with open(OUT, "w") as f:
    nbf.write(nb, f)
print(f"wrote {OUT}")
