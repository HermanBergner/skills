# Repository guide

This repo is a personal collection of **Claude Code skills** plus a TUI installer. It is **not** a
plugin or marketplace — skills install into the user's personal-skills dir (`~/.claude/skills/`, or
`$CLAUDE_CONFIG_DIR/skills`) and are invoked by their bare name.

## Layout

- `skills/<name>/SKILL.md` — one folder per skill. Frontmatter keys: `name`, `description`, `version`
  (integer-dotted, e.g. `1.2.0`). The whole folder is copied on install, so a skill may bundle
  supporting files alongside `SKILL.md`.
- `installer.py` — Textual TUI, run via `uv run installer.py`. Discovers `skills/*/SKILL.md`, compares
  each repo `version` against the installed copy, and installs/updates/uninstalls by copying/removing
  folders. Pure-stdlib logic except for Textual; dependency is declared inline (PEP 723).
- `install.sh` / `install.ps1` — launchers; use `uv` if present, else bootstrap a `.venv` + pip.

## Conventions

- **Add a skill:** create `skills/<name>/SKILL.md` with the three frontmatter keys above.
- **Ship an update:** bump that skill's `version`. Update detection is repo-version > installed-version,
  both read from `SKILL.md` on disk.
- Keep `version` integer-dotted; a non-numeric part makes the installer treat it as "unknown"
  (always shown as updatable).
- The install target is resolved as `Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser() / "skills"`
  — uniform across Linux/macOS/Windows. Do not introduce `platformdirs`; Claude Code does not use
  OS-conventional app-data paths.
- No `.claude-plugin/`, `marketplace.json`, or `plugin.json` — those were the old plugin approach and
  were removed.
