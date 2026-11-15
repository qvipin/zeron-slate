#!/usr/bin/env python3
"""Check Slate against a new Zeron release.

Slate replaces some of Zeron's interface files and inherits the rest, so a
Zeron release can break it in a few ways. Given Zeron's interface source
(`apps/zgx/ui`) at the version Slate was made for and at the new one, this
reports:

  - changed:  files Slate replaces whose Zeron original changed (diffed
              against where Slate's copy came from: Zeron v2's own copy when
              it has one, since Slate is built on v2's layout)
  - removed:  files Slate replaces that Zeron no longer has
  - requires: modules Slate requires that don't exist any more
  - members:  functions or values Slate reads off a Zeron module that the
              module no longer defines (a warning: found by reading the
              source, not by running it)
  - strings:  locale keys Slate uses that the new en.json lacks
  - icons:    icon names Slate uses that ds/icon.luau no longer lists
  - globals:  a module name a file reads (`Dock.hero_offset()`) that it
              never declares or requires (Zeron's own files have shipped
              this; compiling doesn't catch it, loading does)

With --merge it brings Zeron's changes into Slate's copies first (a
three-way merge per file; one that conflicts is left as it was) and runs
the checks on the result. With --bless, when nothing needs a look, it also
moves Slate to the new version: `zeron_version` in the
manifest, and `.base.json`, the fingerprints of Zeron's originals that
Zeron's own "out of date" check compares against.

Usage:
  check_zeron_release.py --old OLD_UI --new NEW_UI --version X.Y.Z \\
      [--report report.md] [--merge] [--bless]

Exit status: 0 when nothing needs attention, 1 when something does.
"""

import argparse
import difflib
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join("templates", "zeron-v2")

# Slate's own files: never Zeron's, never compared.
OWN = {"zeron-template.json", "README.md", "CONTRIBUTING.md", "LICENSE", "preview.png", ".base.json"}
OWN_DIRS = ("scripts/", ".github/", ".githooks/", ".git/", "assets/slate/")


# Zeron's fingerprint of a file (src/plugins/live.rs `hash`): Rust's
# DefaultHasher, SipHash-1-3 with zero keys, over the length then the bytes.
def _siphash13(data):
    mask = (1 << 64) - 1

    def rotl(x, b):
        return ((x << b) | (x >> (64 - b))) & mask

    v0, v1, v2, v3 = 0x736F6D6570736575, 0x646F72616E646F6D, 0x6C7967656E657261, 0x7465646279746573

    def rnd():
        nonlocal v0, v1, v2, v3
        v0 = (v0 + v1) & mask; v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32)
        v2 = (v2 + v3) & mask; v3 = rotl(v3, 16); v3 ^= v2
        v0 = (v0 + v3) & mask; v3 = rotl(v3, 21); v3 ^= v0
        v2 = (v2 + v1) & mask; v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32)

    n = len(data)
    end = n - n % 8
    for i in range(0, end, 8):
        m = struct.unpack_from("<Q", data, i)[0]
        v3 ^= m; rnd(); v0 ^= m
    b = (n & 0xFF) << 56
    for i, c in enumerate(data[end:]):
        b |= c << (8 * i)
    v3 ^= b; rnd(); v0 ^= b
    v2 ^= 0xFF
    for _ in range(3):
        rnd()
    return (v0 ^ v1 ^ v2 ^ v3) & mask


def zeron_hash(content):
    return format(_siphash13(struct.pack("<Q", len(content)) + content), "016x")


def read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def slate_files():
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in files:
            rel = os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, "/")
            if rel in OWN or rel.startswith(OWN_DIRS) or f.startswith("."):
                continue
            yield rel


def origin(ui, rel):
    """Where Slate's copy of `rel` comes from in a Zeron UI tree."""
    v2 = os.path.join(ui, V2, rel)
    return v2 if os.path.isfile(v2) else os.path.join(ui, rel)


