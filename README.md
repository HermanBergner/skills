# Bergner Skills

A small, personal collection of [Claude Code](https://claude.com/claude-code) **skills**, with a
TUI to install / update / uninstall them.

Skills install into Claude Code's personal-skills directory (`~/.claude/skills/`) and are invoked by
their **bare name** — no plugin namespace, no marketplace.

## Quick start

```sh
git clone https://github.com/HermanBergner/skills
cd skills

./install.sh          # macOS / Linux
# .\install.ps1       # Windows (PowerShell)
# uv run installer.py # any OS, if you have uv
```

You get an interactive dashboard — pick skills, install them, quit. A new Claude Code session picks
them up automatically.

### Prerequisites

- **Recommended:** [`uv`](https://docs.astral.sh/uv/). The launcher uses it to fetch the single
  dependency (Textual) automatically — zero setup.
- **Without uv:** any `python3` works. The launcher creates a local `.venv` and `pip install`s Textual
  for you.

## Keys

| key | action |
|-----|--------|
| `↑`/`↓` or `j`/`k` | move |
| `space` / `enter` | install ⇄ uninstall the highlighted skill |
| `u` | update the highlighted skill (when an update is available) |
| `a` | sync all — install everything missing + update everything outdated |
| `x` / `d` | uninstall the highlighted skill |
| `r` | refresh from disk |
| `q` | quit |

Status: `○ not installed` · `● installed` · `↑ update` (the repo has a newer version than the copy
you installed).

## How updates work

Installing **copies** a skill folder into `~/.claude/skills/`. Each `SKILL.md` carries a `version`.
To get updates: `git pull`, then run the installer again — any skill whose repo version is newer than
your installed copy shows `↑ update`. Press `u` on it (or `a` to update everything).

> If you've set `CLAUDE_CONFIG_DIR`, skills install under `$CLAUDE_CONFIG_DIR/skills` instead of
> `~/.claude/skills`.

## Adding a skill

Create `skills/<name>/SKILL.md` with frontmatter:

```yaml
---
name: <name>
description: <when Claude should reach for this skill>
version: 1.0.0
---

# <Title>

…skill instructions…
```

Bump `version` to ship an update. A skill may bundle extra files (scripts, references) in its folder —
the whole folder is copied on install.
