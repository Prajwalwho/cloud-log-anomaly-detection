"""
RQ2: does the feature representation, and retraining on recent data, change detection quality?

Variants (same chronological splits and test sets as RQ1):
    V0  raw counts                        the RQ1 setting
    V1  log counts                        log(1 + count): reduces the dominance of large bursts
    V2  log counts + level counts         BGL only: adds log(1 + count) of FATAL, ERROR, SEVERE, WARNING,
                                          FAILURE lines per window
    V3  retrain on recent data            trained on train + validation normal data, same test set;
                                          label-free threshold only (validation is used for training)

Models: z-score, PCA, Isolation Forest, One-Class SVM (nu = 0.001, chosen in RQ1 on both datasets).
Reference: B5 FATAL count (BGL).

Output (committed): experiments/results/rq2_feature_variants.csv

Usage (from the project root, after parse_hdfs/parse_bgl and the HDFS feature notebook):
    python experiments/run_rq2_features.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.evaluation.metrics import binary_metrics, ranking_metrics  # noqa: E402
from backend.detection.evaluation.splits import chronological_split  # noqa: E402
from backend.detection.evaluation.thresholds import best_f1_threshold, percentile_threshold, predict  # noqa: E402
from backend.detection.features.vectorizer import EventCountVectorizer  # noqa: E402
from backend.detection.models.isolation_forest import IsolationForestDetector  # noqa: E402
from backend.detection.models.one_class_svm import OneClassSVMDetector  # noqa: E402
from backend.detection.models.pca import PCADetector  # noqa: E402
from backend.detection.models.statistical import ZScoreDetector  # noqa: E402

OUT = ROOT / "data" / "processed"
RESULTS = ROOT / "experiments" / "results"
WINDOW_S = 15 * 60
LEVELS = ("FATAL", "ERROR", "SEVERE", "WARNING", "FAILURE")


def section(title: str) -> None:
    print(f"\n{'=' * 90}\n{title}\n{'=' * 90}")


def make_models() -> dict:
    return {
        "z-score": ZScoreDetector(),
        "PCA": PCADetector(variance=0.95),
        "Isolation Forest": IsolationForestDetector(n_estimators=200, random_state=42),
        "One-Class SVM": OneClassSVMDetector(nu=0.001),
    }


def summarise(model: str, scores: np.ndarray, y: np.ndarray, train_normal: np.ndarray,
              val: np.ndarray, test: np.ndarray, use_validation: bool) -> dict:
    """Test-set metrics with the label-free threshold, plus validation-tuned F1 when allowed."""
    threshold = percentile_threshold(scores[train_normal], 99.9)
    m = binary_metrics(y[test], predict(scores[test], threshold))
    row = {
        "model": model,
        "precision": m.precision, "recall": m.recall, "f1_label_free": m.f1, "fp": m.fp,
        "pr_auc": ranking_metrics(y[test], scores[test])["pr_auc"],
        "f1_validation_tuned": np.nan,
    }
    if use_validation:
        tuned, _ = best_f1_threshold(y[val], scores[val])
        row["f1_validation_tuned"] = binary_metrics(y[test], predict(scores[test], tuned)).f1
    return row


def run_variant(dataset: str, variant: str, X: np.ndarray, y: np.ndarray, fit_idx: np.ndarray,
                val: np.ndarray, test: np.ndarray, use_validation: bool) -> list[dict]:
    rows = []
    for name, model in make_models().items():
        start = time.time()
        model.fit(X[fit_idx])
        scores = model.score(X)
        row = summarise(name, scores, y, fit_idx, val, test, use_validation)
        row.update(dataset=dataset, variant=variant, features=X.shape[1], seconds=round(time.time() - start, 2))
        rows.append(row)
    print(f"  {dataset:<5} {variant:<40} done ({X.shape[1]} features)")
    return rows


# ---------------------------------------------------------------------------
# BGL
# ---------------------------------------------------------------------------
def run_bgl() -> list[dict]:
    events = np.load(OUT / "bgl_events.npz")
    ts, alert, template = events["timestamp"], events["alert"], events["template"]
    level_names = events["level_names"][events["level"]]

    window = (ts - ts.min()) // WINDOW_S
    _, starts = np.unique(window, return_index=True)
    sequences = [s.tolist() for s in np.split(template, starts[1:])]
    y = np.maximum.reduceat(alert.astype(np.int8), starts).astype(bool)
    level_counts = np.column_stack(
        [np.add.reduceat((level_names == level).astype(np.int32), starts) for level in LEVELS]
    ).astype(float)

    split = chronological_split(len(sequences), train=0.6, validation=0.2)
    train, val, test = split["train"], split["validation"], split["test"]
    train_normal = train[~y[train]]
    recent_normal = np.concatenate([train_normal, val[~y[val]]])

    def counts(fit_idx: np.ndarray) -> np.ndarray:
        vectorizer = EventCountVectorizer().fit(sequences[i] for i in fit_idx)
        return vectorizer.transform(sequences).astype(float)

    X_train_vocab = counts(train_normal)
    X_recent_vocab = counts(recent_normal)
    log_levels = np.log1p(level_counts)

    section("BGL: normal test windows containing a template unseen in the training data")
    for label, X in (("vocabulary from training normals", X_train_vocab),
                     ("vocabulary from train + validation normals", X_recent_vocab)):
        normal_test = test[~y[test]]
        print(f"  {label:<45} {100 * (X[normal_test, -1] > 0).mean():6.2f}%")

    section("BGL: running variants")
    rows = []
    reference = summarise("B5 FATAL count", level_counts[:, 0], y, train_normal, val, test, True)
    reference.update(dataset="BGL", variant="reference", features=1, seconds=0.0)
    rows.append(reference)

    variants = [
        ("V0 raw counts", X_train_vocab, train_normal, True),
        ("V1 log counts", np.log1p(X_train_vocab), train_normal, True),
        ("V2 log counts + levels", np.hstack([np.log1p(X_train_vocab), log_levels]), train_normal, True),
        ("V3 V2 + retrain on train+validation",
         np.hstack([np.log1p(X_recent_vocab), log_levels]), recent_normal, False),
    ]
    for variant, X, fit_idx, use_validation in variants:
        rows += run_variant("BGL", variant, X, y, fit_idx, val, test, use_validation)
    return rows


# ---------------------------------------------------------------------------
# HDFS (control: variants should not break what already works)
# ---------------------------------------------------------------------------
def run_hdfs() -> list[dict]:
    data = np.load(OUT / "hdfs_features.npz")
    X, y = data["X"].astype(float), data["y"]
    train_normal, val, test = data["train_normal"], data["validation"], data["test"]
    recent_normal = np.concatenate([train_normal, val[~y[val]]])

    section("HDFS: running variants")
    rows = []
    variants = [
        ("V0 raw counts", X, train_normal, True),
        ("V1 log counts", np.log1p(X), train_normal, True),
        # Vocabulary stays the one from training normals (fixed in hdfs_features.npz); on HDFS
        # validation normal blocks contain no unseen templates, so this does not change the features.
        ("V3 V1 + retrain on train+validation", np.log1p(X), recent_normal, False),
    ]
    for variant, Xv, fit_idx, use_validation in variants:
        rows += run_variant("HDFS", variant, Xv, y, fit_idx, val, test, use_validation)
    return rows


# ---------------------------------------------------------------------------
def main() -> int:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)

    for required in ("bgl_events.npz", "hdfs_features.npz"):
        if not (OUT / required).exists():
            print(f"[FAIL] {OUT / required} not found.")
            return 1

    rows = run_bgl() + run_hdfs()
    results = pd.DataFrame(rows)

    for dataset in ("BGL", "HDFS"):
        part = results[results["dataset"] == dataset]
        for metric, title in (("f1_label_free", "F1 (label-free p99.9 threshold)"),
                              ("f1_validation_tuned", "F1 (validation-tuned threshold; not applicable to V3)"),
                              ("pr_auc", "PR-AUC (threshold-free ranking)")):
            section(f"{dataset} test set: {title}")
            print(part.pivot_table(index="model", columns="variant", values=metric).round(4).to_string())

    RESULTS.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS / "rq2_feature_variants.csv", index=False)
    print(f"\nSaved {RESULTS / 'rq2_feature_variants.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())