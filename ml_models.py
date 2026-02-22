"""
Transformer-based category classifier and regression-based urgency score S in [0, 1].
Load once per worker; run in worker process only.
"""

from typing import Literal

Category = Literal["Billing", "Technical", "Legal"]

_classifier_pipeline = None
_sentiment_pipeline = None


def _get_classifier():
    """Lazy-load zero-shot classification pipeline."""
    global _classifier_pipeline
    if _classifier_pipeline is None:
        from transformers import pipeline
        _classifier_pipeline = pipeline(
            "zero-shot-classification",
            model="typeform/distilbert-base-uncased-mnli",
            device=-1,
        )
    return _classifier_pipeline


def _get_sentiment():
    """Lazy-load sentiment pipeline for urgency proxy (negative = more urgent)."""
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        from transformers import pipeline
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=-1,
        )
    return _sentiment_pipeline


def predict_category(text: str) -> Category:
    """Classify ticket into Billing, Technical, or Legal using zero-shot NLI."""
    if not text or not text.strip():
        return "Technical"
    text = text[:512]  # avoid overflow
    pipe = _get_classifier()
    out = pipe(text, candidate_labels=["Billing", "Technical", "Legal"], multi_label=False)
    label = out["labels"][0]
    if label not in ("Billing", "Technical", "Legal"):
        return "Technical"
    return label  # type: ignore


def predict_urgency_score(text: str) -> float:
    """
    Return continuous urgency score S in [0, 1] from sentiment.
    More negative sentiment -> higher urgency. Uses NEGATIVE score as proxy for urgency.
    """
    if not text or not text.strip():
        return 0.0
    text = text[:512]
    pipe = _get_sentiment()
    result = pipe(text)[0]
    # result: {"label": "NEGATIVE"|"POSITIVE", "score": float}
    if result["label"] == "NEGATIVE":
        return float(result["score"])  # already in [0,1]; higher = more negative = more urgent
    return 1.0 - float(result["score"])  # positive -> low urgency
