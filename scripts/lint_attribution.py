#!/usr/bin/env python3
"""Fail if an AI co-author trailer or "generated with" footer appears.

Slate is credited to its author alone. This checks three places:

  files     every file Git tracks (or, outside a repo, every file here)
  history   every commit message reachable from HEAD
  message   one commit message file (the commit-msg hook passes it)

Usage:
  python3 scripts/lint_attribution.py            # files and history
  python3 scripts/lint_attribution.py files
  python3 scripts/lint_attribution.py history
  python3 scripts/lint_attribution.py message .git/COMMIT_EDITMSG
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (Built from parts so this file doesn't match itself.)
TRAILER = "co-authored" + "-by"
PATTERNS = [
    re.compile(TRAILER + r"\s*:.*", re.IGNORECASE),
    re.compile(r"noreply@" + "anthropic" + r"\.com", re.IGNORECASE),
    re.compile(r"generated\s+with\s+\[?" + "claude" + r"(\s+code)?", re.IGNORECASE),
]

SKIP_DIRS = {".git", "node_modules", "__pycache__"}
BINARY_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".ttf", ".otf", ".woff", ".woff2", ".zip"}


def hits(text):
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for p in PATTERNS:
            if p.search(line):
                found.append((n, line.strip()))
                break
    return found


def in_repo():
    return subprocess.run(["git", "rev-parse", "--git-dir"], cwd=ROOT, capture_output=True).returncode == 0


def tracked_files():
    if in_repo():
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        names = [n for n in out.decode().split("\0") if n]
        # (A first commit's files are staged, not yet tracked: check those too.)
        staged = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT, capture_output=True).stdout
        names += [n for n in staged.decode().split("\0") if n and n not in names]
        return names
    names = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".live")]
        for f in files:
            names.append(os.path.relpath(os.path.join(d, f), ROOT))
    return names


def check_files():
    bad = 0
    for name in tracked_files():
        path = os.path.join(ROOT, name)
        if os.path.splitext(name)[1].lower() in BINARY_EXT or not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        for n, line in hits(text):
            print(f"{name}:{n}: {line}")
            bad += 1
    return bad


def check_history():
    if not in_repo():
        return 0
    head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=ROOT, capture_output=True)
    if head.returncode != 0:
        return 0  # no commits yet
    out = subprocess.run(["git", "log", "--format=%H%x00%B%x01"], cwd=ROOT, capture_output=True, check=True).stdout.decode()
    bad = 0
    for entry in out.split("\x01"):
        entry = entry.strip("\n")
        if not entry:
            continue
        sha, _, body = entry.partition("\x00")
        for _, line in hits(body):
            print(f"commit {sha[:12]}: {line}")
            bad += 1
    return bad


def check_message(path):
    text = open(path, encoding="utf-8").read()
    # (Git's own comment lines don't go into the commit.)
    text = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    bad = 0
    for _, line in hits(text):
        print(f"commit message: {line}")
        bad += 1
    return bad


def main(argv):
    what = argv[1] if len(argv) > 1 else "all"
    if what == "message":
        bad = check_message(argv[2])
    elif what == "files":
        bad = check_files()
    elif what == "history":
        bad = check_history()
    elif what == "all":
        bad = check_files() + check_history()
    else:
        print(__doc__)
        return 2
    if bad:
        print(f"\n{bad} AI attribution line(s) found. Slate is credited to its author alone: remove them.")
        return 1
    print("attribution: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
