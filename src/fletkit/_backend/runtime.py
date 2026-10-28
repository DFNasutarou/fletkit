"""実行中のシェル（1ウィンドウ＝1シェル）を保持する。"""

from __future__ import annotations

from typing import Any, Optional

_current: Optional[Any] = None


def set_current_shell(shell: Any) -> None:
    global _current
    _current = shell


def current_shell() -> Any:
    if _current is None:
        raise RuntimeError("fletkit のアプリが起動していません（dialog はイベントハンドラの中で使ってください）")
    return _current
