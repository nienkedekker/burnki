"""Burnki add-on entry point. Sets up the menu and hooks."""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.operations import QueryOp
from aqt.qt import QAction, QMenu
from aqt.utils import showInfo, tooltip

from .sync import SyncResult, apply_sync_result, fetch_sync_data


def _get_token() -> str | None:
    config = mw.addonManager.getConfig(__name__)
    if config is None:
        return None
    token = config.get("wanikani_api_token", "")
    return token if token else None


def _get_updated_after() -> str | None:
    config = mw.addonManager.getConfig(__name__)
    if config is None:
        return None
    ts = config.get("last_sync_timestamp", "")
    return ts if ts else None


def _save_timestamp() -> None:
    import datetime

    config = mw.addonManager.getConfig(__name__) or {}
    config["last_sync_timestamp"] = (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    )
    mw.addonManager.writeConfig(__name__, config)


def _on_sync_done(result: SyncResult) -> None:
    if result.error:
        tooltip(f"Burnki sync error: {result.error}", period=5000)
        return

    if not result.notes:
        tooltip("Burnki: no new burned items to sync.", period=3000)
        return

    created, updated = apply_sync_result(mw.col, result)
    _save_timestamp()
    mw.reset()
    tooltip(
        f"Burnki: synced {result.total_fetched} items "
        f"({created} new, {updated} updated).",
        period=5000,
    )


def _run_sync(full: bool = False) -> None:
    """Kick off a sync. If full=True, re-fetch everything."""
    token = _get_token()
    if not token:
        showInfo(
            "Burnki: no WaniKani API token configured.\n\n"
            "Go to Tools → Add-ons, select Burnki, and click Config "
            "to add your API token."
        )
        return

    updated_after = None if full else _get_updated_after()
    config = mw.addonManager.getConfig(__name__) or {}
    audio = config.get("download_audio", True)

    def _update_progress(msg: str) -> None:
        mw.taskman.run_on_main(lambda: mw.progress.update(label=msg))

    op = QueryOp(
        parent=mw,
        op=lambda col: fetch_sync_data(token, updated_after, progress=_update_progress, download_audio=audio),
        success=_on_sync_done,
    )
    label = "Full re-sync Burnki…" if full else "Syncing Burnki…"
    op.with_progress(label=label).run_in_background()


# -- menu --

def _setup_menu() -> None:
    menu = QMenu("Burnki", mw)
    mw.form.menuTools.addMenu(menu)

    sync_action = QAction("Sync Now", menu)
    sync_action.triggered.connect(lambda: _run_sync())
    menu.addAction(sync_action)

    full_sync_action = QAction("Full Re-sync", menu)
    full_sync_action.triggered.connect(lambda: _run_sync(full=True))
    menu.addAction(full_sync_action)


# -- hooks --

def _on_profile_did_open() -> None:
    config = mw.addonManager.getConfig(__name__)
    if config and config.get("auto_sync_on_startup", True):
        token = _get_token()
        if token:
            _run_sync()
        else:
            tooltip(
                "Burnki: set your WaniKani API token in Tools → Add-ons → Burnki → Config",
                period=5000,
            )


gui_hooks.profile_did_open.append(_on_profile_did_open)
gui_hooks.main_window_did_init.append(_setup_menu)
