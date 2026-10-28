"""契約テスト：fletkit の部品が想定どおりの Flet コントロールに変換されるか。

Flet を版上げしたら最初にこれを実行する。画面を起動せずに壊れた箇所が分かる。
"""

from __future__ import annotations

import asyncio
import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import flet as ft
import pytest

import fletkit as fk
from fletkit._backend.handlers import call_handler
from fletkit._backend.render import render


class FakeShell:
    def __init__(self) -> None:
        self.updates = 0
        self.toasts: list[str] = []
        self.calls: list[tuple] = []
        self.log_listeners: list[Callable[[str], None]] = []

    def handler(self, fn: Optional[Callable[..., Any]], *extractors: Callable[[Any], Any]) -> Any:
        if fn is None and not extractors:
            return None

        async def on_event(e: Any) -> None:
            args = [ex(e) for ex in extractors]
            if fn is not None:
                await self.invoke(fn, *args)

        return on_event

    async def invoke(self, fn: Callable[..., Any], *args: Any) -> Any:
        self.calls.append(args)
        return await call_handler(fn, *args)

    def request_update(self) -> None:
        self.updates += 1

    def call_soon(self, fn: Callable[[], None]) -> None:
        fn()

    def subscribe_log(self, fn: Callable[[str], None]) -> Callable[[], None]:
        self.log_listeners.append(fn)
        return lambda: None

    def recent_logs(self) -> list[str]:
        return ["12:00:00 INFO    app: 起動", "12:00:01 ERROR   app: 失敗"]

    def toast(self, text: str) -> None:
        self.toasts.append(text)


class Ev:
    """Flet のイベントの代わり。control だけを持つ。"""

    def __init__(self, control: Any):
        self.control = control


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture
def shell() -> FakeShell:
    return FakeShell()


def test_text(shell: FakeShell) -> None:
    t = fk.Text("こんにちは", style="title")
    c = render(t, shell)
    assert isinstance(c, ft.Text)
    assert c.value == "こんにちは" and c.weight == ft.FontWeight.W_600
    t.set("更新")
    assert c.value == "更新" and shell.updates == 1


def test_str_child_becomes_text(shell: FakeShell) -> None:
    col = fk.Column("a", fk.Text("b"))
    c = render(col, shell)
    assert isinstance(c, ft.Column)
    assert [x.value for x in c.controls] == ["a", "b"]


def test_render_is_cached(shell: FakeShell) -> None:
    t = fk.Text("x")
    assert render(t, shell) is render(t, shell)


def test_button(shell: FakeShell) -> None:
    clicked = []
    b = fk.Button("開く", on_click=lambda: clicked.append(1), icon="folder_open", primary=True)
    c = render(b, shell)
    assert isinstance(c, ft.FilledButton)
    assert c.content == "開く" and c.icon == ft.Icons.FOLDER_OPEN
    run(c.on_click(Ev(c)))
    assert clicked == [1]
    b.set_enabled(False)
    assert c.disabled is True
    assert isinstance(render(fk.Button("x"), shell), ft.OutlinedButton)


def test_text_input_change(shell: FakeShell) -> None:
    got = []
    ti = fk.TextInput("名前", on_change=lambda v: got.append(v))
    c = render(ti, shell)
    assert isinstance(c, ft.TextField) and c.label == "名前"
    c.value = "abc"
    run(c.on_change(Ev(c)))
    assert ti.value == "abc" and got == ["abc"]


def test_checkbox_and_select(shell: FakeShell) -> None:
    cb = fk.Checkbox("有効", True)
    c = render(cb, shell)
    assert isinstance(c, ft.Checkbox) and c.value is True

    sel_got = []
    s = fk.Select("色", [("r", "赤"), ("g", "緑")], "g", on_change=lambda v: sel_got.append(v))
    d = render(s, shell)
    assert isinstance(d, ft.Dropdown)
    assert [o.text for o in d.options] == ["赤", "緑"] and d.value == "1"
    d.value = "0"
    run(d.on_select(Ev(d)))
    assert s.value == "r" and sel_got == ["r"]


