# Day 0 — Environment and Structure Cleanup

## Completed Tasks

- Switched the backend virtual environment to Python 3.12.
- Recreated the virtual environment using Python 3.12.
- Replaced pip-freeze requirements with separate service requirements files.
- Added the root `requirements-dev.txt`.
- Installed and verified all development dependencies.
- Updated `.gitignore` to preserve `.gitkeep` placeholders.
- Removed unused Vite starter assets and demo styling.
- Verified the frontend production build successfully.
- Renamed `ingestion/log_parser.py` to `ingestion/validator.py`.
- Created `tests/unit/`, `docs/devlog/`, and `docs/design/`.
- Added the API Dockerfile.
- Updated the system architecture documentation.

## Architecture Decisions

- Ingestion and detection operate as independent services.
- Both services consume `logs.raw` using separate Kafka consumer groups.
- Kafka topics: `logs.raw`, `logs.deadletter`, and `anomalies.detected`.
- Live anomaly detection uses fixed 60-second windows per service.
- Benchmark datasets use dataset-appropriate sessions or sliding windows.
- Drain3 template extraction belongs to the detection service.

## Verification

- Python version: 3.12.10
- Python dependency imports: All OK
- Frontend production build: Successful

## Problems Faced

- No blocking issues reported during the completed steps.