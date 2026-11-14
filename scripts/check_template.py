#!/usr/bin/env python3
"""Check that the Slate template is whole and well formed.

  - zeron-template.json is valid JSON with the fields Zeron reads
  - every theme in ds/themes/ parses (JSON with // comments)
  - every "assets/..." path the Luau files name exists
  - LICENSE, README.md and the wallpaper's CREDITS.txt are present
  - each .luau file has balanced brackets and closed strings (a quick
    check; CI also compiles each one with luau-compile)

Usage: python3 scripts/check_template.py
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []


def err(msg):
    errors.append(msg)


def strip_jsonc(text):
    """Drop // and /* */ comments outside strings."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(c)
        i += 1
    # (Trailing commas, which JSONC allows.)
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def check_manifest():
    path = os.path.join(ROOT, "zeron-template.json")
    try:
        m = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return err(f"zeron-template.json: {e}")
    for key in ("id", "name", "version", "description", "author"):
        if not isinstance(m.get(key), str) or not m[key].strip():
            err(f"zeron-template.json: missing or empty \"{key}\"")
    if isinstance(m.get("version"), str) and not re.fullmatch(r"\d+\.\d+\.\d+", m["version"]):
        err(f"zeron-template.json: version \"{m['version']}\" isn't x.y.z")


def check_themes():
    d = os.path.join(ROOT, "ds", "themes")
    if not os.path.isdir(d):
        return
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            try:
                json.loads(strip_jsonc(open(os.path.join(d, f), encoding="utf-8").read()))
            except Exception as e:
                err(f"ds/themes/{f}: {e}")


def luau_files():
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in files:
            if f.endswith(".luau"):
                yield os.path.join(d, f)


def check_assets():
    for path in luau_files():
        text = open(path, encoding="utf-8").read()
        for ref in re.findall(r'"(assets/[^"]+)"', text):
            if not os.path.isfile(os.path.join(ROOT, ref)):
                err(f"{os.path.relpath(path, ROOT)}: names {ref}, which doesn't exist")


def check_required():
    for f in ("LICENSE", "README.md", "assets/slate/CREDITS.txt", "preview.png"):
        if not os.path.isfile(os.path.join(ROOT, f)):
            err(f"missing {f}")


def check_brackets():
    pairs = {")": "(", "]": "[", "}": "{"}
    for path in luau_files():
        text = open(path, encoding="utf-8").read()
        rel = os.path.relpath(path, ROOT)
        stack, i, n, line = [], 0, len(text), 1
        while i < n:
            c = text[i]
            if c == "\n":
                line += 1
            # Comments: --[[ ]] / --[==[ ]==] and -- to end of line.
            if text.startswith("--", i):
                m = re.match(r"--\[(=*)\[", text[i:])
                if m:
                    end = text.find("]" + m.group(1) + "]", i)
                    end = n if end < 0 else end + len(m.group(1)) + 2
                    line += text.count("\n", i, end)
                    i = end
                else:
                    while i < n and text[i] != "\n":
                        i += 1
                continue
            # Long strings [[ ]] / [==[ ]==].
            m = re.match(r"\[(=*)\[", text[i:])
            if m:
                close = "]" + m.group(1) + "]"
                end = text.find(close, i + len(m.group(0)))
                if end < 0:
                    err(f"{rel}:{line}: unclosed long string")
                    break
                line += text.count("\n", i, end)
                i = end + len(close)
                continue
            if c in "\"'`":
                j = i + 1
                while j < n and text[j] != c:
                    if text[j] == "\\":
                        j += 1
                    elif text[j] == "\n" and c != "`":
                        err(f"{rel}:{line}: unclosed string")
                        break
                    j += 1
                line += text.count("\n", i, j)
                i = j + 1
                continue
            if c in "([{":
                stack.append((c, line))
            elif c in ")]}":
                if not stack or stack[-1][0] != pairs[c]:
                    err(f"{rel}:{line}: unexpected '{c}'")
                    break
                stack.pop()
            i += 1
        else:
            if stack:
                err(f"{rel}:{stack[-1][1]}: '{stack[-1][0]}' never closed")


def main():
    check_manifest()
    check_themes()
    check_assets()
    check_required()
    check_brackets()
    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} problem(s).")
        return 1
    print("template: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
