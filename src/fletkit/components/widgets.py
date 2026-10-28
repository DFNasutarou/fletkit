"""基本部品：テキスト、ボタン、入力欄、レイアウトなど。

イベントハンドラは通常の関数でも async 関数でもよい。
- on_click / on_submit（Button）: 引数なし
- on_change（入力系）: 新しい値を1つ受け取る
- on_select（Menu）: 選ばれた項目の値を1つ受け取る
ハンドラ内で例外が起きると、ログに残してエラーダイアログを出す。
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from .base import Child, Component

Handler = Optional[Callable[..., Any]]


class Text(Component):
    """テキスト。style は "body" / "title" / "muted" / "error"。"""

    def __init__(self, value: str = "", *, style: str = "body", selectable: bool = False, size: Optional[int] = None):
        self.value = value
        self.style = style
        self.selectable = selectable
        self.size = size

    def set(self, value: str) -> None:
        self.value = value
        self.refresh()


class Button(Component):
    def __init__(
        self,
        label: str,
        on_click: Handler = None,
        *,
        icon: Optional[str] = None,
        primary: bool = False,
        enabled: bool = True,
        tooltip: Optional[str] = None,
    ):
        self.label = label
        self.on_click = on_click
        self.icon = icon
        self.primary = primary
        self.enabled = enabled
        self.tooltip = tooltip

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.refresh()


class TextInput(Component):
    def __init__(
        self,
        label: str = "",
        value: str = "",
        *,
        on_change: Handler = None,
        on_submit: Handler = None,
        hint: str = "",
        width: Optional[int] = None,
        password: bool = False,
        error: str = "",
        expand: bool = False,
    ):
        self.label = label
        self.value = value
        self.on_change = on_change
        self.on_submit = on_submit
        self.hint = hint
        self.width = width
        self.password = password
        self.error = error
        self.expand = expand


class Checkbox(Component):
    def __init__(self, label: str = "", value: bool = False, *, on_change: Handler = None):
        self.label = label
        self.value = value
        self.on_change = on_change


class Select(Component):
    """ドロップダウン。options は値のリスト、または (値, 表示名) のリスト。"""

    def __init__(
        self,
        label: str = "",
        options: Sequence[Any] = (),
        value: Any = None,
        *,
        on_change: Handler = None,
        width: Optional[int] = None,
        error: str = "",
    ):
        self.label = label
        self.options = list(options)
        self.value = value
        self.on_change = on_change
        self.width = width
        self.error = error

    def items(self) -> list[tuple[Any, str]]:
        out = []
        for o in self.options:
            if isinstance(o, tuple) and len(o) == 2:
                out.append((o[0], str(o[1])))
            else:
                out.append((o, str(o)))
        return out


class Tabs(Component):
    """タブの見出しだけを並べる部品（中身の切り替えはアプリ側で行う）。"""

    def __init__(self, labels: Sequence[str] = (), selected: int = 0, *, on_change: Handler = None):
        self.labels = list(labels)
        self.selected = selected
        self.on_change = on_change

    def set_labels(self, labels: Sequence[str], selected: int = 0) -> None:
        self.labels = list(labels)
        self.selected = selected if labels else 0
        self.refresh()


class Menu(Component):
    """ポップアップメニュー。items は値のリスト、または (値, 表示名) のリスト。"""

    def __init__(self, label: str, items: Sequence[Any] = (), *, on_select: Handler = None, icon: Optional[str] = None):
        self.label = label
        self.items = list(items)
        self.on_select = on_select
        self.icon = icon

    def entries(self) -> list[tuple[Any, str]]:
        out = []
        for o in self.items:
            if isinstance(o, tuple) and len(o) == 2:
                out.append((o[0], str(o[1])))
            else:
                out.append((o, str(o)))
        return out

    def set_items(self, items: Sequence[Any]) -> None:
        self.items = list(items)
        self.refresh()


class _Container(Component):
    def __init__(self, *children: Child, spacing: int = 8, expand: bool = False, scroll: bool = False, padding: int = 0):
        self.children: list[Child] = [c for c in children if c is not None]
        self.spacing = spacing
        self.expand = expand
        self.scroll = scroll
        self.padding = padding

    def set_children(self, *children: Child) -> None:
        self.children = [c for c in children if c is not None]
        self.refresh()


class Column(_Container):
    """縦に並べる。"""


class Row(_Container):
    """横に並べる。"""


class Toolbar(_Container):
    """ボタンや入力欄を横に並べるツールバー（下に区切り線が付く）。"""


class Spacer(Component):
    """Row / Toolbar の中で残りの幅を埋める。"""


class Divider(Component):
    pass


class DropZone(Component):
    """ファイルのドラッグ&ドロップを受け付ける領域。content をそのまま表示し、上にドロップされたファイルを受け取る。

    on_drop はドロップされたファイルのパス（list[Path]）を1つ受け取る。
    ドロップが使えるのは `flet build` で作った実行ファイルだけ（flet-dropzone が必要）。
    それ以外では content だけを表示する。使えるかどうかは DropZone.supported() で分かる。
    """

    def __init__(self, content: Child, on_drop: Handler = None, *, expand: bool = False):
        self.content = content
        self.on_drop = on_drop
        self.expand = expand

    @staticmethod
    def supported() -> bool:
        from .._backend.features import drop_supported

        return drop_supported()


class Raw(Component):
    """Flet のコントロールを直接入れる逃げ道。使った箇所は版上げ時の確認対象。"""

    def __init__(self, control: Any):
        self.control = control


def raw(control: Any) -> Raw:
    return Raw(control)
