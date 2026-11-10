"""
BGL model comparison (RQ1).

15-minute windows (anomalous = at least one alert line), chronological 60/20/20 split,
count vectors (vocabulary from training normal windows + "unseen" column), baselines and the
four detectors, evaluated exactly like HDFS with evaluate_scores().

Outputs (experiments/results/, committed):
    bgl_model_comparison.csv, bgl_model_comparison_summary.csv, bgl_pr_curves.png,
    rq1_combined_summary.csv

Usage (from the project root, after experiments/parse_bgl.py):
    python experiments/run_bgl_comparison.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")   # save plots to files, no window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.evaluation.evaluate import evaluate_scores  # noqa: E402
from backend.detection.evaluation.metrics import ranking_metrics  # noqa: E402
from backend.detection.evaluation.splits import chronological_split  # noqa: E402
from backend.detection.features.vectorizer import EventCountVectorizer  # noqa: E402
from backend.detection.models.isolation_forest import IsolationForestDetector  # noqa: E402
from backend.detection.models.one_class_svm import OneClassSVMDetector  # noqa: E402
from backend.detection.models.pca import PCADetector  # noqa: E402
from backend.detection.models.statistical import ZScoreDetector  # noqa: E402

OUT = ROOT / "data" / "processed"
RESULTS = ROOT / "experiments" / "results"
WINDOW_S = 15 * 60


def section(title: str) -> None:
    print(f"\n{'=' * 90}\n{title}\n{'=' * 90}")


def main() -> int:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.max_colwidth", 90)

    events_file = OUT / "bgl_events.npz"
    if not events_file.exists():
        print(f"[FAIL] {events_file} not found. Run: python experiments/parse_bgl.py")
        return 1

    events = np.load(events_file)
    ts, alert, template = events["timestamp"], events["alert"], events["template"]
    level_names = events["level_names"][events["level"]]
    templates = pd.read_csv(OUT / "bgl_templates.csv")
    print(f"{len(ts):,} lines, {alert.sum():,} alert lines, {len(templates):,} templates")

    # ---------------------------------------------------------------- 1
    section("1. Parser check: rare normal templates")
    per_template = (pd.DataFrame({"template_id": template, "alert": alert})
                    .groupby("template_id")["alert"].agg(lines="size", alert_share="mean")
                    .join(templates.set_index("template_id")["template"]))
    normal_templates = per_template[per_template["alert_share"] == 0]
    alert_templates = per_template[per_template["alert_share"] == 1]
    print(f"Templates never in an alert line: {len(normal_templates)} "
          f"(with at most 5 lines: {(normal_templates['lines'] <= 5).sum()})")
    print(f"Templates always alert: {len(alert_templates)}; mixed: "
          f"{len(per_template) - len(normal_templates) - len(alert_templates)}")
    print("\n15 rarest normal templates:")
    print(normal_templates.sort_values("lines").head(15)[["lines", "template"]].to_string())

    # ---------------------------------------------------------------- 2
    section("2. 15-minute windows")
    t0 = ts.min()
    window = (ts - t0) // WINDOW_S                      # timestamps are in order (Day 17)
    window_ids, starts, lengths = np.unique(window, return_index=True, return_counts=True)
    sequences = [s.tolist() for s in np.split(template, starts[1:])]
    y = np.maximum.reduceat(alert.astype(np.int8), starts).astype(bool)
    fatal_count = np.add.reduceat((level_names == "FATAL").astype(np.int32), starts)
    window_start = pd.to_datetime(t0 + window_ids * WINDOW_S, unit="s")
    print(f"{len(sequences):,} non-empty windows, {y.sum():,} anomalous ({100 * y.mean():.2f}%), "
          f"median {int(np.median(lengths))} lines per window")

    # ---------------------------------------------------------------- 3
    section("3. Chronological split (60/20/20)")
    split = chronological_split(len(sequences), train=0.6, validation=0.2)
    rows = []
    for name, idx in split.items():
        rows.append({"split": name, "windows": len(idx), "anomalous": int(y[idx].sum()),
                     "anomalous_%": round(100 * y[idx].mean(), 2),
                     "from": window_start[idx[0]].date(), "to": window_start[idx[-1]].date()})
    print(pd.DataFrame(rows).to_string(index=False))
    train_normal = split["train"][~y[split["train"]]]
    val, test = split["validation"], split["test"]
    splits = {"validation": val, "test": test}
    print(f"Training normal windows: {len(train_normal):,}")

    # ---------------------------------------------------------------- 4
    section("4. Count vectors")
    vectorizer = EventCountVectorizer().fit(sequences[i] for i in train_normal)
    X_int = vectorizer.transform(sequences)
    X = X_int.astype(float)
    print(f"Feature matrix: {X.shape[0]:,} windows x {X.shape[1]} features "
          f"({len(vectorizer.vocabulary_)} templates seen in training normals + unseen)")
    has_unseen = X_int[:, -1] > 0
    rows = []
    for name, idx in split.items():
        for label, mask in (("Normal", ~y[idx]), ("Anomaly", y[idx])):
            part = idx[mask]
            rows.append({"split": name, "label": label, "windows": len(part),
                         "with_unseen_template_%": round(100 * has_unseen[part].mean(), 2) if len(part) else 0})
    print(pd.DataFrame(rows).to_string(index=False))
    keys = [row.tobytes() for row in X_int]
    train_keys = {keys[i] for i in train_normal}
    novel = np.array([k not in train_keys for k in keys])
    print(f"Distinct vectors among training normal windows: {len(train_keys):,} of {len(train_normal):,}")

    # ---------------------------------------------------------------- 5
    section("5. Baselines")
    min_len, max_len = lengths[train_normal].min(), lengths[train_normal].max()
    scores = {
        "B1 line count": np.maximum(np.maximum(min_len - lengths, lengths - max_len), 0).astype(float),
        "B2 unseen template": X_int[:, -1].astype(float),
        "B4 lookup": novel.astype(float),
        "B5 FATAL count": fatal_count.astype(float),
    }
    print(f"Training normal window length range: {min_len}-{max_len} lines")

    # ---------------------------------------------------------------- 6
    section("6. One-Class SVM nu (chosen on validation PR-AUC)")
    rows = []
    for nu in (0.001, 0.005, 0.01, 0.05, 0.1):
        model = OneClassSVMDetector(nu=nu).fit(X[train_normal])
        rows.append({"nu": nu, "validation_pr_auc": round(ranking_metrics(y[val], model.score(X[val]))["pr_auc"], 4)})
    nu_table = pd.DataFrame(rows)
    print(nu_table.to_string(index=False))
    best_nu = float(nu_table.loc[nu_table["validation_pr_auc"].idxmax(), "nu"])
    print(f"Chosen nu: {best_nu}")

    # ---------------------------------------------------------------- 7
    section("7. Models: training and scoring time")
    models = {
        "z-score": ZScoreDetector(),
        "PCA": PCADetector(variance=0.95),
        "Isolation Forest": IsolationForestDetector(n_estimators=200, random_state=42),
        "One-Class SVM": OneClassSVMDetector(nu=best_nu),
    }
    rows = []
    for name, model in models.items():
        start = time.time()
        model.fit(X[train_normal])
        fitted = time.time()
        scores[name] = model.score(X)
        rows.append({"model": name, "fit_s": round(fitted - start, 2), "score_s": round(time.time() - fitted, 2)})
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"PCA keeps {models['PCA'].n_components_} of {X.shape[1]} components")

    # ---------------------------------------------------------------- 8
    section("8. Results (same evaluation as HDFS)")
    rows = []
    for name, s in scores.items():
        rows += evaluate_scores(name, s, y, train_normal, splits, novel=novel)
    results = pd.DataFrame(rows).drop(columns=["novel_normal_flagged", "novel_normal_total"])
    show = ["model", "threshold", "precision", "recall", "f1", "fp", "fn", "pr_auc"]
    for part in ("validation", "test"):
        print(f"\n--- {part} ---")
        print(results[results["split"] == part][show].round(4).to_string(index=False))

    # ---------------------------------------------------------------- 9
    section("9. BGL summary (test)")
    summary = (results[results["split"] == "test"]
               .pivot_table(index="model", columns="threshold", values="f1")
               .rename(columns=lambda c: f"F1 {c}"))
    summary["PR-AUC"] = results[results["split"] == "test"].groupby("model")["pr_auc"].first()
    summary = summary.sort_values("F1 label-free p99.9", ascending=False).round(4)
    print(summary.to_string())

    RESULTS.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS / "bgl_model_comparison.csv", index=False)
    summary.to_csv(RESULTS / "bgl_model_comparison_summary.csv")

    fig, ax = plt.subplots(figsize=(7, 5))
    for name, s in scores.items():
        precision, recall, _ = precision_recall_curve(y[test], s[test])
        ax.plot(recall, precision, label=f"{name} (PR-AUC {ranking_metrics(y[test], s[test])['pr_auc']:.3f})")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("BGL test set (15-min windows): precision-recall curves")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "bgl_pr_curves.png", dpi=150)
    plt.close(fig)

    # ---------------------------------------------------------------- 10
    section("10. RQ1 combined summary (test): HDFS and BGL")
    hdfs = pd.read_csv(RESULTS / "hdfs_model_comparison_summary.csv", index_col="model")
    combined = hdfs.add_prefix("HDFS ").join(summary.add_prefix("BGL "), how="outer")
    order = ["B1 line count", "B2 unseen template", "B4 lookup", "B5 FATAL count",
             "z-score", "PCA", "Isolation Forest", "One-Class SVM"]
    combined = combined.reindex([m for m in order if m in combined.index]).round(4)
    print(combined.to_string())
    combined.to_csv(RESULTS / "rq1_combined_summary.csv")
    print("\n(HDFS B1/B2 were evaluated as hard rules on Day 14, not here; B5 does not apply to HDFS.)")

    print(f"\nSaved to {RESULTS}: bgl_model_comparison.csv, bgl_model_comparison_summary.csv, "
          f"bgl_pr_curves.png, rq1_combined_summary.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())