# Contributing to Slate

## Layout

Slate is a Zeron template. Each file here replaces the file at the same path in Zeron's interface; everything else comes from Zeron itself.

| Path | What it is |
| --- | --- |
| `zeron-template.json` | The template's manifest: id, name, version, description. |
| `theme.luau`, `ds/themes/` | The palette, dark and light. |
| `ds/sidebar.luau`, `ds/session_row.luau` | The sidebar: its grid, headings, rows, usage strip and bottom bar. |
| `ds/account_row.luau`, `ds/settings.luau` | The bottom bar in the settings pane. |
| `ds/surface.luau`, `ds/dropdown.luau` | Highlights and the composer's chips. |
| `screens/chat/composer.luau` | The new-chat composer and the Zeron mark over it. |
| `screens/shell/page.luau` | The default wallpaper. |
| `assets/slate/` | The wallpaper and its credits. |
| `preview.png` | The screenshot: the README's, and the template's on Zeron's Templates page. |
| `scripts/`, `.githooks/`, `.github/` | Checks. Not part of the template. |

## Working on it

Clone the repository into `~/.zeron/templates/slate`. Zeron reloads a template's files as you save them.

Zeron's MCP tool `template_status` reports any file that fails to load. `export_template` writes a signed `.zeron-template` package for a release.

## Checks

Turn the Git hooks on once per clone:

```sh
git config core.hooksPath .githooks
```

| Check | Run it | What it does |
| --- | --- | --- |
| Attribution | `python3 scripts/lint_attribution.py` | Fails on an AI agent's co-author trailer or a "generated with" footer naming one (people's and plain bots' trailers are fine). It looks in tracked files and in every commit message. The `commit-msg` hook runs it on each new message. |
| Template | `python3 scripts/check_template.py` | Checks that the manifest is valid JSON and has its fields. Checks that both themes parse and that every `assets/...` path the code names exists. Checks that the license and credits are present and that every `.luau` file has balanced brackets and closed strings. |
| Luau | CI only | Compiles every `.luau` file with `luau-compile` (Luau 0.747), which catches syntax errors. Type-checking isn't possible outside Zeron, since `ui` and the rest come from the app. |

CI (`.github/workflows/ci.yml`) runs all three on every push and pull request.

## Zeron releases

`.github/workflows/zeron-release.yml` brings each new Zeron release into Slate (it looks every three hours, or run it by hand from Actions). It fetches Zeron's interface source at the version Slate names in `zeron_version` and at the new one, merges Zeron's changes into each file Slate replaces (a three-way merge: Zeron then, Slate's copy, Zeron now), and runs `scripts/check_zeron_release.py` on the result, which reports:

- files whose merge conflicts with Slate's own changes (left as they were), with Zeron's diffs;
- modules, locale keys and icons Slate uses that no longer exist, module names a file reads but never declares, and module members Zeron may have dropped;
- files that no longer compile.

When nothing Slate replaces changed and every check passes, it moves `zeron_version` to the new release straight on `main`, with no pull request. When Zeron changed files Slate replaces and everything merges and passes, it opens a pull request with the merged files that moves `zeron_version` and rewrites `.base.json`, the fingerprints of Zeron's originals that Zeron's own "out of date" check compares against. Otherwise it opens an issue with the report. No change to Slate's files reaches `main` until you merge it.

## Attribution

Slate is credited to its people, never an AI agent. Co-author trailers for people and plain bots (github-actions, dependabot) are fine. Commits and files must not carry an AI agent's co-author trailer (Claude, Codex, Copilot, Cursor, Gemini and the like), a "generated with" footer naming one, or an AI company's noreply address. The attribution check enforces this.

## Releasing

1. Bump `version` in `zeron-template.json`.
2. Run `export_template` for `slate`.
3. Attach `~/.zeron/template-exports/slate.zeron-template` to the GitHub release.
