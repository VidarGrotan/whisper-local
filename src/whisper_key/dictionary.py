# dictionary.py
# Manages `whisper.hotwords` — the list of names and jargon Whisper is biased
# toward, which is the cheapest way to fix recurring misrecognitions. Provides
# CLI add/remove/list, a small Tk add-word dialog, and history mining that
# suggests hotwords from words the user actually dictates. Writes
# user_settings.yaml directly (round-trip YAML) so it works without a running app;
# a running app picks the change up on its next dictation (ConfigManager reload).

import logging
from pathlib import Path
from typing import List, Optional

from ruamel.yaml import YAML

from .utils import get_user_app_data_path

logger = logging.getLogger(__name__)
USER_SETTINGS = "user_settings.yaml"

# A source checkout may carry its canonical production settings in
# local-config/ (synced to the live file by tools/sync_local_config.py).
# Hotword edits are mirrored there so a later sync doesn't revert them.
LOCAL_CONFIG_SETTINGS = Path(__file__).resolve().parents[2] / "local-config" / USER_SETTINGS


def list_hotwords() -> List[str]:
    user_path = Path(get_user_app_data_path()) / USER_SETTINGS
    if not user_path.exists():
        return []
    try:
        with open(user_path, encoding='utf-8') as f:
            data = YAML().load(f) or {}
        return list((data.get('whisper') or {}).get('hotwords') or [])
    except Exception as e:
        logger.warning(f"Could not read hotwords: {e}")
        return []


# =============================================================================
# Writing the hotword list (live settings + local-config mirror)
# =============================================================================

# Round-trip YAML matching the settings files' layout; a wide line limit keeps
# long prompts on one line instead of re-wrapping them.
def _settings_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


# Replace whisper.hotwords in one settings file, keeping everything else as-is.
def _write_hotwords_to(path: Path, words: List[str]) -> None:
    yaml = _settings_yaml()
    data = {}
    if path.exists():
        with open(path, encoding='utf-8') as f:
            data = yaml.load(f) or {}
    data.setdefault('whisper', {})['hotwords'] = list(words)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f)


# Single writer for every hotword change (dialog, history window, CLI, vocab
# import): the live settings file, plus local-config/ when this checkout has one.
def save_hotwords(words: List[str]) -> None:
    _write_hotwords_to(Path(get_user_app_data_path()) / USER_SETTINGS, words)
    if LOCAL_CONFIG_SETTINGS.is_file():
        try:
            _write_hotwords_to(LOCAL_CONFIG_SETTINGS, words)
        except Exception as e:
            logger.warning(f"Could not mirror hotwords to {LOCAL_CONFIG_SETTINGS}: {e}")


def add_word(word: str) -> bool:
    word = (word or '').strip()
    if not word:
        return False
    current = list_hotwords()
    if word in current:
        print(f"   '{word}' already in dictionary")
        return False
    current.append(word)
    save_hotwords(current)
    print(f"   ✓ Added '{word}' to whisper.hotwords ({len(current)} total)")
    return True


def remove_word(word: str) -> bool:
    word = (word or '').strip()
    if not word:
        return False
    current = list_hotwords()
    if word not in current:
        print(f"   '{word}' not found in dictionary")
        return False
    current.remove(word)
    save_hotwords(current)
    print(f"   ✓ Removed '{word}' from dictionary ({len(current)} left)")
    return True


# =============================================================================
# Hotword suggestions (mined from your own transcription history)
# =============================================================================

import re as _re

# Words that are Capitalized simply because they open a sentence — never good
# hotword candidates on their own, plus a few pronouns/filler that commonly
# start clauses. Kept small on purpose; the user confirms each suggestion.
_SUGGEST_STOPWORDS = {
    'i', 'the', 'a', 'an', 'and', 'but', 'or', 'so', 'then', 'this', 'that',
    'it', 'we', 'you', 'he', 'she', 'they', 'my', 'our', 'your', 'his', 'her',
    'if', 'when', 'while', 'yes', 'no', 'ok', 'okay', 'well', 'also', 'here',
    'there', 'what', 'who', 'how', 'why', 'let', 'please', 'thanks', 'hi', 'hey',
}

# A "namey" token: CamelCase, ALLCAPS acronym, alphanumeric tech term (h264,
# gpt4), or a plain Capitalized word (≥2 letters). Matched case-sensitively.
_NAMEY = _re.compile(r'[A-Za-z][A-Za-z0-9]*')


# Pure, testable core: scan already-spoken transcripts for frequently-used
# proper-noun-ish tokens the model likely gets wrong, biased toward tokens that
# appear MID-sentence (so ordinary sentence-initial capitals don't dominate).
# Returns (word, count) pairs, most frequent first, excluding known hotwords.
def suggest_hotwords(texts: List[str], known: Optional[set] = None,
                     min_count: int = 3, limit: int = 20) -> List[tuple]:
    known_lower = {w.lower() for w in (known or set())}
    counts = {}
    for text in texts:
        if not text:
            continue
        # Split into sentence-ish spans so we can tell "first word" from the rest.
        for span in _re.split(r'[.!?\n]+', text):
            tokens = _NAMEY.findall(span)
            for pos, tok in enumerate(tokens):
                is_namey = (
                    _re.search(r'[A-Z].*[A-Z]', tok)          # CamelCase / ALLCAPS
                    or _re.search(r'\d', tok)                  # has a digit (h264)
                    or (tok[:1].isupper() and pos > 0)         # Capitalized, not 1st word
                )
                if not is_namey or len(tok) < 2:
                    continue
                if tok.lower() in _SUGGEST_STOPWORDS or tok.lower() in known_lower:
                    continue
                counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return [(w, c) for w, c in ranked if c >= min_count][:limit]


