#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["textual>=0.60"]
# ///
"""Bergner Skills — a Mason/Lazy-style TUI to install, update, and uninstall
Claude Code *personal* skills.

Skills live in this repo under ``skills/<name>/`` and are installed by copying
the whole folder into Claude Code's personal-skills directory
(``$CLAUDE_CONFIG_DIR/skills`` or ``~/.claude/skills``). Personal skills are
invoked by their bare name — no plugin namespace.

Run it:  ``uv run installer.py``   (or ``./install.sh`` / ``.\\install.ps1``)
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Static

REPO_ROOT = Path(__file__).resolve().parent
REPO_SKILLS = REPO_ROOT / "skills"


# --------------------------------------------------------------------------- #
# Paths & parsing (stdlib only)
# --------------------------------------------------------------------------- #
def skills_dir() -> Path:
    """Claude Code's personal-skills dir, cross-platform.

    Honors ``CLAUDE_CONFIG_DIR`` (the documented override); otherwise ``~/.claude``.
    ``expanduser()`` resolves ``%USERPROFILE%`` on Windows, ``$HOME`` elsewhere.
    """
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser()
    return base / "skills"


def parse_frontmatter(path: Path) -> dict[str, str]:
    """Read the leading ``---`` fenced frontmatter as flat ``key: value`` pairs.

    Frontmatter here is simple scalars (name/description/version), so we avoid a
    YAML dependency and split each line on its first colon.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    out: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, val = line.partition(":")
            out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def parse_version(s: str | None) -> tuple[int, ...]:
    """``"1.2.0"`` -> ``(1, 2, 0)``. Missing/unparseable -> ``(-1,)`` (= unknown)."""
    if not s:
        return (-1,)
    parts: list[int] = []
    for p in s.split("."):
        p = p.strip()
        if not p.isdigit():
            return (-1,)
        parts.append(int(p))
    return tuple(parts) or (-1,)


# Status constants
NOT_INSTALLED = "not_installed"
UP_TO_DATE = "up_to_date"
UPDATE_AVAILABLE = "update_available"
INSTALLED_UNKNOWN = "installed_unknown"  # installed, but version missing/unparseable

_STATUS_DISPLAY = {
    NOT_INSTALLED: ("○", "not installed", "dim"),
    UP_TO_DATE: ("●", "installed", "green"),
    UPDATE_AVAILABLE: ("↑", "update", "yellow"),
    INSTALLED_UNKNOWN: ("↑", "update", "yellow"),
}


@dataclass
class Skill:
    dirname: str          # folder under skills/ and under the install dir
    name: str             # display name (frontmatter `name`)
    description: str
    repo_version: str
    installed: bool
    installed_version: str | None

    @property
    def status(self) -> str:
        if not self.installed:
            return NOT_INSTALLED
        iv = parse_version(self.installed_version)
        if iv == (-1,):
            return INSTALLED_UNKNOWN
        if parse_version(self.repo_version) > iv:
            return UPDATE_AVAILABLE
        return UP_TO_DATE

    @property
    def updatable(self) -> bool:
        return self.status in (UPDATE_AVAILABLE, INSTALLED_UNKNOWN)


def discover() -> list[Skill]:
    """Scan the repo's ``skills/`` against the install dir to build current state."""
    if not REPO_SKILLS.is_dir():
        return []
    dest = skills_dir()
    skills: list[Skill] = []
    for d in sorted(p for p in REPO_SKILLS.iterdir() if p.is_dir()):
        src_md = d / "SKILL.md"
        if not src_md.is_file():
            continue
        fm = parse_frontmatter(src_md)
        inst_md = dest / d.name / "SKILL.md"
        installed = inst_md.is_file()
        skills.append(
            Skill(
                dirname=d.name,
                name=fm.get("name", d.name),
                description=fm.get("description", ""),
                repo_version=fm.get("version", "0.0.0"),
                installed=installed,
                installed_version=parse_frontmatter(inst_md).get("version") if installed else None,
            )
        )
    return skills


def do_install(skill: Skill) -> None:
    """Copy the skill folder into the install dir (replacing any existing copy)."""
    target = skills_dir() / skill.dirname
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(REPO_SKILLS / skill.dirname, target)


def do_uninstall(skill: Skill) -> None:
    target = skills_dir() / skill.dirname
    if target.exists():
        shutil.rmtree(target)


# --------------------------------------------------------------------------- #
# Cell renderers
# --------------------------------------------------------------------------- #
def _status_cell(sk: Skill) -> Text:
    icon, label, style = _STATUS_DISPLAY[sk.status]
    return Text(f"{icon} {label}", style=style)


def _installed_cell(sk: Skill) -> Text:
    return Text(sk.installed_version or "—", style="" if sk.installed_version else "dim")


