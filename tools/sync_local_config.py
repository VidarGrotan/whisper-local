"""Keep this PC's live Whisper Local config identical to the repo's local-config/.

The live files in %APPDATA%\\whisperkey are only seeded once and are rewritten by
the app, so production settings drifted (and once split into a second, Codex
private copy). This tool checks for drift, installs the canonical config with
backups, and migrates a stray app-package copy back into the real folder.

Usage (from the repo root, with the project venv):
    .venv\\Scripts\\python.exe tools\\sync_local_config.py --check
    .venv\\Scripts\\python.exe tools\\sync_local_config.py
    .venv\\Scripts\\python.exe tools\\sync_local_config.py --migrate-package-folder PATH
"""

import argparse
import datetime
import io
import json
import os
import shutil
import sys
from pathlib import Path

from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = REPO_ROOT / "local-config"
SETTINGS_FILE = "user_settings.yaml"
RULES_FILE = "app_rules.yaml"
PROFILES_FILE = "profiles.yaml"
HISTORY_FILES = ("transcripts.jsonl", "stats.jsonl")
API_KEY_ENV = "NTNU_LLM_API_KEY"


# ============================================================================
# Locations
# ============================================================================

def default_live_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "whisperkey"


# Store (MSIX) apps such as Codex desktop redirect %APPDATA% for processes they
# launch; any whisperkey folder in there is a second, divergent config.
def find_package_config_folders(local_appdata: Path) -> list:
    packages = local_appdata / "Packages"
    if not packages.is_dir():
        return []
    return sorted(packages.glob("*/LocalCache/Roaming/whisperkey"))


# ============================================================================
# YAML helpers
# ============================================================================

def _round_trip_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # keep long prompt lines unwrapped
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load_yaml(path: Path):
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return _round_trip_yaml().load(f)


def _plain(value):
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


# ============================================================================
# Drift detection (read-only)
# ============================================================================

# Every canonical leaf must exist with the same value in live; extra live keys
# (e.g. a tray-chosen input_device) are fine.
def find_settings_drift(canonical, live, prefix="") -> list:
    drift = []
    for key, expected in canonical.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if not isinstance(live, dict) or key not in live:
            drift.append(f"{path}: missing (expected {_short(expected)})")
            continue
        actual = live[key]
        if isinstance(expected, dict) and isinstance(actual, dict):
            drift.extend(find_settings_drift(expected, actual, path))
        elif _plain(expected) != _plain(actual):
            drift.append(f"{path}: expected {_short(expected)}, found {_short(actual)}")
    return drift


def _short(value) -> str:
    text = json.dumps(_plain(value), ensure_ascii=False)
    return text if len(text) <= 70 else text[:67] + "..."


# Whole-file comparison for rules/profiles; profiles' "active" is user state.
def files_match(canonical_path: Path, live_path: Path, ignore_keys=()) -> bool:
    canonical, live = load_yaml(canonical_path), load_yaml(live_path)
    if canonical is None or live is None:
        return False
    canonical, live = _plain(canonical), _plain(live)
    for key in ignore_keys:
        canonical.pop(key, None)
        live.pop(key, None)
    return canonical == live


def api_key_is_set() -> bool:
    if os.environ.get(API_KEY_ENV):
        return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return bool(winreg.QueryValueEx(key, API_KEY_ENV)[0])
    except (ImportError, OSError):
        return False


def check(live_dir: Path, local_appdata: Path) -> list:
    problems = []
    canonical_settings = load_yaml(CANONICAL_DIR / SETTINGS_FILE)
    live_settings = load_yaml(live_dir / SETTINGS_FILE)
    if live_settings is None:
        problems.append(f"{live_dir / SETTINGS_FILE} is missing")
    else:
        problems.extend(f"{SETTINGS_FILE} {line}"
                        for line in find_settings_drift(canonical_settings, live_settings))
    if not files_match(CANONICAL_DIR / RULES_FILE, live_dir / RULES_FILE):
        problems.append(f"{RULES_FILE} differs from local-config/{RULES_FILE}")
    if not files_match(CANONICAL_DIR / PROFILES_FILE, live_dir / PROFILES_FILE,
                       ignore_keys=("active",)):
        problems.append(f"{PROFILES_FILE} differs from local-config/{PROFILES_FILE}")
    for folder in find_package_config_folders(local_appdata):
        problems.append(f"second config folder inside an app package: {folder}")
    if not api_key_is_set():
        problems.append(f"user environment variable {API_KEY_ENV} is not set")
    return problems


# ============================================================================
# Install (writes live files, always after a backup)
# ============================================================================

