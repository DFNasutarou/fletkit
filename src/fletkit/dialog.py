"""ダイアログ（UI-05）。すべて async 関数で、イベントハンドラの中から await して使う。

    if await fk.dialog.confirm("削除しますか？"):
        ...
    path = await fk.dialog.open_file(ext=["xlsx"])
    async with fk.dialog.progress("読み込み中") as p:
        p.update("シート1/3")
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional, Protocol, Sequence


class ProgressHandle(Protocol):
    def update(self, message: Optional[str] = None, value: Optional[float] = None) -> None:
        """メッセージと進捗（0.0〜1.0、None は不定）を更新する。"""


def _shell():
    from ._backend.runtime import current_shell

    return current_shell()


async def info(message: str, title: str = "お知らせ") -> None:
    await _shell().dialog_message(title, message, kind="info")


async def error(message: str, title: str = "エラー", detail: str = "") -> None:
    await _shell().dialog_message(title, message, kind="error", detail=detail)


async def confirm(message: str, title: str = "確認", ok: str = "OK", cancel: str = "キャンセル") -> bool:
    return await _shell().dialog_confirm(title, message, ok, cancel)


async def open_file(
    ext: Optional[Sequence[str]] = None, initial_dir: Optional[str | Path] = None, title: Optional[str] = None
) -> Optional[Path]:
    """ファイルを1つ選ぶ。キャンセル時は None。ext は拡張子（ドットなし）のリスト。"""
    return await _shell().dialog_open_file(list(ext) if ext else None, str(initial_dir) if initial_dir else None, title)


async def open_files(
    ext: Optional[Sequence[str]] = None, initial_dir: Optional[str | Path] = None, title: Optional[str] = None
) -> list[Path]:
    """ファイルを複数選ぶ。キャンセル時は空リスト。"""
    return await _shell().dialog_open_files(list(ext) if ext else None, str(initial_dir) if initial_dir else None, title)


async def save_file(
    file_name: str = "",
    ext: Optional[Sequence[str]] = None,
    initial_dir: Optional[str | Path] = None,
    title: Optional[str] = None,
) -> Optional[Path]:
    """保存先を選ぶ。キャンセル時は None。"""
    return await _shell().dialog_save_file(
        file_name, list(ext) if ext else None, str(initial_dir) if initial_dir else None, title
    )


async def pick_folder(initial_dir: Optional[str | Path] = None, title: Optional[str] = None) -> Optional[Path]:
    return await _shell().dialog_pick_folder(str(initial_dir) if initial_dir else None, title)


@asynccontextmanager
async def progress(title: str = "処理中", message: str = "") -> AsyncIterator[ProgressHandle]:
    """処理中ダイアログ。with を抜けると閉じる。"""
    handle = await _shell().dialog_progress_open(title, message)
    try:
        yield handle
    finally:
        await _shell().dialog_progress_close(handle)
