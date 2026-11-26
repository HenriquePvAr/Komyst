"""Validate tracked public documentation and sample assets using the standard library."""
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
TRACKED = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")) - {""}
PSD = "samples/ludicrital/ludicrital-p01.psd"
DIGEST = "6cf25a9aaf0325452abc9aa582c871797aa6118dc2f206b72bea2bb6bd747c2d"
LINK = re.compile(r"!?\[[^\]\n]+\]\(([^\s)]+)\)")
SENSITIVE_PATH = re.compile(r"(?i)komyst-core|komystlad|[A-Z]:[\\/](?:users|projetos)[\\/]|https?://(?:localhost|127\.0\.0\.1)(?:[:/]|$)")
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16}")
ALLOWED_SUFFIXES = {".md", ".yml", ".py", ".png", ".webp"}
errors = []

for rel in sorted(TRACKED):
    path = ROOT / rel
    if path.is_symlink() or not path.is_file():
        errors.append(f"{rel}: expected regular file")
        continue
    if (path.suffix not in ALLOWED_SUFFIXES and rel != PSD) or path.stat().st_size > (5_000_000 if rel == PSD else 1_000_000):
        errors.append(f"{rel}: unexpected file type or size")
    if path.suffix != ".md":
        continue
    source = path.read_text(encoding="utf-8-sig")
    if not re.search(r"^# \S", source, re.M) or len(re.findall(r"^\s*```", source, re.M)) % 2:
        errors.append(f"{rel}: missing heading or unclosed fence")
    if SECRET.search(source) or SENSITIVE_PATH.search(source):
        errors.append(f"{rel}: review sensitive tokens or paths")
    for match in LINK.finditer(source):
        target = urlsplit(match[1])
        if target.scheme or target.netloc or not target.path:
            continue
        try:
            resolved = (path.parent / unquote(target.path)).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            errors.append(f"{rel}: link outside the repository")
            continue
        if resolved not in TRACKED:
            errors.append(f"{rel}: missing local link to {resolved}")

if PSD not in TRACKED or sha256((ROOT / PSD).read_bytes()).hexdigest() != DIGEST:
    errors.append("The documented PSD hash did not match")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Validated {len(TRACKED)} files and the documented PSD hash.")
