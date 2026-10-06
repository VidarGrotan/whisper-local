# Agent instructions

Before starting work in this repository, read `LOCAL_SETUP.md` in full. Treat it as the source of truth for this computer's installed Whisper Local configuration, privacy boundary, NTNU cleanup routing, language handling, testing, update workflow, and recovery procedures.

In particular, before starting, restarting, or troubleshooting the running Windows application:

- Use `whisper-local-user.cmd` only for a manual start with a visible diagnostic console.
- For background or agent-initiated restarts run `explorer.exe "C:\Dev\whisper-local\whisper-local-autostart.vbs"`. Never start the app directly from an agent shell: Codex desktop is an MSIX app, and anything it starts gets a private, redirected `%APPDATA%` (see "Where the configuration lives" in `LOCAL_SETUP.md`).
- Keep the `WhisperLocal` registry `Run` value as the only login-start mechanism so Explorer starts the app in the user's interactive session. The `\WhisperLocal` Scheduled Task must remain absent. Use `tools\repair-local-startup.ps1` to inspect or restore this state.
- Do not leave the production instance attached to an agent's retained terminal or PTY.
- Do not infer success from a live PID or the “Whisper Local ready” message alone. Verify one physical `Ctrl+Win` dictation reaches the app log and auto-pastes into the foreground application.

Configuration:

- `local-config\` is the source of truth for production settings. Change settings there, apply them with `tools\sync_local_config.py`, and never edit only the live `%APPDATA%\whisperkey` files.
- Before claiming the install works, run `.venv\Scripts\python.exe tools\sync_local_config.py --check` (it must exit 0), then verify a real dictation in the live `app.log` and `transcripts.jsonl`.
- MSIX apps such as Codex desktop also get a private copy of the HKCU registry. A login Run entry written or checked from inside one doesn't exist for Windows. Run `tools\repair-local-startup.ps1` only from an unsandboxed terminal.
- If what you read under `%APPDATA%\whisperkey` contradicts another agent, check for the app-package copy under `%LOCALAPPDATA%\Packages\*\LocalCache\Roaming\whisperkey` before arguing.

Before proposing changes to models, cleanup prompts or audio processing, read "Decisions (2026-10-06)" in `LOCAL_SETUP.md`. NB-Whisper, Borealis, harder condensing and noise reduction were tested on the user's own dictations and rejected; don't propose them again without new evidence.

Development notes:

- Never open a Tk window on a thread inside the running app; the level overlay's Tk thread makes its buttons silently stop working. Run it as a separate process with a `main.py` flag, like `--settings`, `--history` and `--add-word-dialog`.
- Scripts that use the GPU outside the launchers must prepend `.venv\Lib\site-packages\nvidia\{cuda_runtime,cublas,cudnn}\bin` to `PATH`, or CTranslate2 fails with `cublas64_12.dll is not found`.
- To evaluate cleanup models or prompts, use the `raw_text` of real dictations in `%APPDATA%\whisperkey\transcripts.jsonl`; no recording tool is needed. Never put words from the test dictations into a prompt's examples, or the test only measures copying. Check results on dictations the prompt wasn't written for.
- Cleanup prompts change only for repeated patterns, never for a single mistake. Prefer hotwords for recurring misheard words.

Preserve user settings and transcript history under `%APPDATA%\whisperkey`. Never copy the NTNU API key into repository files; configuration must refer only to the `NTNU_LLM_API_KEY` Windows environment variable.
