"""SMS Guard: TF-IDF (word + char n-gram) + logistic regression smishing
detector.

Deliberately mirrors ml/sentinel_ml/mailguard.py's shape -- "same engine, new
config," not a different architecture -- but this module is self-contained
inside channels/sms/ rather than importing from the ml/ package. That is a
deliberate pluggability choice: a "detection channel" should be able to live
entirely inside its own channels/<id>/ folder (data prep, features, model,
inference) with nothing outside it required at serve time, which is exactly
the property this feature is trying to demonstrate to the reviewer.

Feature pipeline, tuned for SMS's much shorter length than email:
  - word-level TF-IDF (unigrams+bigrams, small vocab ~3000) -- the same kind
    of signal MailGuard uses (urgency language, "verify", "account", etc.)
  - character n-gram TF-IDF (3-5 grams, word-bounded) -- catches obfuscated
    spam text like "cl1ck h3re" or "FR33" that a word-level vocabulary would
    either miss entirely or fragment into meaningless out-of-vocabulary
    tokens
Combined via a FeatureUnion so a single LogisticRegression sees both.
"""
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

SEED = 42

# -- text normalization ------------------------------------------------------
# Mirrors ml/sentinel_ml/text.py's approach (numbers/URLs -> placeholder
# tokens so the model can't memorize one phone number or shortlink domain)
# but kept local to this channel on purpose -- see module docstring.
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_NUM_RE = re.compile(r"\d+")


def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = _URL_RE.sub(" urltok ", text)
    text = _NUM_RE.sub(" numtok ", text)
    return text


# -- feature pipeline ---------------------------------------------------------

def build_vectorizer() -> FeatureUnion:
    word = TfidfVectorizer(
        preprocessor=normalize_text,
        ngram_range=(1, 2),
        min_df=2,
        max_features=3000,
        sublinear_tf=True,
    )
    # char_wb: n-grams within word boundaries only (padded with spaces), so
    # "cl1ck" still yields "cl1", "l1c", "1ck" etc. without also matching
    # across unrelated adjacent words. Deliberately NOT run through
    # normalize_text -- replacing "1" with "numtok" would erase exactly the
    # obfuscation signal this feature exists to catch.
    char = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=2,
        max_features=3000,
        sublinear_tf=True,
        lowercase=True,
    )
    return FeatureUnion([("word", word), ("char", char)])


def fit(texts, labels, vec: FeatureUnion = None):
    vec = vec or build_vectorizer()
    X = vec.fit_transform(texts)
    model = LogisticRegression(C=4, max_iter=2000, class_weight="balanced").fit(X, labels)
    return vec, model


def predict_proba(vec: FeatureUnion, model: LogisticRegression, texts):
    return model.predict_proba(vec.transform(texts))[:, 1]


def _humanize(name: str, contrib: float) -> str:
    direction = "smishing" if contrib > 0 else "legitimate"
    strength = "strongly" if abs(contrib) > 1.0 else "moderately" if abs(contrib) > 0.4 else "slightly"
    if name.startswith("word__"):
        token = name[len("word__"):]
        return f"the word/phrase '{token}' {strength} suggests {direction}"
    if name.startswith("char__"):
        token = name[len("char__"):].strip()
        return f"the character pattern '{token}' {strength} suggests {direction}"
    return f"'{name}' {strength} suggests {direction}"


def explain(vec: FeatureUnion, model: LogisticRegression, text: str, top_k: int = 3) -> list[str]:
    """Top-k contributing n-grams (word or char) that drove the score, same
    |coef * tfidf| ranking mailguard.explain() uses."""
    x = vec.transform([text])
    coef = model.coef_[0]
    idx = x.nonzero()[1]
    if len(idx) == 0:
        return []
    contrib = np.asarray(x[0, idx].todense()).ravel() * coef[idx]
    order = np.argsort(-np.abs(contrib))[:top_k]
    names = vec.get_feature_names_out()
    return [_humanize(names[idx[p]], float(contrib[p])) for p in order]


def top_global_ngrams(vec: FeatureUnion, model: LogisticRegression, top_k: int = 15) -> list[str]:
    """Top-k globally most smishing-indicative n-grams (by raw coefficient,
    not tied to one message) -- useful for a training report, not per-call."""
    names = vec.get_feature_names_out()
    coef = model.coef_[0]
    order = np.argsort(-coef)[:top_k]
    return [_humanize(names[i], float(coef[i])) for i in order]