def resolve(ui, spec, from_rel):
    """A require's module file in Slate or the UI, or None."""
    if spec.startswith("@self/"):
        base = os.path.dirname(from_rel)
        rel = os.path.normpath(os.path.join(base, spec[len("@self/"):]))
    elif spec.startswith("@app/"):
        rel = spec[len("@app/"):]
    elif spec.startswith("@"):
        alias, _, rest = spec[1:].partition("/")
        rel = os.path.join(alias, rest) if rest else alias
    else:
        return "?"  # a relative or plain require: not checked
    rel = rel.replace(os.sep, "/")
    for cand in (rel + ".luau", rel + "/init.luau"):
        for root in (ROOT, ui):
            if os.path.isfile(os.path.join(root, cand)):
                return os.path.join(root, cand)
    return None


REQUIRE = re.compile(r'local\s+(\w+)\s*=\s*require\("([^"]+)"\)')
ANY_REQUIRE = re.compile(r'require\("([^"]+)"\)')
LOCALE = re.compile(r'(?:ui\.t|locale\.[st]|locale\.text)\(\s*"([a-z0-9_.\-]+)"')
ICON = re.compile(r'Icon\s*\{\s*name\s*=\s*"([a-z0-9\-]+)"')


def defines(module_src, name):
    """Whether a module's source defines `name` on what it returns."""
    n = re.escape(name)
    pats = [
        rf"\bM\.{n}\b(?:\s*,\s*M\.\w+)*\s*=",  # also `M.A, M.B = …`
        rf"\bM\.\w+\s*,[^=\n]*\bM\.{n}\b[^=\n]*=",
        rf"^\s*export\s+type\s+{n}\b",  # a type, `Module.Name`
        rf"function\s+M[.:]{re.escape(name)}\b",
        rf"^\s*{re.escape(name)}\s*=",  # a returned table's field
        rf"\b{re.escape(name)}\s*=\s*{re.escape(name)}\b",
    ]
    return any(re.search(p, module_src, re.M) for p in pats)


def flatten(d, prefix=""):
    out = set()
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out |= flatten(v, key + ".")
        else:
            out.add(key)
    return out


def check(old, new):
    found = {"changed": [], "removed": [], "requires": [], "members": [], "strings": [], "icons": [], "globals": []}
    luau = [r for r in slate_files() if r.endswith(".luau")]

    for rel in sorted(slate_files()):
        was = read(origin(old, rel))
        now = read(origin(new, rel))
        if was is None and now is None:
            continue  # Slate's own file
        if now is None:
            found["removed"].append(rel)
        elif was != now:
            diff = difflib.unified_diff(
                (was or b"").decode("utf-8", "replace").splitlines(),
                now.decode("utf-8", "replace").splitlines(),
                f"{rel} (Zeron, was)", f"{rel} (Zeron, now)", lineterm="", n=2,
            )
            found["changed"].append((rel, "\n".join(diff)))

    en = json.loads(read(os.path.join(new, "locales", "en.json")) or b"{}")
    keys = flatten(en)
    icon_src = (read(os.path.join(new, "ds", "icon.luau")) or b"").decode()
    svgs = (read(os.path.join(new, "ds", "icon_svgs.luau")) or b"").decode()
    named = re.search(r"export type Name =(.*?)\n\n", icon_src, re.S)
    icons = set(re.findall(r'"([a-z0-9\-]+)"', named.group(1) if named else ""))
    icons |= set(re.findall(r'\["([a-z0-9\-]+)"\]\s*=', svgs))

    for rel in luau:
        src = read(os.path.join(ROOT, rel)).decode("utf-8", "replace")
        for spec in set(ANY_REQUIRE.findall(src)):
            if resolve(new, spec, rel) is None:
                found["requires"].append(f"`{rel}` requires `{spec}`")
        for var, spec in REQUIRE.findall(src):
            path = resolve(new, spec, rel)
            if not path or path == "?" or path.startswith(ROOT):
                continue  # missing (above), unchecked, or Slate's own
            mod = read(path).decode("utf-8", "replace")
            for member in sorted(set(re.findall(rf"\b{re.escape(var)}\.([A-Za-z_]\w*)", src))):
                if not defines(mod, member):
                    found["members"].append(f"`{rel}` uses `{var}.{member}` (`{spec}`)")
        for key in sorted(set(LOCALE.findall(src))):
            if keys and key not in keys and not any(k.startswith(key + ".") for k in keys):
                found["strings"].append(f"`{rel}` uses `{key}`")
        for name in sorted(set(ICON.findall(src))):
            if icons and name not in icons:
                found["icons"].append(f"`{rel}` uses icon `{name}`")
        for name in undeclared(src):
            found["globals"].append(f"`{rel}` reads `{name}` without declaring or requiring it")
    return found


