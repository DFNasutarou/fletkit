"""部品の基底クラス。

fletkit の部品は「何を表示するか」だけを持つ。Flet のコントロールへの変換は
_backend が行い、変換結果（ハンドル）を ``_handle`` に保持する。
部品の属性を変えたら ``refresh()`` を呼ぶと画面に反映される。
"""

from __future__ import annotations

from typing import Any, Optional, Protocol


class Handle(Protocol):
    def refresh(self) -> None: ...


class Component:
    _handle: Optional[Handle] = None

    def refresh(self) -> None:
        """属性の変更を画面に反映する。まだ表示されていなければ何もしない。"""
        if self._handle is not None:
            self._handle.refresh()

    @property
    def mounted(self) -> bool:
        return self._handle is not None

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        attrs = {k: v for k, v in vars(self).items() if not k.startswith("_")}
        return f"{type(self).__name__}({attrs})"


Child = Any  # Component または str（str は Text として扱う）
