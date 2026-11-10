"""
Error analysis (Phase 5 wrap-up).

HDFS: what are the "novel normal" test blocks that the lookup table and every working model flag?
      Is their label doubtful (same count vector as some anomalous block)?
BGL:  which message types, unseen among training normal windows, make normal test windows look anomalous
      (concept drift)? When did they first appear, and did they occur in training anomalous windows?

Outputs (committed):
    experiments/results/error_analysis_hdfs_novel_normal.csv
    experiments/results/error_analysis_bgl_new_templates.csv

Usage (from the project root):
    python experiments/run_error_analysis.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.evaluation.splits import chronological_split  # noqa: E402

OUT = ROOT / "data" / "processed"
RESULTS = ROOT / "experiments" / "results"
WINDOW_S = 15 * 60


def section(title: str) -> None:
    print(f"\n{'=' * 90}\n{title}\n{'=' * 90}")


# ---------------------------------------------------------------------------
# HDFS
# ---------------------------------------------------------------------------
def hdfs() -> None:
    data = np.load(OUT / "hdfs_features.npz")
    X, y = data["X"], data["y"]
    train_normal, test = data["train_normal"], data["test"]
    feature_names = list(data["feature_names"])
    block_ids = data["block_ids"]
    template_text = pd.read_csv(OUT / "hdfs_templates.csv").set_index("template_id")["template"]

    keys = [row.tobytes() for row in X]
    train_keys = {keys[i] for i in train_normal}
    anomaly_keys = {keys[i] for i in np.flatnonzero(y)}
    novel_normal = np.array([i for i in test if not y[i] and keys[i] not in train_keys])

    section("HDFS: novel normal test blocks")
    same_as_anomaly = np.array([keys[i] in anomaly_keys for i in novel_normal])
    print(f"Novel normal test blocks: {len(novel_normal)}  "
          f"(distinct count vectors among them: {len({keys[i] for i in novel_normal})})")
    print(f"Exact count vector also found among anomalous blocks: {same_as_anomaly.sum()} "
          f"of {len(novel_normal)} ({100 * same_as_anomaly.mean():.1f}%)")

    lengths = X.sum(axis=1)
    normal_test = test[~y[test]]
    print(f"Events per block, novel normal: median {np.median(lengths[novel_normal]):.0f} "
          f"(min {lengths[novel_normal].min()}, max {lengths[novel_normal].max()}); "
          f"all normal test blocks: median {np.median(lengths[normal_test]):.0f}")

    # How do they differ from the most common normal training block?
    mode_key = Counter(keys[i] for i in train_normal).most_common(1)[0][0]
    mode = np.frombuffer(mode_key, dtype=X.dtype)
    differs = X[novel_normal] != mode
    rows = []
    for j, name in enumerate(feature_names):
        if differs[:, j].any():
            text = "templates unseen in training normals" if name == "unseen" else template_text.get(int(name[1:]), "?")
            rows.append({"feature": name, "blocks_differing_%": round(100 * differs[:, j].mean(), 1),
                         "mean_count_novel": round(X[novel_normal, j].mean(), 2),
                         "count_in_typical_block": int(mode[j]), "template": text[:80]})
    print("\nFeatures where novel normal blocks differ from the most common training-normal block:")
    print(pd.DataFrame(rows).sort_values("blocks_differing_%", ascending=False).to_string(index=False))

    pd.DataFrame({
        "block_id": block_ids[novel_normal],
        "events": lengths[novel_normal],
        "same_vector_as_some_anomaly": same_as_anomaly,
        "count_vector": [" ".join(map(str, X[i])) for i in novel_normal],
    }).to_csv(RESULTS / "error_analysis_hdfs_novel_normal.csv", index=False)


# ---------------------------------------------------------------------------
# BGL
# ---------------------------------------------------------------------------
def bgl() -> None:
    events = np.load(OUT / "bgl_events.npz")
    ts, alert, template = events["timestamp"], events["alert"], events["template"]
    template_text = pd.read_csv(OUT / "bgl_templates.csv").set_index("template_id")["template"]

    window = (ts - ts.min()) // WINDOW_S
    _, starts, lengths = np.unique(window, return_index=True, return_counts=True)
    n_windows = len(starts)
    y = np.maximum.reduceat(alert.astype(np.int8), starts).astype(bool)
    split = chronological_split(n_windows, train=0.6, validation=0.2)
    line_window = np.repeat(np.arange(n_windows), lengths)

    train_normal_w = split["train"][~y[split["train"]]]
    train_anomalous_w = split["train"][y[split["train"]]]
    test_normal_w = split["test"][~y[split["test"]]]

    vocabulary = np.unique(template[np.isin(line_window, train_normal_w)])
    in_train_anomalous = set(np.unique(template[np.isin(line_window, train_anomalous_w)]).tolist())
    first_seen_anywhere = pd.Series(ts).groupby(template).min()

    new_lines = np.isin(line_window, test_normal_w) & ~np.isin(template, vocabulary)
    df = pd.DataFrame({"template_id": template[new_lines], "window": line_window[new_lines]})

    section("BGL: message types unseen among training normals, in normal test windows")
    affected = df["window"].nunique()
    print(f"Normal test windows: {len(test_normal_w):,}; with at least one such template: {affected:,} "
          f"({100 * affected / len(test_normal_w):.2f}%)")

    per = df.groupby("template_id").agg(normal_test_windows=("window", "nunique"), lines=("window", "size"))
    per["first_seen"] = pd.to_datetime(first_seen_anywhere.reindex(per.index), unit="s").dt.date
    per["in_training_anomalous_windows"] = [t in in_train_anomalous for t in per.index]
    per["template"] = template_text.reindex(per.index).str.slice(0, 80)
    per = per.sort_values("normal_test_windows", ascending=False)
    print(f"Distinct such templates: {len(per)}; of these seen in training ANOMALOUS windows: "
          f"{per['in_training_anomalous_windows'].sum()}")

    top5 = per.index[:5]
    covered = df[df["template_id"].isin(top5)]["window"].nunique()
    print(f"The 5 most frequent of them appear in {covered:,} of the {affected:,} affected windows "
          f"({100 * covered / affected:.1f}%)")
    print("\nTop 15:")
    print(per.head(15).to_string())

    per.to_csv(RESULTS / "error_analysis_bgl_new_templates.csv")


def main() -> int:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    for required in ("hdfs_features.npz", "hdfs_templates.csv", "bgl_events.npz", "bgl_templates.csv"):
        if not (OUT / required).exists():
            print(f"[FAIL] {OUT / required} not found.")
            return 1
    hdfs()
    bgl()
    print(f"\nSaved error_analysis_hdfs_novel_normal.csv and error_analysis_bgl_new_templates.csv to {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())