# Convenience wrapper: mine the on-disk transcript journal against the current
# hotword list. Used by the history window's "Suggest hotwords" action.
def suggest_hotwords_from_history(min_count: int = 3, limit: int = 20) -> List[tuple]:
    from .transcript_log import load_transcripts
    texts = [e.get('text', '') for e in load_transcripts()]
    return suggest_hotwords(texts, known=set(list_hotwords()),
                            min_count=min_count, limit=limit)


def show_dictionary() -> int:
    words = list_hotwords()
    if not words:
        print("Dictionary is empty. Add words with: whisper-local --add-word NAME")
        return 0
    print(f"\nWhisper Local — Dictionary ({len(words)} word{'s' if len(words) != 1 else ''})\n")
    for w in sorted(words, key=str.lower):
        print(f"  • {w}")
    print()
    print("Edit via:")
    print("  whisper-local --add-word NAME")
    print("  whisper-local --remove-word NAME")
    print(f"  Or open {Path(get_user_app_data_path()) / USER_SETTINGS} directly\n")
    return 0


# Shows the small "add a hotword" dialog and blocks until it closes. Runs in its
# own process (`whisper-local --add-word-dialog`, launched from the tray): a Tk
# window on a thread of the running app shares the process with the level
# overlay's Tk thread, and its buttons silently stop working. The running app
# picks up saved words from disk on its next dictation.
def show_add_word_dialog():
    def run():
        try:
            import tkinter as tk
        except ImportError:
            logger.info("Tkinter unavailable for add-word dialog")
            return
        try:
            root = tk.Tk()
            root.title("Whisper Local — Add Word")
            root.configure(bg='#0d1117')
            try:
                root.attributes('-topmost', True)
            except Exception:
                pass

            w, h = 380, 160
            try:
                root.update_idletasks()
                sw = root.winfo_screenwidth()
                sh = root.winfo_screenheight()
                root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
            except Exception:
                root.geometry(f"{w}x{h}")

            outer = tk.Frame(root, bg='#0d1117', padx=14, pady=12)
            outer.pack(fill='both', expand=True)

            tk.Label(outer, text="Add to your hotword dictionary",
                     bg='#0d1117', fg='#3fb950',
                     font=('Segoe UI Semibold', 11),
                     anchor='w').pack(fill='x')
            tk.Label(outer, text="Names, jargon, acronyms — anything Whisper mishears",
                     bg='#0d1117', fg='#7d8590',
                     font=('Segoe UI', 9),
                     anchor='w').pack(fill='x', pady=(2, 10))

            entry_var = tk.StringVar()
            entry = tk.Entry(outer, textvariable=entry_var,
                             bg='#161b22', fg='#c9d1d9',
                             insertbackground='#c9d1d9',
                             relief='flat', bd=0,
                             font=('Segoe UI', 11))
            entry.pack(fill='x', ipady=6, pady=(0, 12))
            entry.focus_set()

            status_var = tk.StringVar(value="")
            tk.Label(outer, textvariable=status_var,
                     bg='#0d1117', fg='#7d8590',
                     font=('Segoe UI', 9),
                     anchor='w').pack(fill='x', pady=(0, 8))

            def commit(_=None):
                word = entry_var.get().strip()
                if not word:
                    status_var.set("Type a word first.")
                    return
                try:
                    ok = add_word(word)
                except Exception as e:
                    logger.exception(f"Could not save hotword '{word}'")
                    status_var.set(f"Could not save '{word}': {e}")
                    return
                if ok:
                    status_var.set(f"Added '{word}'. Active from your next dictation.")
                    entry_var.set("")
                else:
                    status_var.set(f"'{word}' is already in the dictionary.")

            def close(_=None):
                try: root.destroy()
                except Exception: pass

            buttons = tk.Frame(outer, bg='#0d1117')
            buttons.pack(fill='x')

            tk.Button(buttons, text="Close", command=close,
                      bg='#161b22', fg='#c9d1d9',
                      activebackground='#30363d', activeforeground='#c9d1d9',
                      bd=0, relief='flat', padx=14, pady=6,
                      font=('Segoe UI', 9), cursor='hand2').pack(side='right', padx=(8, 0))
            tk.Button(buttons, text="Add", command=commit,
                      bg='#3fb950', fg='#0d1117',
                      activebackground='#46c155', activeforeground='#0d1117',
                      bd=0, relief='flat', padx=14, pady=6,
                      font=('Segoe UI Semibold', 9), cursor='hand2').pack(side='right')

            root.protocol("WM_DELETE_WINDOW", close)
            root.bind('<Return>', commit)
            root.bind('<Escape>', close)
            # Tk swallows handler errors to stderr, which is invisible here.
            root.report_callback_exception = (
                lambda *exc: logger.error("Add-word dialog error", exc_info=exc))
            root.mainloop()
        except Exception as e:
            logger.warning(f"Add-word dialog failed: {e}")

    run()