def backup(path: Path, live_dir: Path, stamp: str) -> None:
    if path.is_file():
        backups = live_dir / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backups / f"{path.name}.{stamp}")


# Merge canonical nodes into the live round-trip document, keeping live extras.
def _merge_into(live, canonical) -> None:
    for key, value in canonical.items():
        if isinstance(value, dict) and isinstance(live.get(key), dict):
            _merge_into(live[key], value)
        else:
            live[key] = value


def install(live_dir: Path, stamp: str) -> list:
    live_dir.mkdir(parents=True, exist_ok=True)
    changed = []

    settings_path = live_dir / SETTINGS_FILE
    canonical = load_yaml(CANONICAL_DIR / SETTINGS_FILE)
    live = load_yaml(settings_path)
    if live is None or find_settings_drift(canonical, live):
        backup(settings_path, live_dir, stamp)
        merged = live if live is not None else canonical
        if live is not None:
            _merge_into(merged, canonical)
        buffer = io.StringIO()
        _round_trip_yaml().dump(merged, buffer)
        settings_path.write_text(buffer.getvalue(), encoding="utf-8")
        changed.append(SETTINGS_FILE)

    rules_path = live_dir / RULES_FILE
    if not files_match(CANONICAL_DIR / RULES_FILE, rules_path):
        backup(rules_path, live_dir, stamp)
        shutil.copyfile(CANONICAL_DIR / RULES_FILE, rules_path)
        changed.append(RULES_FILE)

    profiles_path = live_dir / PROFILES_FILE
    if not files_match(CANONICAL_DIR / PROFILES_FILE, profiles_path, ignore_keys=("active",)):
        live_profiles = load_yaml(profiles_path)
        active = live_profiles.get("active") if live_profiles else None
        backup(profiles_path, live_dir, stamp)
        profiles = load_yaml(CANONICAL_DIR / PROFILES_FILE)
        if active:
            profiles["active"] = active
        with open(profiles_path, "w", encoding="utf-8") as f:
            _round_trip_yaml().dump(profiles, f)
        changed.append(PROFILES_FILE)

    return changed


# ============================================================================
# Migration of a stray app-package config folder
# ============================================================================

def _entry_time(line: str) -> str:
    try:
        entry = json.loads(line)
    except ValueError:
        return ""
    return str(entry.get("timestamp") or entry.get("ts") or "")


# Union of both histories, exact duplicates dropped, ordered by entry time.
def merge_history(live_path: Path, other_path: Path) -> int:
    lines = []
    for path in (live_path, other_path):
        if path.is_file():
            lines.extend(line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    unique = sorted({line for line in lines if line}, key=_entry_time)
    live_path.write_text("".join(line + "\n" for line in unique), encoding="utf-8")
    return len(unique)


def migrate_package_folder(package_dir: Path, live_dir: Path, stamp: str) -> Path:
    live_dir.mkdir(parents=True, exist_ok=True)
    for name in HISTORY_FILES:
        backup(live_dir / name, live_dir, stamp)
        total = merge_history(live_dir / name, package_dir / name)
        print(f"  merged {name}: {total} entries")

    # Keep the package copy's own settings snapshots alongside the live backups.
    backups = live_dir / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    for snapshot in package_dir.glob(f"{SETTINGS_FILE}*"):
        shutil.copy2(snapshot, backups / f"package-{snapshot.name}.{stamp}")

    retired = package_dir.with_name(f"whisperkey.migrated-{stamp}")
    package_dir.rename(retired)
    return retired


# ============================================================================
# CLI
# ============================================================================

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift only; exit 1 on drift")
    parser.add_argument("--migrate-package-folder", metavar="PATH", type=Path,
                        help="merge history from an app-package whisperkey folder, then retire it")
    parser.add_argument("--live-dir", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--local-appdata", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    live_dir = args.live_dir or default_live_dir()
    local_appdata = args.local_appdata or Path(os.environ["LOCALAPPDATA"])
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    if args.check:
        problems = check(live_dir, local_appdata)
        for problem in problems:
            print(f"DRIFT  {problem}")
        if problems:
            print("Run tools\\sync_local_config.py (without --check) to repair.")
            return 1
        print(f"Live config in {live_dir} matches local-config/.")
        return 0

    if args.migrate_package_folder:
        retired = migrate_package_folder(args.migrate_package_folder, live_dir, stamp)
        print(f"Retired package folder -> {retired}")

    changed = install(live_dir, stamp)
    if changed:
        print(f"Updated {', '.join(changed)} in {live_dir} (backups in {live_dir / 'backups'}).")
        print("Restart Whisper Local from the tray or Start menu to load the new settings.")
    else:
        print("Live config already matches local-config/; nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
