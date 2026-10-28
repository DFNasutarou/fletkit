"""Excel ビューア：Excel ファイルを開き、シートを切り替えてセルの値を表で見る。

起動時にファイルパスを引数で渡すと、そのファイルを開く。
    python main.py C:\\data\\log.xlsx
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fletkit as fk
from excel_loader import ExcelBook, ExcelLoadError

APP_TITLE = "Excel ビューア"
RECENT_MAX = 5


def format_value(value: object) -> str:
    """Excel の日付セルは時刻 0:00 の datetime になるので、そのときは日付だけ出す。"""
    if isinstance(value, dt.datetime) and value.time() == dt.time(0, 0):
        return value.date().isoformat()
    return fk.format_cell(value)


@dataclass
class Settings:
    header_first_row: bool = field(default=True, metadata=fk.meta("1行目を見出しにする"))
    show_hidden_sheets: bool = field(default=False, metadata=fk.meta("非表示のシートもタブに出す"))
    rows_per_page: int = field(default=200, metadata=fk.meta("1ページの行数", min=50, max=2000, help="50〜2000"))
    last_dir: str = field(default="", metadata=fk.meta(hidden=True))
    recent_files: list[str] = field(default_factory=list)


app = fk.App(APP_TITLE, settings=Settings, app_id="excel-viewer", window_size=(1280, 800))


class Viewer:
    """ビューア画面の状態と操作。"""

    def __init__(self, ctx: fk.Context):
        self.ctx = ctx
        s: Settings = ctx.settings
        self.book: Optional[ExcelBook] = None
        self.sheet_names: list[str] = []
        self.current: Optional[str] = None

        self.recent = fk.Menu("最近のファイル", self._recent_items(), on_select=self.open_path, icon="history")
        self.header = fk.Checkbox("1行目を見出しにする", s.header_first_row, on_change=self.on_header)
        self.export = fk.Button("CSV出力", self.export_csv, icon="download", enabled=False)
        self.tabs = fk.Tabs(on_change=self.on_tab)
        self.table = fk.Table(page_size=s.rows_per_page, formatter=format_value, empty_text="「開く」から Excel ファイルを選んでください")
        self.view = fk.Column(
            fk.Toolbar(
                fk.Button("開く", self.choose_file, icon="folder_open", primary=True),
                self.recent,
                self.header,
                fk.Spacer(),
                self.export,
            ),
            self.tabs,
            fk.Column(self.table, expand=True, padding=12),
            spacing=0,
            expand=True,
        )
        ctx.on_settings_changed(self.on_settings)

    # ---- ファイルを開く ----
    async def choose_file(self) -> None:
        s: Settings = self.ctx.settings
        path = await fk.dialog.open_file(ext=["xlsx", "xlsm"], initial_dir=s.last_dir or None, title="Excel ファイルを開く")
        if path:
            await self.open_path(path)

    async def open_path(self, path: str | Path) -> None:
        path = Path(path)
        log = self.ctx.log
        try:
            async with fk.dialog.progress("読み込み中", path.name):
                book = await self.ctx.run_in_thread(ExcelBook, path)
        except ExcelLoadError as ex:
            log.warning("読み込み失敗: %s", ex)
            self._forget_recent(path)
            await fk.dialog.error(str(ex), title="開けませんでした")
            return
        if self.book is not None:
            self.book.close()
        self.book = book
        log.info("開きました: %s", path)
        self._remember(path)
        self.ctx.subtitle(str(path))
        self.export.set_enabled(True)
        await self.reload_sheets()

    async def reload_sheets(self, keep: Optional[str] = None) -> None:
        if self.book is None:
            return
        s: Settings = self.ctx.settings
        infos = self.book.sheets(include_hidden=s.show_hidden_sheets)
        self.sheet_names = [i.name for i in infos]
        labels = [f"{i.name}（非表示）" if i.hidden else i.name for i in infos]
        index = self.sheet_names.index(keep) if keep in self.sheet_names else 0
        self.tabs.set_labels(labels, index)
        if self.sheet_names:
            await self.show_sheet(self.sheet_names[index])
        else:
            self.current = None
            self.table.set_rows([])
            self.ctx.status("表示できるシートがありません")

    # ---- シート表示 ----
    async def on_tab(self, index: int) -> None:
        if 0 <= index < len(self.sheet_names):
            await self.show_sheet(self.sheet_names[index])

    async def show_sheet(self, name: str) -> None:
        assert self.book is not None
        self.ctx.status(f"{name} を読み込み中…")
        values = await self.ctx.run_in_thread(self.book.values, name)
        columns, rows = values.table(self.ctx.settings.header_first_row)
        self.current = name
        self.table.set_rows(rows, columns)
        n_rows, n_cols = values.size
        self.ctx.status(f"{name}　使用範囲 {n_rows:,} 行 × {n_cols:,} 列" if n_rows else f"{name}　（空のシート）")

    async def on_header(self, value: bool) -> None:
        self.ctx.save_settings(dataclasses.replace(self.ctx.settings, header_first_row=value))

    async def on_settings(self, s: Settings) -> None:
        self.header.value = s.header_first_row
        self.header.refresh()
        self.table.model.page_size = s.rows_per_page
        if self.book is not None:
            await self.reload_sheets(keep=self.current)
        else:
            self.table.set_page_size(s.rows_per_page)

    # ---- CSV ----
    async def export_csv(self) -> None:
        if self.book is None or self.current is None:
            return
        name = f"{self.book.path.stem}_{self.current}.csv"
        out = await self.table.export_csv(file_name=name)
        if out:
            self.ctx.status(f"CSV を書き出しました：{out}")

    # ---- 最近のファイル ----
    def _recent_items(self) -> list[tuple[str, str]]:
        return [(p, Path(p).name) for p in self.ctx.settings.recent_files]

    def _remember(self, path: Path) -> None:
        s: Settings = self.ctx.settings
        p = str(path.resolve())
        recent = [p] + [x for x in s.recent_files if x != p]
        self.ctx.save_settings(
            dataclasses.replace(s, recent_files=recent[:RECENT_MAX], last_dir=str(path.resolve().parent))
        )
        self.recent.set_items(self._recent_items())

    def _forget_recent(self, path: Path) -> None:
        s: Settings = self.ctx.settings
        p = str(path.resolve())
        if p in s.recent_files:
            self.ctx.save_settings(dataclasses.replace(s, recent_files=[x for x in s.recent_files if x != p]))
            self.recent.set_items(self._recent_items())


_viewer: Optional[Viewer] = None


@app.page("/", label="ビューア", icon="table_view")
def viewer_page(ctx: fk.Context) -> fk.Component:
    global _viewer
    _viewer = Viewer(ctx)
    return _viewer.view


@app.page("/settings", label="設定", icon="settings")
def settings_page(ctx: fk.Context) -> fk.Component:
    def save(new: Settings) -> None:
        # フォームに出ていない項目（最近のファイルなど）は現在の値を残す
        cur: Settings = ctx.settings
        ctx.save_settings(
            dataclasses.replace(
                cur,
                header_first_row=new.header_first_row,
                show_hidden_sheets=new.show_hidden_sheets,
                rows_per_page=new.rows_per_page,
            )
        )

    form = fk.Form(ctx.settings, on_submit=save)
    ctx.on_settings_changed(lambda s: form.set_object(s))
    return fk.Column(fk.Text("設定", style="title"), form, padding=24, spacing=16)


@app.started
async def on_start(ctx: fk.Context) -> None:
    files = [a for a in ctx.args if not a.startswith("-")]
    if files and _viewer is not None:
        await _viewer.open_path(files[0])


if __name__ == "__main__":
    app.run()
