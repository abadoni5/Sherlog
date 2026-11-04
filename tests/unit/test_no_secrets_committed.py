"""Guards against leaking keys or the private gateway hostname into tracked files."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Key-looking strings and the internal gateway host. Extend as needed.
FORBIDDEN = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"bain\.dev"),
]
SELF = {"tests/unit/test_no_secrets_committed.py"}


def _candidate_files() -> list[Path]:
    """Files git would track: tracked + untracked-but-not-ignored. Falls back to a walk."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split("\n")
        return [ROOT / p for p in out if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        skip = {".venv", ".git", "__pycache__", ".pytest_cache"}
        return [
            p for p in ROOT.rglob("*")
            if p.is_file() and not skip & set(p.relative_to(ROOT).parts)
            and p.name not in {".env", "sherlog.local.toml"}
        ]


def test_no_forbidden_strings_in_files():
    hits = []
    for path in _candidate_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in SELF or not path.is_file():
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in FORBIDDEN:
            if pattern.search(text):
                hits.append(f"{rel}: {pattern.pattern}")
    assert not hits, "forbidden strings found:\n" + "\n".join(hits)
