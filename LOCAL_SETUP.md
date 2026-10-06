# Local Whisper Setup

This file documents the customized Whisper Local installation on Vidar's Windows PC. The upstream project documentation remains in [README.md](README.md); this file covers the local GPU installation, NTNU text polishing, operational behavior, and maintenance workflow.

## What this installation does

Ordinary dictation uses this pipeline:

```text
Microphone audio
    -> local faster-whisper (large-v3-turbo, CUDA float16)
    -> language detection
       -> English: NTNU Kimi K2.6 Instant cleanup (two 2-second attempts)
          -> if both attempts fail: NTNU Qwen 3.8 27B fallback (one 3-second attempt)
       -> Norwegian: NTNU Borealis 27B cleanup
       -> other/unknown: no remote cleanup
    -> clipboard paste at the active cursor
```

Audio and speech recognition remain local. Only the completed text transcript is sent to NTNU for configured languages. If NTNU is unavailable, misconfigured, or returns no usable text, Whisper Local preserves and delivers the local transcript.

## Installation

| Item | Location/value |
|---|---|
| Repository | `C:\Dev\whisper-local` |
| Python environment | `C:\Dev\whisper-local\.venv` |
| Visible/manual launcher | `C:\Dev\whisper-local\whisper-local-user.cmd` |
| Background/restart launcher | `C:\Dev\whisper-local\whisper-local-autostart.vbs` |
| Start-menu/taskbar launcher | `C:\Dev\whisper-local\WhisperLocalLauncher.exe` (Start menu entry `Whisper Local`; rebuild with `tools\build-whisper-local-launcher.ps1`) |
| Windows login startup | HKCU `Run` value `WhisperLocal` -> `whisper-local-autostart.vbs` |
| Canonical configuration | `C:\Dev\whisper-local\local-config\` (source of truth, in Git) |
| Live configuration | `%APPDATA%\whisperkey\` (synced from `local-config\`) |
| NTNU credential | Windows user environment variable `NTNU_LLM_API_KEY` |
| Whisper model | `large-v3-turbo` |
| Inference | NVIDIA CUDA, `float16` |
| Recording | Push-to-talk |
| Preferred microphone | `HyperX Quadcast` by name on Windows WASAPI; Windows default if unavailable |

The launcher adds the CUDA, cuBLAS, and cuDNN DLL directories installed inside the virtual environment to `PATH`, then starts the editable Whisper Local installation.

At every startup, Whisper Local enumerates Windows WASAPI inputs and selects the
device whose name contains `HyperX Quadcast`. The preference is name-based rather
than a fixed device ID because Windows can renumber audio devices. If HyperX is not
available, startup continues with the Windows default microphone and records a
warning in `app.log`.

`WhisperLocalLauncher.exe` does the same as `whisper-local-user.cmd`, but has no console
window. Windows Search and the taskbar treat it as a normal app, which they don't do for a
`.cmd` script. Ignore any `whisper-local-launcher.cmd` search result under
`Documents\Codex\...`: that copy is obsolete.

## Where the configuration lives (read this first)

### One live folder: `%APPDATA%\whisperkey`

Whisper Local reads `user_settings.yaml`, `app_rules.yaml` and `profiles.yaml` from this
folder, and writes `app.log`, `transcripts.jsonl` and `stats.jsonl` to it.

**Codex desktop sees a different folder at the same path.** Codex is a Microsoft Store
(MSIX) app, so Windows redirects `%APPDATA%` for Codex and for every program Codex starts
into Codex's private folder:

```text
%LOCALAPPDATA%\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Roaming\whisperkey
```

A Whisper Local started by Codex therefore ran on different settings, logs and history
from one started by Explorer (login, Start menu). Agents reading "`%APPDATA%\whisperkey`"
from Codex and from Claude Code saw different files and reported contradictory results.
Since 2026-10-06:

- Whisper Local detects a start from inside an app package and hands the start to
  Explorer (`WhisperLocalLauncher.exe` or `whisper-local-autostart.vbs`), then exits.
  The log and console say `Started inside app package ...; Relaunching via Explorer`.
- `tools\sync_local_config.py --check` reports any `whisperkey` folder under
  `%LOCALAPPDATA%\Packages\` as drift.
- Agents restart Whisper Local only through Explorer:
  `explorer.exe "C:\Dev\whisper-local\whisper-local-autostart.vbs"`.

### `local-config\` is the source of truth

The live files are only seeded from `src\whisper_key\*.defaults.yaml` when they're missing,
and the app rewrites `user_settings.yaml` itself. Repo fixes to defaults never reach an
existing install, and hand edits to the live files get lost. So:

1. Change production settings in `local-config\` (`user_settings.yaml`, `app_rules.yaml`,
   `profiles.yaml`) and commit.
2. Apply them: `.venv\Scripts\python.exe tools\sync_local_config.py`. It backs up every
   file it replaces to `%APPDATA%\whisperkey\backups\` and keeps live-only extras such as
   a tray-chosen microphone ID.
3. Restart Whisper Local (tray **Restart**, or the Start menu).
4. Confirm: `.venv\Scripts\python.exe tools\sync_local_config.py --check` exits 0.

To change a setting from the tray or settings window, also copy the change into
`local-config\`, or `--check` will report it as drift.

### Dictation logs

| File | Contents | Use it for |
|---|---|---|
| `app.log` | Every pipeline step: hotkey, recording length, detected language, Whisper time, `OpenAI cleanup model=... elapsed ... outcome=... final=polished/raw` | Response times, which NTNU model ran, failures |
| `transcripts.jsonl` | One entry per dictation: `raw_text` (local Whisper), `text` (delivered), `language`, `app`, duration | Whether cleanup changed the text |
| `stats.jsonl` | Characters, duration and app per dictation (no model) | Usage statistics only |

### Verify the real install (do not skip)

Synthetic tests and a live PID aren't enough. After any configuration or startup change:

1. `tools\sync_local_config.py --check` exits 0.
2. The latest start in `%APPDATA%\whisperkey\app.log` shows `large-v3-turbo` and
   `Selected preferred input device: Microphone (HyperX Quadcast)`.
3. One messy English dictation produces an `OpenAI cleanup model=moonshotai/Kimi-K2.6-instant ... final=polished`
   line, and its `transcripts.jsonl` entry has `text` different from `raw_text`.
4. The text pastes into the foreground app.

### Incident 2026-10-06: two configs, silently stripped routes

- **Symptoms:** the `base` model and no NTNU cleanup when started at login or from the
  Start menu, webcam instead of HyperX, terminal paste "fixed repeatedly" but coming back.
  Codex reported cleanup working at the same time.
- **Cause 1:** the Codex/MSIX `%APPDATA%` split described above. The production settings,
  including the terminal-paste fix, lived only in Codex's private copy.
- **Cause 1b, no autostart at login (2026-09-24 to 2026-10-06):** MSIX apps also get a
  private copy of the **registry**. On 2026-09-23 Codex replaced the Scheduled Task with the
  `WhisperLocal` Run entry, but wrote it from inside Codex, into Codex's private hive
  (`%LOCALAPPDATA%\Packages\OpenAI.Codex_...\SystemAppData\Helium\User.dat`). Its own
  `repair-local-startup.ps1 -Check` ran in the same sandbox and passed. At login Windows saw
  no Run entry, and nothing started. The real log shows starts at every login until
  2026-09-23 and none at the logins on 09-29, 10-01 and 10-06. The real Run entry was first
  written on 2026-10-06 20:04. `sync_local_config.py --check` now verifies the Run entry from
  an unsandboxed process. **Never run the startup repair from inside Codex.**
- **Cause 2:** `config_manager` dropped `postprocess.openai_compatible.routes` and
  `postprocess.corrections` whenever the app saved settings (tray microphone or model
  change, profile apply, GPU onboarding), because their defaults are empty maps.
- **Fixes:** routes and corrections are now kept on save (`EXTENSIBLE_PATHS`); the app
  relaunches outside app packages; `local-config\` plus `tools\sync_local_config.py`; the
  Codex copy's history was merged into the real `transcripts.jsonl`/`stats.jsonl` and the
  folder retired as `whisperkey.migrated-<timestamp>`.

## Normal use

Hold `Ctrl+Win`, dictate, and release the keys. Whisper transcribes locally and the language router applies the appropriate cleanup before pasting.

### Starting and restarting on Windows

- For a manual start with a visible diagnostic console, double-click `whisper-local-user.cmd`.
- For startup, background launches, or restarts initiated by an automation/assistant, run `explorer.exe "C:\Dev\whisper-local\whisper-local-autostart.vbs"`. Going through Explorer keeps the app out of an agent's app-package container (see "Where the configuration lives"); a direct `wscript.exe` call from Codex would start inside it.
- The `WhisperLocal` value in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` is the sole login-start mechanism. It launches the VBS wrapper from Explorer's interactive user session. The older `Whisper Local` value and Scheduled Task `\WhisperLocal` must remain absent.
- Check the durable startup state with `powershell -ExecutionPolicy Bypass -File tools\repair-local-startup.ps1 -Check`. Run the same command without `-Check` to restore the exact Run value and remove the obsolete task and legacy Run value.
- On 2026-09-16 and again on 2026-09-23, the Scheduled Task produced a Python process with CUDA and audio modules loaded, but current dictations did not reach the PID/log/history and simulated paste failed. Starting the same VBS launcher in the interactive session immediately restored transcription, language cleanup, and paste. This is why Task Scheduler is no longer used here. *Correction (2026-10-06):* this diagnosis was most likely wrong. The real `%APPDATA%` log shows the task-started instances initialising normally on both mornings. They were probably healthy but invisible to Codex, which read its private copy of the log (see "Where the configuration lives"). The Run entry works equally well, so it stays.
- Do not leave the production instance attached to a retained automation terminal/PTY. On 2026-09-09, that process completed initialization and reported all hotkeys configured, but it did not receive physical Windows hotkey input. Relaunching through the VBS background launcher restored `Ctrl+Win`; the app log and a complete dictation verified the recovery.

