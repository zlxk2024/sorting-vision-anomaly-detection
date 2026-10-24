# Windows Field Test Implementation Plan

**Goal:** Provide a Windows GPU field runbook and independent camera/model/database/status checks for ToDesk-assisted deployment.
**Architecture:** Native Python 3.11 + CUDA PyTorch; environment files loaded as data without interpolation. Separate preflight commands isolate video, model and SQL failures before the existing real-time service starts.
**Tech Stack:** Python, python-dotenv, OpenCV, Ultralytics, SQLAlchemy, Windows CMD/PowerShell.
**Spec:** User asks how to deploy and test on the Windows/RTX3060 industrial PC, and compare ToDesk with Windows App.

## Constraints and review focus
- No actual camera IP or remote-PC access is available; local checks cannot certify Windows/CUDA or field-camera acceptance.
- Never persist operational credentials in tracked files, output URLs/passwords, or automatically execute remote DDL.
- Database probe is read-only by default; explicit CRUD testing must roll back and never commit synthetic business events.
- CUDA must be explicitly selected and unavailable GPUs must fail visibly.
- Camera decoding alone and model detection alone do not establish anomaly accuracy or durable live database delivery.

### Task 1: Runtime configuration
- [x] Add literal `.env` loading to CLI without shell execution or interpolation.
- [x] Add credential wizard, GPU Windows example config, ignored local config and foreground launch script.
- [x] Verify escaped credentials, literal values and refusal to overwrite an existing file.

### Task 2: Independent diagnostic commands
- [x] Implement camera decode + optional screenshot, one-image model test, SQL/schema/rollback CRUD probe, and local API readiness query.
- [x] Verify secret-safe failure output and rollback CRUD in an isolated local SQLite database.
- [x] Decode a real local test video and run the actual model on the captured frame.

### Task 3: Field instructions and publish
- [x] Document ToDesk vs Windows App, native CUDA installation, each pass condition, DBA setup, ROI calibration and long-run acceptance.
- [x] Run regression, model hash checks and upload-scope audit; push and verify remote SHA.
