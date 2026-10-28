"""データテーブル（UI-02〜04）。

ロジック（ソート・フィルタ・ページ分割・CSV出力）は TableModel に置き、Flet なしでテストできる。
Table 部品は TableModel を持ち、表示は _backend が行う。
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, Union

from .base import Component

Rows = Union[Sequence[Sequence[Any]], Sequence[Mapping[str, Any]]]


def format_cell(value: Any) -> str:
    """セル値の標準の表示形式。日付・時刻は ISO 形式。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, dt.datetime):
        if value.microsecond:
            return value.isoformat(sep=" ")
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return repr(value)
    return str(value)


def _sort_key(value: Any) -> tuple:
    """型が混ざった列でも比較できるキー。空欄は常に最後。"""
    if value is None or value == "":
        return (3, "")
    if isinstance(value, bool):
        return (0, float(value))
    if isinstance(value, (int, float)):
        return (0, float(value)) if not (isinstance(value, float) and math.isnan(value)) else (2, "")
    if isinstance(value, dt.datetime):
        return (1, value.isoformat())
    if isinstance(value, (dt.date, dt.time)):
        return (1, value.isoformat())
    return (2, str(value).casefold())


class TableModel:
    def __init__(
        self,
        rows: Optional[Rows] = None,
        columns: Optional[Sequence[str]] = None,
        page_size: int = 100,
        formatter: Callable[[Any], str] = format_cell,
    ):
        self.page_size = max(1, int(page_size))
        self.formatter = formatter
        self.columns: list[str] = []
        self._rows: list[list[Any]] = []
        self._text: list[list[str]] = []
        self.filter_text = ""
        self.sort_col: Optional[int] = None
        self.sort_asc = True
        self.page = 0
        self._view: Optional[list[int]] = None
        self.set_data(rows or [], columns)

    # ---- データ設定 ----
    def set_data(self, rows: Rows, columns: Optional[Sequence[str]] = None) -> None:
        rows = list(rows)
        if rows and isinstance(rows[0], Mapping):
            keys: list[str] = list(columns) if columns else []
            if not columns:
                seen: set[str] = set()
                for r in rows:
                    for k in r.keys():  # type: ignore[union-attr]
                        if k not in seen:
                            seen.add(k)
                            keys.append(k)
            data = [[r.get(k) for k in keys] for r in rows]  # type: ignore[union-attr]
            cols = keys
        else:
            data = [list(r) for r in rows]  # type: ignore[arg-type]
            width = max((len(r) for r in data), default=0)
            cols = list(columns) if columns else [str(i + 1) for i in range(width)]
            width = max(width, len(cols))
            if len(cols) < width:
                cols += [str(i + 1) for i in range(len(cols), width)]
            data = [r + [None] * (width - len(r)) for r in data]
        self.columns = cols
        self._rows = data
        self._text = [[self.formatter(v) for v in r] for r in data]
        self.sort_col = None
        self.sort_asc = True
        self.page = 0
        self._view = None

    # ---- 状態変更 ----
    def set_filter(self, text: str) -> None:
        self.filter_text = text or ""
        self.page = 0
        self._view = None

    def sort_by(self, col: int, ascending: Optional[bool] = None) -> None:
        if not 0 <= col < len(self.columns):
            raise IndexError(col)
        if ascending is None:
            ascending = not self.sort_asc if self.sort_col == col else True
        self.sort_col = col
        self.sort_asc = ascending
        self._view = None

    def set_page(self, page: int) -> None:
        self.page = min(max(0, page), self.page_count - 1)

    def set_page_size(self, size: int) -> None:
        self.page_size = max(1, int(size))
        self.page = 0

    # ---- 参照 ----
    @property
    def total(self) -> int:
        return len(self._rows)

    def _indices(self) -> list[int]:
        if self._view is not None:
            return self._view
        idx = list(range(len(self._rows)))
        needle = self.filter_text.casefold().strip()
        if needle:
            idx = [i for i in idx if any(needle in t.casefold() for t in self._text[i])]
        if self.sort_col is not None:
            c = self.sort_col
            idx.sort(key=lambda i: _sort_key(self._rows[i][c]), reverse=not self.sort_asc)
            if not self.sort_asc:
                # 降順でも空欄は最後に置く
                blanks = [i for i in idx if _sort_key(self._rows[i][c])[0] == 3]
                idx = [i for i in idx if _sort_key(self._rows[i][c])[0] != 3] + blanks
        self._view = idx
        return idx

    @property
    def filtered_count(self) -> int:
        return len(self._indices())

    @property
    def page_count(self) -> int:
        return max(1, math.ceil(self.filtered_count / self.page_size))

    def page_rows(self) -> list[list[str]]:
        """現在のページの行（表示用文字列）。"""
        idx = self._indices()
        start = self.page * self.page_size
        return [self._text[i] for i in idx[start : start + self.page_size]]

    def page_range(self) -> tuple[int, int]:
        """現在のページが表示している行番号（1始まり、両端含む）。0件なら (0, 0)。"""
        n = self.filtered_count
        if n == 0:
            return (0, 0)
        start = self.page * self.page_size
        return (start + 1, min(start + self.page_size, n))

    def view_rows(self, as_text: bool = True) -> list[list[Any]]:
        """フィルタ・ソート後の全行。"""
        src = self._text if as_text else self._rows
        return [src[i] for i in self._indices()]

    # ---- CSV ----
    def to_csv(self, target: Union[str, Path, io.TextIOBase, None] = None, *, encoding: str = "utf-8-sig") -> Optional[str]:
        """フィルタ・ソート後の内容を CSV にする。target を省略すると文字列を返す。"""
        def write(f: Any) -> None:
            w = csv.writer(f, lineterminator="\r\n")
            w.writerow(self.columns)
            w.writerows(self.view_rows())

        if target is None:
            buf = io.StringIO()
            write(buf)
            return buf.getvalue()
        if isinstance(target, (str, Path)):
            with open(target, "w", encoding=encoding, newline="") as f:
                write(f)
            return None
        write(target)
        return None