After an automated restart, do not treat a live PID or “Whisper Local ready” as sufficient verification. Confirm one physical `Ctrl+Win` dictation reaches the app log and is pasted into the foreground application.

### English cleanup

- Model: `moonshotai/Kimi-K2.6-instant`
- Transport policy: try Kimi twice with a 2-second timeout per attempt, then try
  `Qwen/Qwen3.8-27B-FP8` once with a 3-second timeout. If all three attempts fail,
  deliver the raw local Whisper transcript.
- Each request attempt logs its model, role, attempt number, elapsed milliseconds,
  and outcome. The final log entry identifies whether polished or raw text was used.
- Intended for AI prompts, email/messages, and ordinary prose.
- Improves clarity and logical flow.
- Shortens redundant wording and removes fillers, false starts, stutters, and accidental repetitions.
- Makes actions, context, constraints, and desired output clearer in AI instructions.
- Adds paragraphs or bullets only when structure materially improves readability.
- Preserves intent, tone, uncertainty, technical terms, identifiers, commands, paths, URLs, and code.
- Must edit the transcript, not answer or execute it.
- If the cleanup model nevertheless returns an assistant-style reply or turns a
  short dictation into a substantially longer response, Whisper Local rejects
  that output and retries the same raw text once with a corrective system
  prompt. It accepts the retry only if it passes the same guard; otherwise it
  delivers the local transcript. This guard was added after Kimi answered three
  short "Please see this transcript ..." dictations on 2026-10-01 rather than
  transcribing them.

