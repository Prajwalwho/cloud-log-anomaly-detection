# Day 13 — Template extraction with Drain

## Done
- backend/detection/preprocessing/parser.py: Drain template miner with masking (BLK, IP, UUID, HEX, PATH, NUM),
  shared by the offline experiments and the future live detection service.
- tests/unit/test_parser.py: 7 tests (masking, separation of different messages, path masking, strict threshold,
  generator messages, counts).
- experiments/parse_hdfs.py: streams HDFS.log through Drain, writes templates, per-block event sequences
  (chronological) and run metadata to data/processed/ (not committed).
- experiments/notebooks/02_hdfs_templates.ipynb: template list, comparison with the dataset authors' templates,
  template presence in normal vs anomalous blocks, repetitiveness of behaviour.

## Parser tuning (threshold experiment on the first 200,000 lines)

| Similarity threshold | Templates | Result |
|---|---|---|
| 0.5 | 25 | "PacketResponder ... <*>" and "writeBlock ... received exception <*>" merged different messages |
| 0.7 | 25 | identical to 0.5 (merged messages are 0.8 similar: 4 of 5 words equal) |
| 0.9 | 27 | the two merges split ("terminating"/"Interrupted.", "SocketTimeoutException"/"EOFException"); all other templates unchanged |

Chosen: 0.9. Masking removes variable values first, so a strict threshold separates messages that differ in a
real word without fragmenting templates. A PATH mask was added for file paths.

## Results (full run)
- 11,175,629 lines in 127 s (~88,000 lines/s), 0 unparsed, 575,061 blocks, 53 templates
  (count stable from ~9 M lines).
- allocateBlock occurs 575,061 times = number of blocks (sanity check).
- Reference comparison: 22 of 29 reference templates matched closely; the others are coarser in the reference
  (one template per message family instead of per exception type). All reference templates are covered.

| Template | In normal blocks | In anomalous blocks |
|---|---|---|
| #3 PacketResponder ... terminating | 100% | 63.29% |
| #4 Received block ... of size ... | 100% | 63.14% |
| #5 addStoredBlock: blockMap updated | 100% | 63.14% |
| #35 Unexpected error trying to delete block | 0.04% | 30.44% |
| #16 writeBlock ... Could not read from stream | 0% | 19.16% |
| #36 addStoredBlock ... does not belong to any file | 0% | 7.41% |
| #21 Redundant addStoredBlock request | 0% | 5.77% |
| #18 Receiving empty packet | 0% | 2.90% |
| #26 PacketResponder ... Interrupted. | 0% | 0.27% |

| | Blocks | Distinct count vectors | Distinct ordered sequences |
|---|---|---|---|
| Normal | 558,223 | 212 | 14,259 |
| Anomaly | 16,838 | 394 | 4,126 |

## Findings
- ~37% of anomalous blocks lack the "write completed" events (#3, #4, #5): writes that never finished.
- 41 of 53 templates never appear in normal blocks; several are strong anomaly signals.
- "Interrupted." appears only in anomalies; it would have been hidden at threshold 0.5.
- Normal behaviour is concentrated in very few event-count patterns (212), which suits unsupervised
  novelty detection. Ordered sequences vary much more (interleaved parallel writes), supporting count vectors
  as the representation.
- Our templates are finer than the reference (exception types kept separate); the effect of granularity can be
  tested as part of RQ2.

## Caution for the experiments
- Template statistics above use all labels. In experiments, any "seen/unseen template" information must be
  derived from the training split only (no label leakage).

## Problems faced
- First quick check at threshold 0.5 merged semantically different messages; fixed by masking paths and
  raising the threshold to 0.9 after a three-value comparison.