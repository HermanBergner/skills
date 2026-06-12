#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["textual>=0.60"]
# ///
"""Bergner Skills — a keyboard-driven TUI to install, update, and uninstall
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
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

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
    """Read the leading ``---`` fenced frontmatter as flat ``key: value`` pairs."""
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
# Palette (lifted from bergner-service-todo-app design tokens) + renderers
# --------------------------------------------------------------------------- #
C_NAME = "#F5F6F8"     # text-strong
C_BODY = "#CBCFD6"     # text-default
C_DIM = "#8B909A"      # text-muted
C_OFF = "#5B606B"      # text-faint
C_OK = "#74D3A2"       # success-text
C_UPDATE = "#ECBC77"   # warning-text

_ICON = {
    NOT_INSTALLED: ("○", C_OFF),
    UP_TO_DATE: ("●", C_OK),
    UPDATE_AVAILABLE: ("↑", C_UPDATE),
    INSTALLED_UNKNOWN: ("↑", C_UPDATE),
}


def _state_label(sk: Skill) -> str:
    if not sk.installed:
        return "not installed"
    if sk.updatable:
        return f"update → {sk.repo_version}"
    return f"installed {sk.installed_version}"


def _row_text(sk: Skill) -> Text:
    icon, color = _ICON[sk.status]
    t = Text(no_wrap=True, overflow="ellipsis")
    t.append(f"{icon} ", style=color)
    t.append(f"{sk.name[:24]:<24} ", style=f"bold {C_NAME}" if sk.installed else C_BODY)
    t.append(f"{sk.repo_version:<7} ", style=C_DIM)
    t.append(_state_label(sk), style=color)
    return t


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
class SkillManager(App):
    CSS = """
    Screen { background: #101216; color: #CBCFD6; }
    Header { background: #16191E; color: #F5F6F8; }
    Footer { background: #0A0B0D; color: #8B909A; }

    #search {
        height: 3;
        margin: 1 1 0 1;
        border: round #262B33;
        background: #16191E;
        color: #CBCFD6;
    }
    #search:focus { border: round #2BD4E0; }

    #body { height: 1fr; }

    #list {
        width: 2fr;
        margin: 1 0 1 1;
        padding: 0 1;
        border: round #262B33;
        background: #16191E;
    }
    #list:focus { border: round #2BD4E0; }
    OptionList > .option-list--option { padding: 0 1; color: #CBCFD6; }
    OptionList > .option-list--option-highlighted { background: #1D2127; }
    #list:focus > .option-list--option-highlighted { background: #13343A; color: #F5F6F8; }

    #detailbox {
        width: 3fr;
        margin: 1 1 1 1;
        padding: 1 2;
        border: round #262B33;
        background: #16191E;
    }
    #detail { background: #16191E; color: #CBCFD6; }
    """

    BINDINGS = [
        Binding("slash", "focus_search", "search"),
        Binding("space,enter", "toggle", "install/remove"),
        Binding("u", "update", "update"),
        Binding("a", "sync_all", "sync all"),
        Binding("x", "uninstall", "uninstall"),
        Binding("r", "refresh", "refresh"),
        Binding("q", "quit", "quit"),
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("escape", "blur_search", "to list", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="type to filter…", id="search")
        with Horizontal(id="body"):
            yield OptionList(id="list")
            with VerticalScroll(id="detailbox"):
                yield Static("", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Bergner Skills"
        self.sub_title = str(skills_dir())
        self.list: OptionList = self.query_one("#list", OptionList)
        self.detail: Static = self.query_one("#detail", Static)
        self.query_one("#search", Input).border_title = "Search"
        self.list.border_title = "Skills"
        self.query_one("#detailbox", VerticalScroll).border_title = "Details"
        self.skills: list[Skill] = []
        self.filtered: list[Skill] = []
        self._reload()
        self.list.focus()

    # -- data --------------------------------------------------------------- #
    def _query(self) -> str:
        return self.query_one("#search", Input).value.strip().lower()

    def _refilter(self) -> None:
        q = self._query()
        prev = self.list.highlighted or 0
        self.filtered = [
            s for s in self.skills
            if not q or q in s.name.lower() or q in s.description.lower()
        ]
        self.list.clear_options()
        for sk in self.filtered:
            self.list.add_option(Option(_row_text(sk), id=sk.dirname))
        if self.filtered:
            self.list.highlighted = min(prev, len(self.filtered) - 1)
        self._update_detail()

    def _reload(self) -> None:
        """Re-scan disk, then re-apply the current search filter."""
        self.skills = discover()
        self._refilter()

    def _current(self) -> Skill | None:
        i = self.list.highlighted
        if i is None or not (0 <= i < len(self.filtered)):
            return None
        return self.filtered[i]

    def _update_detail(self) -> None:
        sk = self._current()
        if sk is None:
            self.detail.update(Text("No matching skill.", style=C_DIM))
            return
        icon, color = _ICON[sk.status]
        body = Text()
        body.append(f"{icon} {sk.name}\n", style=f"bold {C_NAME}")
        body.append(f"repo {sk.repo_version}", style=C_DIM)
        body.append(
            f"   ·   {_state_label(sk)}\n\n",
            style=color if sk.installed else C_DIM,
        )
        body.append(sk.description or "(no description)", style=C_BODY)
        self.detail.update(body)

    # -- events ------------------------------------------------------------- #
    def on_option_list_option_highlighted(self, _e: OptionList.OptionHighlighted) -> None:
        self._update_detail()

    def on_option_list_option_selected(self, _e: OptionList.OptionSelected) -> None:
        self.action_toggle()  # Enter / click-equivalent

    def on_input_changed(self, _e: Input.Changed) -> None:
        self._refilter()

    def on_input_submitted(self, _e: Input.Submitted) -> None:
        self.list.focus()

    # -- navigation / focus ------------------------------------------------- #
    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_blur_search(self) -> None:
        self.list.focus()

    def action_cursor_down(self) -> None:
        if self.list.option_count:
            self.list.action_cursor_down()

    def action_cursor_up(self) -> None:
        if self.list.option_count:
            self.list.action_cursor_up()

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