### Norwegian cleanup

- Model: `NbAiLab/borealis-27b`
- Normalizes dialectal Norwegian to Bokmål.
- Removes fillers and accidental repetition and improves sentence structure.
- Preserves English technical terminology and identifiers.

### Other languages

No NTNU model is called. The local Whisper transcript is delivered unchanged apart from deterministic local formatting configured by Whisper Local.

## Other hotkeys and tray features

| Feature | Current behavior |
|---|---|
| `Ctrl+Win` | Normal automatic dictation and language-routed cleanup |
| `Ctrl+Shift+Win` | Rephrases selected existing text from a spoken instruction; currently requires Ollama and is not connected to NTNU |
| Transforms | Rewrite selected existing text using fixed prompts; currently require Ollama |
| Profiles | Apply persistent groups of Whisper/clipboard settings; unrelated to automatic LLM cleanup |

The tray normally displays the `Dictation` profile because `profiles.yaml` contains `active: dictation`. The canonical profiles live in `local-config\profiles.yaml`. The Dictation profile keeps `large-v3-turbo`, restricts language detection to English and Norwegian, and prefers English when detection is uncertain. The `Notes` profile still specifies the smaller `base` model and should not be selected for normal dictation.

## Privacy and disabling remote cleanup

With cleanup enabled, English and Norwegian transcript text may contain sensitive prompts, code, names, or messages and is sent to the NTNU endpoint. Audio is not sent.

To disable all NTNU cleanup, edit `%APPDATA%\whisperkey\user_settings.yaml`:

```yaml
postprocess:
  openai_compatible:
    enabled: false
```

The `postprocess` section hot-reloads, so this takes effect on the next dictation without restarting the app. Set `enabled: true` to restore the configured routes.

Never store the actual API key in YAML or commit it to Git. The configuration stores only the environment-variable name.

## Diagnostics and tests

From PowerShell:

```powershell
Set-Location C:\Dev\whisper-local
& .\whisper-local-user.cmd --doctor
& .\.venv\Scripts\python.exe -m unittest discover -s tests
& .\.venv\Scripts\python.exe tools\sync_local_config.py --check
git diff --check
```

