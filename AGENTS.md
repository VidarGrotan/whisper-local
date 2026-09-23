# Agent instructions

Before starting work in this repository, read `LOCAL_SETUP.md` in full. Treat it as the source of truth for this computer's installed Whisper Local configuration, privacy boundary, NTNU cleanup routing, language handling, testing, update workflow, and recovery procedures.

In particular, before starting, restarting, or troubleshooting the running Windows application:

- Use `whisper-local-user.cmd` only for a manual start with a visible diagnostic console.
- Use `whisper-local-autostart.vbs` through `wscript.exe` for background, startup, or agent-initiated restarts.
- Keep the `WhisperLocal` registry `Run` value as the only login-start mechanism so Explorer starts the app in the user's interactive session. The `\WhisperLocal` Scheduled Task must remain absent. Use `tools\repair-local-startup.ps1` to inspect or restore this state.
- Do not leave the production instance attached to an agent's retained terminal or PTY.
- Do not infer success from a live PID or the “Whisper Local ready” message alone. Verify one physical `Ctrl+Win` dictation reaches the app log and auto-pastes into the foreground application.

Preserve user settings and transcript history under `%APPDATA%\whisperkey`. Never copy the NTNU API key into repository files; configuration must refer only to the `NTNU_LLM_API_KEY` Windows environment variable.
