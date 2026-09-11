# Local Whisper Setup

This file documents the customized Whisper Local installation on Vidar's Windows PC. The upstream project documentation remains in [README.md](README.md); this file covers the local GPU installation, NTNU text polishing, operational behavior, and maintenance workflow.

## What this installation does

Ordinary dictation uses this pipeline:

```text
Microphone audio
    -> local faster-whisper (large-v3-turbo, CUDA float16)
    -> language detection
       -> English: NTNU Kimi K2.6 Instant cleanup
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
| Windows login startup | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `Whisper Local` |
| User settings | `%APPDATA%\whisperkey\user_settings.yaml` |
| NTNU credential | Windows user environment variable `NTNU_LLM_API_KEY` |
| Whisper model | `large-v3-turbo` |
| Inference | NVIDIA CUDA, `float16` |
| Recording | Push-to-talk |

The launcher adds the CUDA, cuBLAS, and cuDNN DLL directories installed inside the virtual environment to `PATH`, then starts the editable Whisper Local installation.

## Normal use

Hold `Ctrl+Win`, dictate, and release the keys. Whisper transcribes locally and the language router applies the appropriate cleanup before pasting.

### Starting and restarting on Windows

- For a manual start with a visible diagnostic console, double-click `whisper-local-user.cmd`.
- For startup, background launches, or restarts initiated by an automation/assistant, launch `whisper-local-autostart.vbs` with `wscript.exe`.
- The per-user Windows `Run` entry named `Whisper Local` must point to `wscript.exe "C:\Dev\whisper-local\whisper-local-autostart.vbs"`. Check this entry when the app does not start after login.
- Do not leave the production instance attached to a retained automation terminal/PTY. On 2026-09-09, that process completed initialization and reported all hotkeys configured, but it did not receive physical Windows hotkey input. Relaunching through the VBS background launcher restored `Ctrl+Win`; the app log and a complete dictation verified the recovery.

After an automated restart, do not treat a live PID or “Whisper Local ready” as sufficient verification. Confirm one physical `Ctrl+Win` dictation reaches the app log and is pasted into the foreground application.

### English cleanup

- Model: `moonshotai/Kimi-K2.6-instant`
- Intended for AI prompts, email/messages, and ordinary prose.
- Improves clarity and logical flow.
- Shortens redundant wording and removes fillers, false starts, stutters, and accidental repetitions.
- Makes actions, context, constraints, and desired output clearer in AI instructions.
- Adds paragraphs or bullets only when structure materially improves readability.
- Preserves intent, tone, uncertainty, technical terms, identifiers, commands, paths, URLs, and code.
- Must edit the transcript, not answer or execute it.

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

The tray normally displays the `Dictation` profile because `profiles.yaml` contains `active: dictation`. This installation customizes that profile to preserve `large-v3-turbo`, restrict language detection to English and Norwegian, and prefer English when detection is uncertain. The `Notes` profile still specifies the smaller `base` model and should not be selected for normal dictation.

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
git diff --check
```

Last verified after the durable Dictation-profile repair: 186 tests passed, with 4 platform-specific skips. Synthetic installed-configuration checks confirmed:

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

The user settings under `%APPDATA%` are deliberately outside Git. This repository contains the implementation and safe configuration schema, not the NTNU key or private transcript history.

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
- A dead continuous-audio stream can leave the Python process, tray icon, and hotkeys alive while Windows no longer shows the microphone-in-use icon. The verified 2026-09-11 signature was: a spoken attempt logged `Starting audio recording` and `Push-to-talk key released`, but no subsequent resampling, recorded-duration, VAD, or transcription entry. A preceding long silent test also contained only the 0.5-second pre-roll because no new samples were arriving. Confirm that the configured input device still exists, then restart through `wscript.exe "C:\Dev\whisper-local\whisper-local-autostart.vbs"` and verify one physical spoken `Ctrl+Win` dictation. The underlying event that stopped the PortAudio callback was not captured in the log; do not claim the user's deliberate silence caused it.
- Configuration problem: compare `%APPDATA%\whisperkey\user_settings.yaml` with its local backup files before resetting anything.
- Code regression after an upstream merge: return to the last known-good commit on `local/ntnu-polish`; do not use destructive Git reset commands while uncommitted work exists.
- Unexpected `base` model or unrestricted language output: check both `user_settings.yaml` and the active profile in `profiles.yaml`. The local `Dictation` profile must preserve `large-v3-turbo`, `allowed_languages: [en, no]`, and `fallback_language: en`.
