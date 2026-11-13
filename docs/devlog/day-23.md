# Day 23 — Model package and registry

## Done
- backend/detection/package.py: save/load model packages (detector.joblib, drain_state.bin, metadata.json);
  versions are never overwritten; the Drain state is loaded read-only.
- backend/detection/registry.py: register a model (deactivates the previous active model in the same
  transaction), read the active model, set the active model.
- backend/detection/config.py: DetectionSettings (Kafka, PostgreSQL, models directory, windows, services).
- backend/detection/evaluation/live_eval.py: window labelling and evaluation against ground truth (from Day 22).
- backend/detection/train.py: train, save, reload, reproducibility check, fault-run evaluation, fault-free
  evaluation, metadata (copy in models/metadata/), registration.
- parser.py: create_template_miner accepts a persistence handler (loading a saved Drain state).
- tests: test_package.py (3), test_registry_integration.py (2).

## Model live-pca 1.0.0
- Global PCA, log counts, label-free 99.9th-percentile threshold, min_std 0.01.
- Training: train_normal_1/2/3 (seeds 1–3, 2 h each), 1,785 windows, 31 templates, 38 features.
- Training windows flagged: 2 (0.11%, as expected for a 99.9th-percentile threshold).
- Reloaded package reproduces in-memory scores and flags exactly on the fault run.

| Evaluation | Result |
|---|---|
| Fault run (seed 42) | precision 0.571, recall 0.952, F1 0.714, incidents 7/7, quiet false alarms 0/20 |
| Fault-free run (seed 4, 1 h) | 1 false alarm in 295 windows (0.34%), api-gateway |

- Time to first flag: 11 s for most faults, 41 s (cascading inventory), 71 s (silent auth).
- Practical meaning: ~300 windows per hour -> roughly one false alarm per hour; notifications will be limited to
  HIGH/CRITICAL (Phase 8).
- Registered in model_registry as the active model (id 4; ids 1–3 were used and removed by the integration test).

## Decisions
- A model version is immutable: saving refuses to overwrite an existing package.
- The Drain state is part of the package and loaded read-only, so template ids match the feature columns and live
  parsing never changes the package.
- The package files are generated (models/trained/ ignored by Git); the metadata copy in models/metadata/ is
  committed as the model's training record.

## Problems faced
- None.