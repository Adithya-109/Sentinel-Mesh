"""Render the three pitch charts from reports/metrics.json (run build_all.py first).

    1. email_false_alarms.png   random split vs leave-one-corpus-out, per corpus
    2. email_red_team.png       recall before/after adversarial training, clean vs padded
    3. malware_thirdparty.png   third-party false alarms, dataset-only vs +benign
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))


def load_metrics():
    with open(os.path.join(HERE, "metrics.json")) as f:
        return json.load(f)


def chart_email_false_alarms(m):
    loco = m["mailguard"]["email_leave_one_corpus_out"]
    corpora = [c for c in loco if "legit_false_alarm" in loco[c]]
    held_out = [loco[c]["legit_false_alarm"] * 100 for c in corpora]
    random_fa = m["mailguard"]["email_random_split_final"]["legit_false_alarm"] * 100

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = range(len(corpora))
    ax.bar(x, held_out, color="#4472C4", label="Held-out whole corpus")
    ax.axhline(random_fa, color="#A6A6A6", linestyle="--", label=f"Random split ({random_fa:.1f}%)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(corpora, rotation=20, ha="right")
    ax.set_ylabel("False alarm rate on legit mail (%)")
    ax.set_title("MailGuard: random split flatters the model")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "charts", "email_false_alarms.png"), dpi=150)
    plt.close(fig)


def chart_email_red_team(m):
    rt = m["mailguard"]["email_red_team_padding"]
    labels = ["Clean malicious", "Padded malicious"]
    baseline = [rt["baseline"]["recall_clean"] * 100, rt["baseline"]["recall_padded"] * 100]
    hardened = [rt["adversarially_trained"]["recall_clean"] * 100, rt["adversarially_trained"]["recall_padded"] * 100]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    x = range(len(labels))
    w = 0.35
    ax.bar([i - w / 2 for i in x], baseline, width=w, color="#A6A6A6", label="Baseline model")
    ax.bar([i + w / 2 for i in x], hardened, width=w, color="#4472C4", label="Adversarially trained")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Detection rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("MailGuard red-team test: padding attack")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "charts", "email_red_team.png"), dpi=150)
    plt.close(fig)


def chart_malware_thirdparty(m):
    exp = m["fileguard"].get("thirdparty_experiment_mean_of_5")
    if not exp:
        return
    labels = ["dataset_only", "plus_thirdparty_benign"]
    vals = [exp[l]["unseen_thirdparty_false_alarm"] * 100 for l in labels]
    det = [exp[l]["detection_rate"] * 100 for l in labels]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    x = range(len(labels))
    w = 0.35
    ax.bar([i - w / 2 for i in x], vals, width=w, color="#C00000", label="Unseen third-party false alarm")
    ax.bar([i + w / 2 for i in x], det, width=w, color="#4472C4", label="Malware detection rate")
    ax.set_xticks(list(x))
    ax.set_xticklabels(["Dataset only", "+ third-party benign"])
    ax.set_ylabel("Rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("FileGuard: fixing the third-party false-alarm bias")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "charts", "malware_thirdparty.png"), dpi=150)
    plt.close(fig)


def main():
    os.makedirs(os.path.join(HERE, "charts"), exist_ok=True)
    m = load_metrics()
    chart_email_false_alarms(m)
    chart_email_red_team(m)
    chart_malware_thirdparty(m)
    print("wrote charts to", os.path.join(HERE, "charts"))


if __name__ == "__main__":
    main()
