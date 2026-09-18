# transformer_mailguard.ipynb

Brief section 5's optional "strengthen at the event" item: fine-tune
DistilBERT and adopt it only if it beats TF-IDF on the **held-out**
(leave-one-corpus-out) false-alarm rate, not the random split.

Not run in this repo -- it needs a GPU. Open in Colab or Kaggle, upload
the club's `security/` folder (or mount Drive), and run top to bottom.
It clones this repo so it trains on the identical deduplicated corpora
and split seed the shipped TF-IDF model uses, then prints a comparison
table and an automatic recommendation.

Regenerate after editing: `python _build_transformer_notebook.py`
(keeps the notebook's JSON valid rather than hand-editing cells).
