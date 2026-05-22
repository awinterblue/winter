"""Self-update — check GitHub for a newer version and apply it.

Winter is installed as a git clone, so an update is just new commits on the
remote `main`. These helpers shell out to git and pip; they are blocking, so
the AppController runs them on worker threads and never from the UI thread.
"""
from __future__ import annotations

import subprocess
import sys

from winter import PROJECT_ROOT

_GIT = ["git", "-C", str(PROJECT_ROOT)]


def _git(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([*_GIT, *args], capture_output=True, text=True, **kwargs)


def check_for_update() -> bool:
    """True if the remote `main` has commits this install doesn't have yet.

    Returns False on any error — offline, not a git clone, git missing — so a
    failed check can never be mistaken for an available update.
    """
    try:
        _git("fetch", "--quiet", "origin", "main", check=True, timeout=30)
        local = _git("rev-parse", "HEAD", check=True).stdout.strip()
        remote = _git("rev-parse", "origin/main", check=True).stdout.strip()
        if not local or not remote or local == remote:
            return False
        # only count it if HEAD is strictly behind — a developer's own
        # unpushed commits ("ahead") are not an update to offer
        return _git("merge-base", "--is-ancestor",
                    "HEAD", "origin/main").returncode == 0
    except Exception:  # noqa: BLE001 - any failure means "no update"
        return False


def _pyproject_text() -> str:
    try:
        return (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return ""


def apply_update() -> None:
    """Pull the latest version, reinstalling only if dependencies changed.

    Winter is an editable install, so a code-only update needs no reinstall —
    the new source is simply live on the next launch. The slower pip step runs
    only when pyproject.toml changed (its dependencies might have), which keeps
    the common code-only update down to a quick `git pull`. Raises on failure.
    """
    deps_before = _pyproject_text()
    _git("pull", "--ff-only", "origin", "main", check=True, timeout=120)
    if _pyproject_text() != deps_before:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "-e",
             str(PROJECT_ROOT)],
            check=True, timeout=600,
        )


def relaunch() -> None:
    """Best-effort relaunch of Winter through its platform launcher."""
    from winter.system.osinfo import IS_MACOS, IS_WINDOWS

    try:
        if IS_MACOS and (PROJECT_ROOT / "Winter.app").is_dir():
            subprocess.Popen(["open", str(PROJECT_ROOT / "Winter.app")])
        elif IS_WINDOWS and (PROJECT_ROOT / "winter.vbs").exists():
            subprocess.Popen(["wscript", str(PROJECT_ROOT / "winter.vbs")])
    except Exception:  # noqa: BLE001 - relaunch is best-effort
        pass
