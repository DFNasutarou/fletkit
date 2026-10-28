"""ページ関数に渡す Context。設定・ログ・ステータスバー・画面遷移を扱う。"""

from __future__ import annotations

import asyncio
import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

if TYPE_CHECKING:
    from ..services.settings import SettingsStore
    from .app import App

R = TypeVar("R")


class ShellPort:
    """_backend のシェルが実装する操作（Flet 非依存のインターフェース）。"""

    def set_status(self, text: str) -> None: ...
    def set_subtitle(self, text: str) -> None: ...
    def navigate(self, route: str) -> None: ...
    def close(self) -> None: ...


class Context:
    def __init__(
        self,
        app: "App",
        store: "SettingsStore[Any]",
        settings: Any,
        logger: logging.Logger,
        args: list[str],
        log_path: Optional[Path],
    ):
        self.app = app
        self._store = store
        self._settings = settings
        self.log = logger
        self.args = args
        self.log_path = log_path
        self._shell: ShellPort = ShellPort()
        self._listeners: list[Callable[[Any], Any]] = []
        self._tasks: set[asyncio.Task[Any]] = set()

    # ---- 設定 ----
    @property
    def settings(self) -> Any:
        """現在の設定（データクラス）。変更したら save_settings() を呼ぶ。"""
        return self._settings

    def save_settings(self, new: Any = None) -> None:
        """設定を保存する。new を渡すとそれに置き換えてから保存する。"""
        if new is not None:
            self._settings = new
        self._store.save(self._settings)
        self.log.debug("設定を保存しました: %s", self._store.path)
        for fn in list(self._listeners):
            try:
                result = fn(self._settings)
            except Exception:
                self.log.exception("設定変更の通知でエラー")
                continue
            if inspect.isawaitable(result):
                self._spawn(result)

    def _spawn(self, awaitable: Any) -> None:
        async def runner() -> None:
            try:
                await awaitable
            except Exception:
                self.log.exception("設定変更の通知でエラー")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(runner())
            return
        task = loop.create_task(runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def on_settings_changed(self, fn: Callable[[Any], Any]) -> None:
        """設定が保存されたときに呼ばれる関数を登録する。"""
        self._listeners.append(fn)

    # ---- 画面 ----
    def status(self, text: str) -> None:
        """ステータスバーの文字を変える。"""
        self._shell.set_status(text)

    def subtitle(self, text: str) -> None:
        """ヘッダのアプリ名の横に出す文字（開いているファイル名など）を変える。"""
        self._shell.set_subtitle(text)

    def navigate(self, route: str) -> None:
        self._shell.navigate(route)

    def quit(self) -> None:
        self._shell.close()

    # ---- 重い処理 ----
    async def run_in_thread(self, fn: Callable[..., R], *args: Any, **kwargs: Any) -> R:
        """重い処理を別スレッドで実行し、画面を固めずに結果を待つ。"""
        return await asyncio.to_thread(fn, *args, **kwargs)