def _short(s: str, n: int = 64) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
class SkillManager(App):
    CSS = """
    Screen { background: $surface; }
    #table { height: 1fr; }
    #detail {
        height: auto;
        min-height: 4;
        padding: 1 2;
        border-top: solid $primary;
        background: $panel;
    }
    """

    BINDINGS = [
        Binding("space", "toggle", "install/remove"),
        Binding("u", "update", "update"),
        Binding("a", "sync_all", "sync all"),
        Binding("x,d", "uninstall", "uninstall"),
        Binding("r", "refresh", "refresh"),
        Binding("q", "quit", "quit"),
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
            yield Static("", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Bergner Skills"
        self.sub_title = str(skills_dir())
        self.table: DataTable = self.query_one("#table", DataTable)
        self.detail: Static = self.query_one("#detail", Static)
        self.table.add_column("", key="status", width=16)
        self.table.add_column("Skill", key="name", width=20)
        self.table.add_column("Repo", key="repo", width=8)
        self.table.add_column("Installed", key="installed", width=10)
        self.table.add_column("Description", key="desc")
        self.skills: list[Skill] = []
        self._populate()
        self.table.focus()

    # -- data --------------------------------------------------------------- #
    def _populate(self) -> None:
        self.skills = discover()
        self.table.clear()
        for sk in self.skills:
            self.table.add_row(
                _status_cell(sk), sk.name, sk.repo_version,
                _installed_cell(sk), _short(sk.description), key=sk.dirname,
            )
        if not self.skills:
            self.detail.update(Text("No skills found under skills/ in this repo.", style="dim"))
        self._update_detail()

    def _reload(self) -> None:
        """Re-scan disk and refresh status cells in place, preserving the cursor."""
        cursor = self.table.cursor_row
        self.skills = discover()
        for sk in self.skills:
            self.table.update_cell(sk.dirname, "status", _status_cell(sk))
            self.table.update_cell(sk.dirname, "installed", _installed_cell(sk))
        if cursor is not None and self.table.row_count:
            self.table.move_cursor(row=min(cursor, self.table.row_count - 1))
        self._update_detail()

    def _current(self) -> Skill | None:
        i = self.table.cursor_row
        if i is None or not (0 <= i < len(self.skills)):
            return None
        return self.skills[i]

    def _update_detail(self) -> None:
        sk = self._current()
        if sk is None:
            return
        body = Text()
        body.append(sk.name, style="bold")
        body.append(f"   repo {sk.repo_version}", style="dim")
        if sk.installed:
            body.append(f"  ·  installed {sk.installed_version or '?'}", style="dim")
        body.append("\n")
        body.append(sk.description or "(no description)")
        self.detail.update(body)

    # -- events ------------------------------------------------------------- #
    def on_data_table_row_highlighted(self, _event: DataTable.RowHighlighted) -> None:
        self._update_detail()

    def on_data_table_row_selected(self, _event: DataTable.RowSelected) -> None:
        # Enter selects a row -> treat as toggle.
        self.action_toggle()

    # -- navigation --------------------------------------------------------- #
    def action_cursor_down(self) -> None:
        if self.table.row_count:
            self.table.move_cursor(row=min(self.table.cursor_row + 1, self.table.row_count - 1))

    def action_cursor_up(self) -> None:
        if self.table.row_count:
            self.table.move_cursor(row=max(self.table.cursor_row - 1, 0))

    # -- actions ------------------------------------------------------------ #
    def _apply(self, fn, sk: Skill, msg: str) -> None:
        try:
            fn(sk)
        except Exception as exc:  # noqa: BLE001 — surface any FS error as a toast
            self.notify(str(exc), title=f"error: {sk.name}", severity="error")
            return
        self._reload()
        self.notify(msg, title="skills")

    def action_toggle(self) -> None:
        sk = self._current()
        if sk is None:
            return
        if sk.installed:
            self._apply(do_uninstall, sk, f"removed {sk.name}")
        else:
            self._apply(do_install, sk, f"installed {sk.name} {sk.repo_version}")

    def action_update(self) -> None:
        sk = self._current()
        if sk is None:
            return
        if sk.updatable:
            self._apply(do_install, sk, f"updated {sk.name} → {sk.repo_version}")
        elif not sk.installed:
            self.notify(f"{sk.name} is not installed", severity="warning")
        else:
            self.notify(f"{sk.name} already up to date")

    def action_uninstall(self) -> None:
        sk = self._current()
        if sk is None:
            return
        if sk.installed:
            self._apply(do_uninstall, sk, f"removed {sk.name}")
        else:
            self.notify(f"{sk.name} is not installed", severity="warning")

    def action_sync_all(self) -> None:
        installed = updated = errs = 0
        for sk in self.skills:
            try:
                if not sk.installed:
                    do_install(sk)
                    installed += 1
                elif sk.updatable:
                    do_install(sk)
                    updated += 1
            except Exception:  # noqa: BLE001
                errs += 1
        self._reload()
        parts = []
        if installed:
            parts.append(f"{installed} installed")
        if updated:
            parts.append(f"{updated} updated")
        if errs:
            parts.append(f"{errs} errors")
        self.notify("sync: " + (", ".join(parts) if parts else "nothing to do"), title="skills")

    def action_refresh(self) -> None:
        self._reload()
        self.notify("refreshed from disk")


if __name__ == "__main__":
    SkillManager().run()
