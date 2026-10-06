# local-config

The production Whisper Local configuration for this PC. These files are the source of truth;
`%APPDATA%\whisperkey` is a synced copy. See "Where the configuration lives" in
[`../LOCAL_SETUP.md`](../LOCAL_SETUP.md) for the reasons.

| File | Synced to |
|---|---|
| `user_settings.yaml` | `%APPDATA%\whisperkey\user_settings.yaml` (merged; live-only extras are kept) |
| `app_rules.yaml` | `%APPDATA%\whisperkey\app_rules.yaml` (replaced) |
| `profiles.yaml` | `%APPDATA%\whisperkey\profiles.yaml` (replaced; the active profile is kept) |

```powershell
.\.venv\Scripts\python.exe tools\sync_local_config.py --check   # report drift, exit 1 if any
.\.venv\Scripts\python.exe tools\sync_local_config.py           # apply, with backups in %APPDATA%\whisperkey\backups
```

No secrets belong here. The NTNU key is read from the `NTNU_LLM_API_KEY` user environment variable.
