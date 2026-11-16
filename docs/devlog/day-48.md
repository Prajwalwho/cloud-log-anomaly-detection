# Day 48 — Docs: Study guide and final check

## Written
- `docs/guide/study-guide.md`: the project in four sentences; a study plan in six sessions, each with the guide
  pages and code files to read and a "you can explain" checklist; the numbers to know with their sources; a
  12-minute demo script (preparation, ten steps with what to show and say, what to do if something goes wrong);
  likely questions with answers (the idea, the system, the results); the limits to mention; where to look things up.
- Docs sidebar: a **Study** section. The FAQ's "Next" leads to the study guide.
- `README.md`: status line (built, evaluated and documented; the final report comes next), the study guide in the
  documentation table, roadmap Phase 11 done and Phase 12 (final report) pending.

## Final check
- Every link and heading anchor in the 13 guide pages and the README resolves (script).
- Every `python -m` module, every script and every repository path named in the guide and the README exists.
- All 13 pages render in the in-app viewer without errors, and none is wider than a phone screen (390 px).
- Facts in the study guide checked against the sources it names: research results (`research-plan.md`), live
  evaluation (delay 52 s ± 7, precision 54.5% strict and 100% with reactions, 0 alerts outside incidents), load test
  (735 events/s, p95 0.71 s), PCA variance 0.95 (`models/pca.py`, `live_model.py`).

## Phase 11 done
The guide has 13 pages in five sections: Start here, Learn, Use, Reference, Study. The final report is next.