Last verified after the interactive-login startup repair: 188 tests passed, with 4 platform-specific skips. Synthetic installed-configuration checks confirmed:

- English selects `moonshotai/Kimi-K2.6-instant`.
- Norwegian selects `NbAiLab/borealis-27b`.
- An unconfigured language sends zero NTNU requests.
- Both configured routes preserve the local transcript when the provider fails.

## Local source changes

The customization adds:

- An OpenAI-compatible Chat Completions provider in `text_postprocess.py`.
- Language metadata propagation from faster-whisper through `whisper_engine.py` and `state_manager.py`.
- Explicit language-to-model routes with fail-closed behavior for unknown languages.
- Configuration schema entries and regression tests for provider routing and fallback.
- `whisper-local-user.cmd` for the project-local NVIDIA runtime DLLs.

The production settings are versioned in `local-config\` (no secrets) and synced to `%APPDATA%\whisperkey`. The NTNU key and the private transcript history stay outside Git.

## Git and upstream updates

This directory is already a Git repository cloned from `drajb/whisper-local`. Keep the customization on the `local/ntnu-polish` branch and publish that branch to a personal fork. Recommended remotes:

```text
origin    -> Vidar's fork
upstream  -> https://github.com/drajb/whisper-local.git
```

When upstream changes:

```powershell
Set-Location C:\Dev\whisper-local
git fetch upstream
git switch local/ntnu-polish
git merge upstream/master
& .\.venv\Scripts\python.exe -m unittest discover -s tests
git diff --check
```

Most upstream updates will merge automatically. Git stops and marks conflicts if both branches changed the same lines, especially in `text_postprocess.py`, `state_manager.py`, `whisper_engine.py`, configuration defaults, or smoke tests. Resolve those conflicts while preserving language routing and raw-transcript fallback, rerun the full suite, and only then push the updated branch.

Do not push custom changes directly to the upstream repository. Use the personal fork for backup and collaboration; keep the original repository as the `upstream` remote.

## Recovery

- NTNU unavailable: local transcripts are delivered automatically.
- Bad cleanup behavior: set `postprocess.openai_compatible.enabled: false`.
- App will not start: run `whisper-local-user.cmd --doctor` from a visible PowerShell window.
- Deliberate silence is not a microphone fault. A normal silent test logs the hotkey press/release, about 0.5 seconds of retained pre-roll, and `VAD check: SILENCE`, with no transcript produced.
- A dead continuous-audio stream can leave the Python process, tray icon, and hotkeys alive while Windows no longer shows the microphone-in-use icon. The verified 2026-09-11 signature was: a spoken attempt logged `Starting audio recording` and `Push-to-talk key released`, but no subsequent resampling, recorded-duration, VAD, or transcription entry. A silent recording being trimmed to the 0.5-second pre-roll is normal and does not establish this failure by itself. Confirm that the configured input device still exists, then restart through `explorer.exe "C:\Dev\whisper-local\whisper-local-autostart.vbs"` and verify one physical spoken `Ctrl+Win` dictation. The underlying event that stopped the PortAudio callback was not captured in the log; do not claim the user's deliberate silence caused it.
- Repeated failure specifically after Windows login: run `tools\sync_local_config.py --check` and `tools\repair-local-startup.ps1 -Check` from a normal terminal (never from Codex, whose registry view is private). The required state is one exact `WhisperLocal` registry Run value and no `\WhisperLocal` Scheduled Task. Before the 2026-09-14 mutex fix, duplicate launches leaked a mutex handle; later testing also showed Task Scheduler could create a fully loaded but non-functional process outside the effective interactive input path. A PID, GPU allocation, or tray icon alone does not prove that instance is healthy; `app.log` must contain a current initialization sequence and one physical dictation must paste successfully.
- Configuration problem: run `tools\sync_local_config.py --check`; repair with `tools\sync_local_config.py`. Earlier versions of each replaced file are in `%APPDATA%\whisperkey\backups\`.
- Code regression after an upstream merge: return to the last known-good commit on `local/ntnu-polish`; do not use destructive Git reset commands while uncommitted work exists.
- Unexpected `base` model, no cleanup, or the wrong microphone: run `tools\sync_local_config.py --check` first. It also catches a second config folder inside an app package (the 2026-10-06 incident). Then check the active profile in `profiles.yaml`. The local `Dictation` profile must preserve `large-v3-turbo`, `allowed_languages: [en, no]`, and `fallback_language: en`.
