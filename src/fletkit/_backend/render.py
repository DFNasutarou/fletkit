"""fletkit の部品を Flet のコントロールに変換する（Flet に依存するのは _backend だけ）。

部品ごとに Renderer クラスを用意し、@renders で登録する。
Renderer は部品の _handle に入り、部品の refresh() で画面を更新する。
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

import flet as ft

from ..components import widgets as w
from ..components.base import Component
from ..components.form import Form
from ..components.logview import LogView
from ..components.table import Table
from .features import drop_supported


class ShellLike(Protocol):
    """Renderer がシェルに求める操作。テストでは偽物を使う。"""

    def handler(self, fn: Optional[Callable[..., Any]], *args_from_event: Callable[[Any], Any]) -> Any: ...
    def request_update(self) -> None: ...
    def call_soon(self, fn: Callable[[], None]) -> None: ...
    def subscribe_log(self, fn: Callable[[str], None]) -> Callable[[], None]: ...
    def recent_logs(self) -> list[str]: ...
    def toast(self, text: str) -> None: ...
    async def invoke(self, fn: Callable[..., Any], *args: Any) -> Any: ...


_RENDERERS: dict[type, type["Renderer"]] = {}


def renders(comp_type: type):
    def deco(cls: type["Renderer"]):
        _RENDERERS[comp_type] = cls
        return cls

    return deco


def render(comp: Any, shell: ShellLike) -> ft.Control:
    """部品を Flet コントロールにする。表示済みの部品は同じコントロールを返す。"""
    if isinstance(comp, str):
        comp = w.Text(comp)
    if not isinstance(comp, Component):
        raise TypeError(f"fletkit の部品ではありません: {comp!r}（Flet の部品は fk.raw() で包んでください）")
    if isinstance(comp._handle, Renderer):
        return comp._handle.control
    for klass in type(comp).__mro__:
        r = _RENDERERS.get(klass)
        if r is not None:
            renderer = r(comp, shell)
            comp._handle = renderer
            return renderer.control
    raise TypeError(f"{type(comp).__name__} の変換方法が登録されていません")


def icon(name: Optional[str]) -> Optional[Any]:
    """'folder_open' のようなアイコン名を Flet のアイコンにする。"""
    if not name:
        return None
    return getattr(ft.Icons, name.upper(), None)


class Renderer:
    control: ft.Control

    def __init__(self, comp: Any, shell: ShellLike):
        self.comp = comp
        self.shell = shell
        self.control = self.build()

    def build(self) -> ft.Control:  # pragma: no cover - 抽象
        raise NotImplementedError

    def apply(self) -> None:
        """部品の属性をコントロールに書き戻す。既定は作り直し不要な部品向けに何もしない。"""

    def refresh(self) -> None:
        self.apply()
        self.shell.request_update()


# ---------------------------------------------------------------- 基本部品


@renders(w.Text)
class TextRenderer(Renderer):
    def build(self) -> ft.Control:
        self.t = ft.Text()
        self.apply()
        return self.t

    def apply(self) -> None:
        c: w.Text = self.comp
        t = self.t
        t.value = c.value
        t.selectable = c.selectable
        t.size = c.size
        t.weight = None
        t.color = None
        if c.style == "title":
            t.size = c.size or 18
            t.weight = ft.FontWeight.W_600
        elif c.style == "muted":
            t.size = c.size or 12
            t.color = ft.Colors.ON_SURFACE_VARIANT
        elif c.style == "error":
            t.color = ft.Colors.ERROR


@renders(w.Button)
class ButtonRenderer(Renderer):
    def build(self) -> ft.Control:
        c: w.Button = self.comp
        cls = ft.FilledButton if c.primary else ft.OutlinedButton
        self.b = cls(content=c.label, on_click=self.shell.handler(c.on_click) if c.on_click else None)
        self.apply()
        return self.b

    def apply(self) -> None:
        c: w.Button = self.comp
        self.b.content = c.label
        self.b.icon = icon(c.icon)
        self.b.disabled = not c.enabled
        self.b.tooltip = c.tooltip


@renders(w.TextInput)
class TextInputRenderer(Renderer):
    def build(self) -> ft.Control:
        c: w.TextInput = self.comp

        def changed(e: Any) -> Any:
            c.value = e.control.value or ""
            return c.value

        self.f = ft.TextField(
            dense=True,
            on_change=self.shell.handler(c.on_change, changed),
            on_submit=self.shell.handler(c.on_submit, changed),
            password=c.password,
            can_reveal_password=c.password,
        )
        self.apply()
        return self.f

    def apply(self) -> None:
        c: w.TextInput = self.comp
        f = self.f
        f.label = c.label or None
        f.value = c.value
        f.hint_text = c.hint or None
        f.width = c.width
        f.expand = c.expand
        f.error = c.error or None


@renders(w.Checkbox)
class CheckboxRenderer(Renderer):
    def build(self) -> ft.Control:
        c: w.Checkbox = self.comp

        def changed(e: Any) -> Any:
            c.value = bool(e.control.value)
            return c.value

        self.cb = ft.Checkbox(on_change=self.shell.handler(c.on_change, changed))
        self.apply()
        return self.cb

    def apply(self) -> None:
        self.cb.label = self.comp.label
        self.cb.value = self.comp.value


@renders(w.Select)
class SelectRenderer(Renderer):
    def build(self) -> ft.Control:
        c: w.Select = self.comp

        def changed(e: Any) -> Any:
            items = c.items()
            try:
                c.value = items[int(e.control.value)][0]
            except (TypeError, ValueError, IndexError):
                c.value = None
            return c.value

        self.d = ft.Dropdown(dense=True, on_select=self.shell.handler(c.on_change, changed))
        self.apply()
        return self.d

    def apply(self) -> None:
        c: w.Select = self.comp
        items = c.items()
        self.d.label = c.label or None
        self.d.width = c.width
        self.d.error_text = c.error or None
        self.d.options = [ft.DropdownOption(key=str(i), text=label) for i, (_, label) in enumerate(items)]
        values = [v for v, _ in items]
        self.d.value = str(values.index(c.value)) if c.value in values else None


@renders(w.Tabs)
class TabsRenderer(Renderer):
    def build(self) -> ft.Control:
        self.box = ft.Container()
        self.apply()
        return self.box

    def apply(self) -> None:
        c: w.Tabs = self.comp
        if not c.labels:
            self.box.content = None
            return

        def changed(e: Any) -> Any:
            c.selected = int(e.control.selected_index)
            return c.selected

        c.selected = min(max(0, c.selected), len(c.labels) - 1)
        self.box.content = ft.Tabs(
            length=len(c.labels),
            selected_index=c.selected,
            animation_duration=ft.Duration(),
            on_change=self.shell.handler(c.on_change, changed),
            content=ft.TabBar(
                tabs=[ft.Tab(label=label) for label in c.labels],
                scrollable=True,
                tab_alignment=ft.TabAlignment.START,
            ),
        )


@renders(w.Menu)
class MenuRenderer(Renderer):
    def build(self) -> ft.Control:
        c: w.Menu = self.comp
        self.m = ft.PopupMenuButton(
            content=ft.Container(
                ft.Row([ft.Icon(icon(c.icon) or ft.Icons.ARROW_DROP_DOWN, size=18), ft.Text(c.label)], spacing=4, tight=True),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            ),
            tooltip="",
        )
        self.apply()
        return self.m

    def apply(self) -> None:
        c: w.Menu = self.comp
        entries = c.entries()
        if not entries:
            self.m.items = [ft.PopupMenuItem(content=ft.Text("（なし）"), disabled=True)]
            return
        self.m.items = [
            ft.PopupMenuItem(content=ft.Text(label), on_click=self.shell.handler(c.on_select, (lambda e, v=value: v)))
            for value, label in entries
        ]


class _ContainerRenderer(Renderer):
    def children(self) -> list[ft.Control]:
        return [render(ch, self.shell) for ch in self.comp.children]


@renders(w.Column)
class ColumnRenderer(_ContainerRenderer):
    def build(self) -> ft.Control:
        self.col = ft.Column()
        self.apply()
        if self.comp.padding:
            return ft.Container(self.col, padding=self.comp.padding, expand=self.comp.expand)
        return self.col

    def apply(self) -> None:
        c = self.comp
        self.col.controls = self.children()
        self.col.spacing = c.spacing
        self.col.expand = c.expand
        self.col.scroll = ft.ScrollMode.AUTO if c.scroll else None


@renders(w.Row)
class RowRenderer(_ContainerRenderer):
    def build(self) -> ft.Control:
        self.row = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.apply()
        if self.comp.padding:
            return ft.Container(self.row, padding=self.comp.padding, expand=self.comp.expand)
        return self.row

    def apply(self) -> None:
        c = self.comp
        self.row.controls = self.children()
        self.row.spacing = c.spacing
        self.row.expand = c.expand
        self.row.scroll = ft.ScrollMode.AUTO if c.scroll else None


@renders(w.Toolbar)
class ToolbarRenderer(_ContainerRenderer):
    def build(self) -> ft.Control:
        self.row = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.apply()
        return ft.Container(
            self.row,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )

    def apply(self) -> None:
        self.row.controls = self.children()
        self.row.spacing = self.comp.spacing


@renders(w.Spacer)
class SpacerRenderer(Renderer):
    def build(self) -> ft.Control:
        return ft.Container(expand=True)


@renders(w.Divider)
class DividerRenderer(Renderer):
    def build(self) -> ft.Control:
        return ft.Divider(height=1)


@renders(w.Raw)
class RawRenderer(Renderer):
    def build(self) -> ft.Control:
        if not isinstance(self.comp.control, ft.Control):
            raise TypeError("fk.raw() には Flet のコントロールを渡してください")
        return self.comp.control


@renders(w.DropZone)
class DropZoneRenderer(Renderer):
    """flet-dropzone（Flutter の desktop_drop）で包む。使えない環境では中身だけを出す。"""

    IDLE = ft.Border.all(2, ft.Colors.TRANSPARENT)
    ACTIVE = ft.Border.all(2, ft.Colors.PRIMARY)

    def build(self) -> ft.Control:
        c: w.DropZone = self.comp
        self.box = ft.Container(render(c.content, self.shell), expand=c.expand, border=self.IDLE, border_radius=6)
        if not drop_supported():
            return self.box
        import flet_dropzone as ftd

        def dropped(e: Any) -> list[Path]:
            self._highlight(False)
            return [Path(f.path) for f in e.files if f.path]

        return ftd.Dropzone(
            content=self.box,
            expand=c.expand,
            on_dropped=self.shell.handler(c.on_drop, dropped),
            on_entered=lambda e: self._highlight(True),
            on_exited=lambda e: self._highlight(False),
        )

    def _highlight(self, on: bool) -> None:
        """ドラッグ中は枠を色付きにする。"""
        self.box.border = self.ACTIVE if on else self.IDLE
        self.shell.request_update()


# ---------------------------------------------------------------- テーブル


@renders(Table)
class TableRenderer(Renderer):
    def build(self) -> ft.Control:
        c: Table = self.comp
        sh = self.shell

        def on_filter(e: Any) -> None:
            c.model.set_filter(e.control.value or "")
            self.refresh()

        def go(delta: int) -> Callable[[Any], None]:
            def f(e: Any) -> None:
                c.model.set_page(c.model.page + delta)
                self.refresh()

            return f

        self.filter = ft.TextField(
            hint_text="フィルタ（全列から検索）",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            width=280,
            on_change=on_filter,
            visible=c.filterable,
        )
        self.count = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.prev = ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=go(-1), tooltip="前のページ")
        self.next = ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=go(1), tooltip="次のページ")
        self.page_info = ft.Text(size=12)
        header = ft.Row(
            [self.filter, self.count, ft.Container(expand=True), self.prev, self.page_info, self.next],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.body = ft.Container(expand=True)
        self.apply()
        _ = sh
        return ft.Column([header, self.body], expand=c.expand, spacing=4)

    def _sort_handler(self, index: int) -> Callable[[Any], None]:
        def f(e: Any) -> None:
            self.comp.model.sort_by(index)
            self.refresh()

        return f

    def apply(self) -> None:
        c: Table = self.comp
        m = c.model
        self.filter.value = m.filter_text
        if m.total == m.filtered_count:
            self.count.value = f"{m.total:,} 件"
        else:
            self.count.value = f"{m.filtered_count:,} / {m.total:,} 件"
        first, last = m.page_range()
        self.page_info.value = f"{first:,}–{last:,}"
        self.prev.disabled = m.page <= 0
        self.next.disabled = m.page >= m.page_count - 1

        if not m.columns:
            self.body.content = ft.Container(
                ft.Text(c.empty_text, color=ft.Colors.ON_SURFACE_VARIANT), alignment=ft.Alignment.CENTER, expand=True
            )
            return

        table = ft.DataTable(
            columns=[
                ft.DataColumn(
                    label=ft.Text(name, weight=ft.FontWeight.W_600),
                    on_sort=self._sort_handler(i) if c.sortable else None,
                )
                for i, name in enumerate(m.columns)
            ],
            rows=[ft.DataRow(cells=[ft.DataCell(ft.Text(t, size=13, no_wrap=True)) for t in row]) for row in m.page_rows()],
            sort_column_index=m.sort_col,
            sort_ascending=m.sort_asc,
            heading_row_height=36,
            data_row_min_height=28,
            data_row_max_height=32,
            column_spacing=24,
            horizontal_margin=12,
            heading_row_color=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        )
        self.body.content = ft.Column(
            [ft.Row([table], scroll=ft.ScrollMode.ALWAYS)],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
        )


# ---------------------------------------------------------------- フォーム


@renders(Form)
class FormRenderer(Renderer):
    def build(self) -> ft.Control:
        c: Form = self.comp
        self.widgets: dict[str, ft.Control] = {}
        rows: list[ft.Control] = []
        for spec in c.fields:
            rows.append(self._field(spec))
        self.submit = ft.FilledButton(content=c.submit_label, icon=ft.Icons.SAVE, on_click=self._on_submit)
        rows.append(ft.Container(self.submit, padding=ft.Padding.only(top=8)))
        self.apply()
        return ft.Column(rows, spacing=12, width=c.width)

    def _field(self, spec: Any) -> ft.Control:
        c: Form = self.comp
        name = spec.name

        def set_input(value: Any) -> None:
            c.inputs[name] = value

        if spec.kind == "bool":
            ctl: ft.Control = ft.Checkbox(label=spec.label, on_change=lambda e: set_input(bool(e.control.value)))
        elif spec.kind == "enum":
            members = list(spec.enum_type)
            options = [ft.DropdownOption(key=str(i), text=str(m.value)) for i, m in enumerate(members)]

            def on_sel(e: Any, members: list[enum.Enum] = members) -> None:
                try:
                    set_input(members[int(e.control.value)].value)
                except (TypeError, ValueError, IndexError):
                    set_input(None)

            ctl = ft.Dropdown(label=spec.label, options=options, on_select=on_sel, dense=True, width=c.width)
        else:
            numeric = spec.kind in ("int", "float")
            ctl = ft.TextField(
                label=spec.label,
                helper=spec.help or None,
                dense=True,
                keyboard_type=ft.KeyboardType.NUMBER if numeric else None,
                on_change=lambda e: set_input(e.control.value or ""),
            )
        self.widgets[name] = ctl
        return ctl

    def apply(self) -> None:
        c: Form = self.comp
        for spec in c.fields:
            ctl = self.widgets[spec.name]
            value = c.inputs.get(spec.name)
            err = c.errors.get(spec.name)
            if isinstance(ctl, ft.Checkbox):
                ctl.value = bool(value)
            elif isinstance(ctl, ft.Dropdown):
                members = list(spec.enum_type)
                vals = [m.value for m in members]
                ctl.value = str(vals.index(value)) if value in vals else None
                ctl.error_text = err
            elif isinstance(ctl, ft.TextField):
                ctl.value = "" if value is None else str(value)
                ctl.error = err

    async def _on_submit(self, e: Any) -> None:
        c: Form = self.comp
        new, errors = c.submit_values()
        self.refresh()
        if errors:
            return
        c.obj = new
        if c.on_submit:
            await self.shell.invoke(c.on_submit, new)
        self.shell.toast("保存しました")


# ---------------------------------------------------------------- ログビューア


@renders(LogView)
class LogViewRenderer(Renderer):
    def build(self) -> ft.Control:
        c: LogView = self.comp
        self.lv = ft.ListView(expand=True, spacing=0, auto_scroll=True)
        for line in self.shell.recent_logs()[-c.max_lines :]:
            self.lv.controls.append(self._line(line))
        self.shell.subscribe_log(self._on_log)
        return ft.Container(self.lv, expand=True, padding=12)

    def _line(self, line: str) -> ft.Control:
        color = None
        if " ERROR " in line or " CRITICAL " in line:
            color = ft.Colors.ERROR
        elif " WARNING " in line:
            color = ft.Colors.TERTIARY
        return ft.Text(line, size=12, selectable=True, color=color)

    def _on_log(self, line: str) -> None:
        def add() -> None:
            self.lv.controls.append(self._line(line))
            extra = len(self.lv.controls) - self.comp.max_lines
            if extra > 0:
                del self.lv.controls[:extra]
            self.shell.request_update()

        self.shell.call_soon(add)
