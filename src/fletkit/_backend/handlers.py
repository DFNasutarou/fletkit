"""ユーザーのイベントハンドラを呼び出す共通処理。"""

from __future__ import annotations

import inspect
from typing import Any, Callable


def accepted_args(fn: Callable[..., Any]) -> int:
    """関数が受け取れる位置引数の数（*args があれば大きな数）。"""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return 1
    n = 0
    for p in sig.parameters.values():
        if p.kind == p.VAR_POSITIONAL:
            return 99
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
            n += 1
    return n


async def call_handler(fn: Callable[..., Any], *args: Any) -> Any:
    """受け取れる数だけ引数を渡して呼び、awaitable なら待つ。"""
    result = fn(*args[: accepted_args(fn)])
    if inspect.isawaitable(result):
        result = await result
    return result
