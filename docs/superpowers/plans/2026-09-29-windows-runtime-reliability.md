# Windows Runtime Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local Windows installation start observably after login and recover automatically from application exits and dead audio callbacks.

**Architecture:** A non-elevated Startup-folder entry launches a single per-user supervisor, which records bootstrap evidence and restarts the exact local application with backoff. The application publishes local health and first attempts to reopen a stale audio stream internally; unrecoverable failure exits into the supervisor's recovery path.

**Tech Stack:** PowerShell 7/Windows PowerShell, VBScript/WScript, Python 3.12, `unittest`, PortAudio through `sounddevice`, Windows per-user Startup folder.

**Spec:** `docs/design/windows-runtime-reliability.md`

## Global Constraints

- Keep all runtime data local under `%APPDATA%\whisperkey`.
- Run in the non-elevated interactive user session; do not use a Windows service or Scheduled Task.
- Preserve `C:\Dev\whisper-local\whisper-local-user.cmd` as the CUDA-aware application launcher.
- Never terminate a PID unless its executable or command line is verified as belonging to this checkout.
- Preserve user settings, transcripts, the `NTNU_LLM_API_KEY` environment-variable boundary, and current language/model routing.
- A PID, tray icon, or ready message alone is not acceptance evidence.

## Review Focus

- A stale PID file names an unrelated reused PID: the supervisor must not terminate it and must launch only after resolving application ownership safely.
- Model initialization exceeds the ordinary check interval: startup grace prevents premature restart loops.
- The app repeatedly crashes: bounded exponential backoff prevents a tight loop and logs every attempt.
- PortAudio is quiet because the user is not speaking: continuous callback heartbeat remains current and is not confused with VAD silence.
- Sleep causes wall-clock jumps: callback staleness and recovery remain safe across suspend/resume.

---

### Task 1: Testable Supervisor Policy

**Files:**
- Create: `tools/whisper-local-supervisor.ps1`
- Create: `tests/test_windows_supervisor.py`

**Interfaces:**
- Consumes: repository launcher path and `%APPDATA%\whisperkey\WhisperKeyLocal.pid`.
- Produces: supervisor entry point with `-Once`, `-StateRoot`, and `-ProjectRoot` test seams; `%APPDATA%\whisperkey\supervisor.log`.

- [ ] **Step 1: Write failing policy tests** for single-instance ownership, missing-process launch, correct-process no-op, wrong/stale PID safety, startup grace, exponential backoff, and bounded log growth using temporary state/project roots.
- [ ] **Step 2: Run `C:\Dev\whisper-local\.venv\Scripts\python.exe -m unittest tests.test_windows_supervisor -v` and confirm failures are caused by the missing supervisor behavior.**
- [ ] **Step 3: Implement the minimal supervisor** with an injectable one-cycle mode, exact checkout verification, named mutex, immediate logging, and backoff.
- [ ] **Step 4: Re-run the focused tests and confirm they pass.**
- [ ] **Step 5: Commit supervisor behavior and tests.**

### Task 2: Durable Interactive Startup Registration

**Files:**
- Modify: `tools/repair-local-startup.ps1`
- Modify: `whisper-local-autostart.vbs`
- Modify: `tests/test_windows_supervisor.py`

**Interfaces:**
- Consumes: Task 1 supervisor entry point.
- Produces: exact per-user Startup-folder launcher; idempotent `-Check` and repair behavior.

- [ ] **Step 1: Add failing tests** that assert Startup-folder launcher generation, current-checkout targeting, idempotence, and rejection/removal of both registry Run values and the obsolete Scheduled Task.
- [ ] **Step 2: Run the focused test module and confirm the new assertions fail against the registry-only implementation.**
- [ ] **Step 3: Update the repair script** to install the interactive Startup-folder entry, remove old registrations, and report the launcher and supervisor-log paths separately from runtime status.
- [ ] **Step 4: Re-run the focused tests and confirm they pass.**
- [ ] **Step 5: Commit startup registration and tests.**

### Task 3: Audio Callback Health and Recovery

**Files:**
- Modify: `src/whisper_key/audio_recorder.py`
- Create: `src/whisper_key/runtime_health.py`
- Create: `tests/test_audio_recovery.py`

**Interfaces:**
- Consumes: audio callback events and existing stream open/close operations.
- Produces: `RuntimeHealth` atomic health writer; serialized callback-staleness monitor; bounded reopen-or-exit behavior.

- [ ] **Step 1: Add failing tests** for atomic health output, fresh callback no-op, stale callback reopen, single recovery under concurrent checks, successful recovery, bounded failed recovery, VAD silence distinction, and suspend/resume clock behavior.
- [ ] **Step 2: Run `C:\Dev\whisper-local\.venv\Scripts\python.exe -m unittest tests.test_audio_recovery -v` and confirm failures reflect missing health/recovery behavior.**
- [ ] **Step 3: Implement `RuntimeHealth`** with monotonic in-process timing and atomic JSON replacement containing only PID/status/timestamps.
- [ ] **Step 4: Integrate callback heartbeat and serialized stream recovery** into `AudioRecorder`, exiting only after the configured bounded attempts fail.
- [ ] **Step 5: Re-run focused tests and confirm they pass.**
- [ ] **Step 6: Commit audio recovery and tests.**

### Task 4: Installation, Documentation, and Acceptance

**Files:**
- Modify: `AGENTS.md`
- Modify: `LOCAL_SETUP.md`
- Modify: `docs/design/windows-runtime-reliability.md`

**Interfaces:**
- Consumes: Tasks 1-3 and the local Windows installation.
- Produces: installed startup entry, documented recovery path, and recorded acceptance evidence.

- [ ] **Step 1: Run the full suite:** `C:\Dev\whisper-local\.venv\Scripts\python.exe -m unittest discover -s tests` and require zero failures.
- [ ] **Step 2: Run `git diff --check` and the startup checker; require clean output and an exact Startup-folder installation.**
- [ ] **Step 3: Install the repaired startup mechanism and run the supervisor once; confirm current bootstrap, health, PID, and initialization evidence.**
- [ ] **Step 4: Update operator documentation** to replace the registry-only rule and explain supervisor/health logs without promising success before acceptance tests.
- [ ] **Step 5: Commit and push the implementation branch.**
- [ ] **Step 6: Reboot/log in and perform the five physical acceptance tests from the spec, recording actual results.**

Implementation is complete only after automated verification and the post-reboot physical acceptance tests both pass.
