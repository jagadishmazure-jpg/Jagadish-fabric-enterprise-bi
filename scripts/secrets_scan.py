"""Minimal secrets scan over every tracked or to-be-tracked file. Exit 1 on any finding.

    python scripts/secrets_scan.py

Looks for cloud keys, connection strings with keys, tokens, private keys and password assignments.
It complements (does not replace) GitHub secret scanning."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "azure storage/service key": re.compile(
        r"(AccountKey|SharedAccessKey|primaryKey)\s*=\s*[A-Za-z0-9+/]{30,}={0,2}"
    ),
    "SAS signature": re.compile(r"[?&]sig=[A-Za-z0-9%+/]{30,}"),
    "app insights ikey": re.compile(r"InstrumentationKey=[0-9a-f]{8}-[0-9a-f]{4}-"),
    "github token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "openai-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}"),
    "private key block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "password assignment": re.compile(
        r"(?i)\b(password|passwd|client_secret)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"
    ),
}
SKIP_SUFFIXES = {".png", ".jpg", ".pdf", ".docx"}


def files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()
    return [ROOT / f for f in out if (ROOT / f).is_file() and (ROOT / f).suffix not in SKIP_SUFFIXES]


def main() -> int:
    hits = 0
    fs = files()
    for f in fs:
        if f.name == "secrets_scan.py":
            continue
        text = f.read_text(errors="ignore")
        for name, rx in PATTERNS.items():
            for m in rx.finditer(text):
                hits += 1
                line = text[: m.start()].count("\n") + 1
                print(f"{f.relative_to(ROOT)}:{line}: possible {name}")
    print(f"scanned {len(fs)} files: {hits} finding(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
