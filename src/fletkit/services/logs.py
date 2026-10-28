"""ログ出力（CM-05）。

標準の logging を使い、次の2か所に出す。
- ファイル：<設定フォルダ>/logs/app.log（1MB × 5世代でローテーション）
- 画面：LogBuffer に直近のログを溜め、ログビューアが購読する
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Optional

from .settings import config_dir

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class LogBuffer(logging.Handler):
    """直近のログ行を保持し、追加時にリスナーへ通知するハンドラ。"""

    def __init__(self, capacity: int = 2000):
        super().__init__()
        self.records: deque[str] = deque(maxlen=capacity)
        self._listeners: list[Callable[[str], None]] = []
        self._lock_l = threading.Lock()
        self.setFormatter(logging.Formatter(FORMAT, "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:  # pragma: no cover - logging 自体の失敗は握りつぶす
            return
        self.records.append(line)
        with self._lock_l:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(line)
            except Exception:
                pass

    def subscribe(self, fn: Callable[[str], None]) -> Callable[[], None]:
        with self._lock_l:
            self._listeners.append(fn)

        def unsubscribe() -> None:
            with self._lock_l:
                if fn in self._listeners:
                    self._listeners.remove(fn)

        return unsubscribe


def log_file_path(app_id: str) -> Path:
    return config_dir(app_id) / "logs" / "app.log"


def setup_logging(
    app_id: str, to_file: bool = True, level: int = logging.INFO
) -> tuple[logging.Logger, LogBuffer, Optional[Path]]:
    """アプリ用ロガーを準備する。戻り値は (アプリのロガー, 画面用バッファ, ログファイルパス)。"""
    root = logging.getLogger()
    root.setLevel(level)
    # 2回呼ばれても重複しないよう、以前に付けた fletkit のハンドラを外す
    for h in list(root.handlers):
        if getattr(h, "_fletkit", False):
            root.removeHandler(h)

    buffer = LogBuffer()
    buffer._fletkit = True  # type: ignore[attr-defined]
    root.addHandler(buffer)

    path: Optional[Path] = None
    if to_file:
        path = log_file_path(app_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
            fh.setFormatter(logging.Formatter(FORMAT))
            fh._fletkit = True  # type: ignore[attr-defined]
            root.addHandler(fh)
        except OSError as ex:
            path = None
            logging.getLogger("fletkit").warning("ログファイルを開けませんでした: %s", ex)

    # flet 内部の詳細ログは抑える
    logging.getLogger("flet").setLevel(logging.WARNING)
    logging.getLogger("flet_desktop").setLevel(logging.WARNING)
    logging.getLogger("flet_web").setLevel(logging.WARNING)
    return logging.getLogger(app_id), buffer, path