class Table(Component):
    """一覧表示の部品。フィルタ欄・件数・ページ送りが付く。

    rows には list[dict] または 2次元のリストを渡す。
    """

    def __init__(
        self,
        rows: Optional[Rows] = None,
        columns: Optional[Sequence[str]] = None,
        *,
        sortable: bool = True,
        filterable: bool = True,
        page_size: int = 100,
        formatter: Callable[[Any], str] = format_cell,
        empty_text: str = "データがありません",
        expand: bool = True,
    ):
        self.model = TableModel(rows, columns, page_size, formatter)
        self.sortable = sortable
        self.filterable = filterable
        self.empty_text = empty_text
        self.expand = expand

    def set_rows(self, rows: Rows, columns: Optional[Sequence[str]] = None) -> None:
        self.model.set_data(rows, columns)
        self.refresh()

    def set_filter(self, text: str) -> None:
        self.model.set_filter(text)
        self.refresh()

    def set_page_size(self, size: int) -> None:
        self.model.set_page_size(size)
        self.refresh()

    async def export_csv(self, path: Union[str, Path, None] = None, *, file_name: str = "export.csv") -> Optional[Path]:
        """CSV に書き出す。path を省略すると保存ダイアログを出す。書き出したパスを返す。"""
        from .. import dialog

        if path is None:
            if not self.model.columns:
                await dialog.info("書き出すデータがありません。")
                return None
            chosen = await dialog.save_file(file_name=file_name, ext=["csv"])
            if chosen is None:
                return None
            path = chosen
        p = Path(path)
        if p.suffix.lower() != ".csv":
            p = p.with_suffix(".csv")
        self.model.to_csv(p)
        import logging

        logging.getLogger("fletkit.table").info("CSVを書き出しました: %s（%d行）", p, self.model.filtered_count)
        return p
