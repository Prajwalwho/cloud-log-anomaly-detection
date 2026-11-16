# Day 45 — Docs: Concepts and How detection works

## Written
- `docs/guide/concepts.md`: service, log event (with a real example and the contract fields), template, window,
  score and threshold (the 0–1 scale), anomaly, severity (the rule table), reasons, baseline, model; alert
  (grouping, states, automatic resolution), notification, incident, ground truth; Kafka topics with retention,
  partitions and keys, consumer groups and offsets, grace period and watermark, live feed.
- `docs/guide/how-detection-works.md`: the path of one log line in ten steps: reading, masking and Drain (with the
  similarity threshold), one-minute windows, the 38 features and why counts are log-scaled, PCA in plain words
  (normal space, what is left over = the score), training data, why PCA was chosen (Day 22 comparison), threshold
  and the score formula, the "no logs" rule, severity rules and the baselines of live-pca 1.1.0, when a minute is
  judged (grace, watermark, the minutes that are skipped), storing and committing, the delay formula with the live
  examples, limits, how the model was checked.
- The docs sidebar gets a **Learn** section.

## Checked against the code and data
- Masks, similarity 0.9 and depth 4 (`preprocessing/parser.py`); 31 templates, 38 features, threshold 9.90,
  training flag rate 0.11%, baselines and 1,785 training windows (`models/metadata/live-pca-1.1.0.json`); feature
  list (`features/extractor.py`); severity limits (`scoring/severity.py`); alert titles and grouping
  (`alerting/rules.py`, `alerting/store.py`); topic partitions and retention (`docker-compose.yml`); the model
  choice (devlog day 22, detection-design.md §4); delay examples (latency and improvements results).

## Next
- Day 46: using the dashboard, alerts and Telegram, operations.