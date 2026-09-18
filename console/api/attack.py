"""MITRE ATT&CK labels and the four-step attack chain.

Technique ids come from the events themselves (contracts/CONTRACT.md fixes
which layer emits which); this module only turns an id into something an
operator can read, and maps a layer onto its step in the Ukraine-2015 chain
the pitch follows.
"""

TECHNIQUES = {
    "T1566.001": {
        "name": "Phishing: Spearphishing Attachment",
        "tactic": "Initial Access",
        "url": "https://attack.mitre.org/techniques/T1566/001/",
    },
    "T1204.002": {
        "name": "User Execution: Malicious File",
        "tactic": "Execution",
        "url": "https://attack.mitre.org/techniques/T1204/002/",
    },
    "T0830": {
        "name": "Adversary-in-the-Middle (ICS)",
        "tactic": "Collection",
        "url": "https://attack.mitre.org/techniques/T0830/",
    },
    "T1692.002": {
        "name": "Unauthorized Message: Reporting Message (ICS)",
        "tactic": "Impair Process Control",
        "url": "https://attack.mitre.org/techniques/T1692/002/",
    },
}

# layer -> (step index, label shown on the attack-chain strip)
CHAIN = {
    "mail": (0, "Inbox"),
    "file": (1, "Endpoint"),
    "field": (2, "Field network"),
    "tamper": (3, "Physical"),
}
CHAIN_STEPS = ["Inbox", "Endpoint", "Field network", "Physical"]
CHAIN_LAYERS = ["mail", "file", "field", "tamper"]


def technique_name(technique: str | None) -> str | None:
    if not technique:
        return None
    known = TECHNIQUES.get(technique)
    return f"{technique} {known['name']}" if known else technique


def technique_info(technique: str | None) -> dict | None:
    if not technique:
        return None
    return TECHNIQUES.get(technique, {"name": "unknown technique", "tactic": "", "url": ""})


def chain_state(layers) -> list[dict]:
    """Which steps of Inbox -> Endpoint -> Field -> Physical have fired."""
    lit = set(layers)
    return [
        {"step": CHAIN_STEPS[i], "layer": layer, "lit": layer in lit}
        for i, layer in enumerate(CHAIN_LAYERS)
    ]