def undeclared(src):
    """Capitalised names read as modules (`Name.x`, `Name {`, `Name(`) that
    the file never declares: not a local, a function, a parameter, a loop
    variable or a type."""
    code = re.sub(r"--\[(=*)\[.*?\]\1\]", "", src, flags=re.S)
    code = re.sub(r"--[^\n]*", "", code)
    code = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`', '""', code)
    code = re.sub(r"\[(=*)\[.*?\]\1\]", '""', code, flags=re.S)
    declared = set()
    for m in re.finditer(r"\blocal\s+function\s+(\w+)|\bfunction\s+(\w+)\b", code):
        declared.add(m.group(1) or m.group(2))
    for m in re.finditer(r"\blocal\s+([\w\s,:<>?|{}()\[\].]+?)(?==|\n|$)", code):
        declared |= set(re.findall(r"(?:^|,)\s*(\w+)", m.group(1)))
    for m in re.finditer(r"\bfor\s+([\w\s,]+?)\s+in\b|\bfor\s+(\w+)\s*=", code):
        declared |= set(re.findall(r"\w+", m.group(1) or m.group(2)))
    for m in re.finditer(r"function\s*[\w.:]*\s*\(([^)]*)\)", code):
        declared |= set(re.findall(r"(?:^|,)\s*(\w+)", m.group(1)))
    declared |= set(re.findall(r"\b(?:export\s+)?type\s+(\w+)", code))
    builtins = {"Enum", "Instance", "Vector3", "Color3", "UDim2"}
    used = set(re.findall(r"(?<![\w.:])([A-Z]\w*)\s*(?:\.\w|\{|\()", code))
    return sorted(u for u in used - declared - builtins)


def merge(old, new, changed):
    """Bring Zeron's changes into Slate's copies: a three-way merge of each
    changed file (Zeron then, Slate's copy, Zeron now). A clean merge is
    written over Slate's copy; one that conflicts leaves it as it was.
    Returns (merged, conflicted), lists of paths."""
    import subprocess
    merged, conflicted = [], []
    for rel, _diff in changed:
        base, theirs = origin(old, rel), origin(new, rel)
        if not os.path.isfile(base):
            conflicted.append((rel, "Zeron had no such file before; Slate's copy came from elsewhere"))
            continue
        ours = os.path.join(ROOT, rel)
        r = subprocess.run(
            ["git", "merge-file", "-p", "-L", "Slate", "-L", "Zeron (was)", "-L", "Zeron (now)", ours, base, theirs],
            capture_output=True,
        )
        if r.returncode == 0:
            with open(ours, "wb") as f:
                f.write(r.stdout)
            merged.append(rel)
        elif r.returncode > 0:
            conflicted.append((rel, f"{r.returncode} conflicting change(s) with Slate's own"))
        else:
            conflicted.append((rel, r.stderr.decode("utf-8", "replace").strip() or "git merge-file failed"))
    return merged, conflicted


PROBLEMS = ("removed", "requires", "strings", "icons", "globals")


def report(found, old_v, new_v, merging=None):
    """The report, and whether something needs a person. Merging, a change
    Zeron made is brought in, not a problem; a conflict is."""
    lines = [f"Checked Slate against **Zeron {new_v}** (it was made for {old_v})."]
    merged, conflicted = merging if merging is not None else ([], [])
    if merging is None:
        needs = bool(found["changed"]) or any(found[k] for k in PROBLEMS)
    else:
        needs = bool(conflicted) or any(found[k] for k in PROBLEMS)
    lines.append("")
    if not needs:
        lines.append(
            f"Zeron's changes to {len(merged)} file(s) Slate replaces merged cleanly, and everything Slate uses is still there."
            if merged else "Nothing Slate replaces changed, and everything it uses is still there."
        )
    else:
        lines.append("Needs a look.")
    titles = {
        "removed": "Files Slate replaces that Zeron removed",
        "requires": "Modules that no longer exist",
        "strings": "Locale keys that no longer exist",
        "icons": "Icons that no longer exist",
        "globals": "Module names read but never declared",
        "members": "Module members Zeron may no longer define (check by hand)",
    }
    if conflicted:
        lines += ["", "### Couldn't merge", "", "Zeron changed these where Slate changed them too. Slate's copy is left as it was; bring Zeron's change in by hand (its diff is below), then run the check again.", ""]
        lines += [f"- `{rel}`: {why}" for rel, why in conflicted]
    for key, title in titles.items():
        if found[key]:
            lines += ["", f"### {title}", ""] + [f"- {x}" for x in found[key]]
    if found["changed"]:
        if merging is None:
            lines += ["", "### Zeron changed files Slate replaces", "",
                      "Bring what applies into Slate's copy, then rerun this check.", ""]
        else:
            lines += ["", "### What Zeron changed", "",
                      "Merged into Slate's copy" + (" (except the files above)" if conflicted else "") + ":", ""]
        for rel, diff in found["changed"]:
            cut = diff if len(diff) < 12000 else diff[:12000] + "\n… (cut; see the release)"
            lines += [f"<details><summary><code>{rel}</code></summary>", "", "```diff", cut, "```", "", "</details>"]
    return "\n".join(lines) + "\n", needs


def bless(new, version):
    manifest_path = os.path.join(ROOT, "zeron-template.json")
    manifest = json.loads(read(manifest_path))
    manifest["zeron_version"] = version
    with open(manifest_path, "w") as f:
        f.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    base = {}
    for rel in sorted(slate_files()):
        content = read(os.path.join(new, rel))  # Zeron's own, as its check reads it
        if content is not None:
            base[rel] = zeron_hash(content)
    with open(os.path.join(ROOT, ".base.json"), "w") as f:
        f.write(json.dumps(base, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="Zeron's apps/zgx/ui at the version Slate was made for")
    ap.add_argument("--new", required=True, help="Zeron's apps/zgx/ui at the new release")
    ap.add_argument("--version", required=True, help="the new release's version, x.y.z")
    ap.add_argument("--report")
    ap.add_argument("--merge", action="store_true", help="merge Zeron's changes into Slate's copies")
    ap.add_argument("--bless", action="store_true", help="when nothing needs a look, move Slate to the new version")
    a = ap.parse_args()
    old_v = json.loads(read(os.path.join(ROOT, "zeron-template.json")))["zeron_version"]
    found = check(a.old, a.new)
    merging = None
    if a.merge and found["changed"]:
        merging = merge(a.old, a.new, found["changed"])
        # The checks again, on Slate as merged (what it would ship).
        again = check(a.old, a.new)
        for key in again:
            if key != "changed":
                found[key] = again[key]
    text, needs = report(found, old_v, a.version, merging)
    if a.report:
        with open(a.report, "w") as f:
            f.write(text)
    print(text)
    if a.bless and not needs:
        bless(a.new, a.version)
    return 1 if needs else 0


if __name__ == "__main__":
    sys.exit(main())