def test_tabs(shell: FakeShell) -> None:
    got = []
    tabs = fk.Tabs([], on_change=lambda i: got.append(i))
    box = render(tabs, shell)
    assert isinstance(box, ft.Container) and box.content is None
    tabs.set_labels(["Sheet1", "Sheet2"])
    inner = box.content
    assert isinstance(inner, ft.Tabs) and inner.length == 2
    assert isinstance(inner.content, ft.TabBar)
    assert [t.label for t in inner.content.tabs] == ["Sheet1", "Sheet2"]
    inner.selected_index = 1
    run(inner.on_change(Ev(inner)))
    assert tabs.selected == 1 and got == [1]


def test_menu(shell: FakeShell) -> None:
    got = []
    m = fk.Menu("最近", [], on_select=lambda v: got.append(v))
    c = render(m, shell)
    assert isinstance(c, ft.PopupMenuButton)
    assert c.items[0].disabled is True
    m.set_items([("/a.xlsx", "a.xlsx")])
    run(c.items[0].on_click(Ev(c.items[0])))
    assert got == ["/a.xlsx"]


def test_toolbar_and_spacer(shell: FakeShell) -> None:
    c = render(fk.Toolbar(fk.Button("a"), fk.Spacer(), "b"), shell)
    assert isinstance(c, ft.Container) and isinstance(c.content, ft.Row)
    assert len(c.content.controls) == 3


def test_raw(shell: FakeShell) -> None:
    native = ft.Text("native")
    assert render(fk.raw(native), shell) is native
    with pytest.raises(TypeError):
        render(fk.raw("not a control"), shell)


def test_non_component_rejected(shell: FakeShell) -> None:
    with pytest.raises(TypeError):
        render(ft.Text("x"), shell)


def test_table(shell: FakeShell) -> None:
    t = fk.Table(page_size=2)
    c = render(t, shell)
    assert isinstance(c, ft.Column)
    t.set_rows([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}, {"a": 3, "b": "z"}])
    r = t._handle
    dt = r.body.content.controls[0].controls[0]
    assert isinstance(dt, ft.DataTable)
    assert [col.label.value for col in dt.columns] == ["a", "b"]
    assert len(dt.rows) == 2
    assert r.count.value == "3 件" and r.page_info.value == "1–2"
    # ソート（列ヘッダ）
    dt.columns[0].on_sort(None)
    assert t.model.sort_col == 0 and t.model.sort_asc is True
    # ページ送り
    r.next.on_click(None)
    dt = r.body.content.controls[0].controls[0]
    assert len(dt.rows) == 1 and r.next.disabled is True
    # フィルタ
    r.filter.value = "y"
    r.filter.on_change(Ev(r.filter))
    assert r.count.value == "1 / 3 件"


class Mode(enum.Enum):
    FAST = "高速"
    SAFE = "安全"


@dataclass
class Conf:
    name: str = field(default="", metadata=fk.meta("名前", required=True))
    rows: int = field(default=100, metadata=fk.meta("行数", min=10, max=1000))
    enabled: bool = True
    mode: Mode = Mode.FAST
    folder: Path = Path(".")
    secret: str = field(default="", metadata=fk.meta(hidden=True))


def test_form(shell: FakeShell) -> None:
    saved = []
    form = fk.Form(Conf(name="a"), on_submit=lambda v: saved.append(v))
    c = render(form, shell)
    assert isinstance(c, ft.Column)
    r = form._handle
    assert set(r.widgets) == {"name", "rows", "enabled", "mode", "folder"}
    assert isinstance(r.widgets["enabled"], ft.Checkbox)
    assert isinstance(r.widgets["mode"], ft.Dropdown) and r.widgets["mode"].value == "0"
    rows = r.widgets["rows"]
    rows.value = "5"
    rows.on_change(Ev(rows))
    run(r._on_submit(None))
    assert saved == [] and rows.error == "10 以上にしてください"
    rows.value = "50"
    rows.on_change(Ev(rows))
    run(r._on_submit(None))
    assert saved and saved[0].rows == 50 and shell.toasts == ["保存しました"]


def test_logview(shell: FakeShell) -> None:
    lv = fk.LogView(max_lines=3)
    c = render(lv, shell)
    lst = c.content
    assert isinstance(lst, ft.ListView) and len(lst.controls) == 2
    assert lst.controls[1].color == ft.Colors.ERROR
    for i in range(3):
        shell.log_listeners[0](f"line {i}")
    assert len(lst.controls) == 3 and lst.controls[-1].value == "line 2"
