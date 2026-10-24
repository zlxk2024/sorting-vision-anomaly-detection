# Realtime camera detection Implementation Plan


**Goal:** Deliver configurable live camera detection, incremental anomaly rules, durable database writes and evidence, then publish to the existing GitHub repository.

**Architecture:** Each camera has a bounded latest-frame capture buffer, one persistent YOLO/ByteTrack adapter and a time-based rule engine. Events are first stored in a local SQLite outbox, then retried idempotently into PostgreSQL/MySQL/SQLite. A separate HTTP server exposes readiness, camera state, events and evidence.

**Tech Stack:** Python, OpenCV, Ultralytics, SQLAlchemy 2, psycopg, PyMySQL, SQLite, Docker.

**Spec:** This chat: configurable camera/database integration with live detection and database results; preserve existing offline API and publish code, config and technical evidence only.

## Global Constraints

- Credentials and camera URLs use environment variables; no business data or credentials committed.
- Missing target chute information produces visual candidates, not confirmed business mis-sorts.
- Latest-frame queue size is one. Rules use elapsed seconds and normalized geometry.
- Existing offline service and model hashes remain unchanged.
- Field cameras/database credentials are unavailable; test local RTSP and isolated databases and disclose this boundary.

## Review Focus

- Lost frames/reconnects must reset temporal and tracker state without reusing stale images.
- Moving parcels or successive parcels must not trigger stationary-parcel rules.
- Database outages must preserve events across restart and avoid duplicate rows after retry.
- Evidence queues and frame history must be bounded, and evidence failures must be explicit.
- Configuration errors, missing secrets and partial readiness must be observable without exposing URLs.

### Task 1: Configuration and incremental rules

**Files:** `sorting_vision/live_config.py`, `sorting_vision/live_rules.py`, `tests/test_live_rules.py`, `config/realtime.example.yaml`.

- [x] Define validated configuration and environment-only connection values.
- [x] Test time-based anomaly onset/clear, normalized ROI assignment, moving parcels, unknown targets, gaps and reconnects.
- [x] Implement incremental rule events with stable event IDs and review status.

### Task 2: Durable database delivery

**Files:** `sorting_vision/event_store.py`, `tests/test_event_store.py`, `requirements-realtime.txt`.

- [x] Implement event/status schemas, local revisioned outbox, idempotent target writes and bounded retry.
- [x] Test outage/restart/replay, concurrent update/ack and duplicate delivery with SQLite.
- [x] Verify real PostgreSQL against isolated Docker; MySQL driver implemented, live instance blocked by repeated official-image TLS failures and explicitly documented.

### Task 3: Camera service, evidence and HTTP

**Files:** `sorting_vision/live_capture.py`, `sorting_vision/live_evidence.py`, `sorting_vision/realtime.py`, `tests/test_live_capture.py`.

- [x] Capture latest frames with timeout, reconnect, session boundaries and file playback fixtures.
- [x] Keep the model loaded; store bounded pre/post evidence and heartbeat.
- [x] Expose readiness/status/event/evidence endpoints with existing API key convention.
- [x] Verify real YOLO on local RTSP, stream interruption/recovery, event database persistence and playable evidence.

### Task 4: Deploy and publish

**Files:** `compose.realtime.yaml`, `.env.example`, `docs/REALTIME.md`, `docs/REALTIME_VERIFICATION.md`, `README.md`.

- [x] Document configuration, ROI calibration, schema ownership and remaining field acceptance.
- [x] Build/run the real Docker service; retain only technical test results in Git.
- [x] Review upload scope, push normally, and verify remote commit and fresh clone checks.
