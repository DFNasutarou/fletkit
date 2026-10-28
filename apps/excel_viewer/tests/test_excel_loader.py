import datetime as dt
import importlib.util
from pathlib import Path

import pytest

from excel_loader import ROW_COLUMN, ExcelBook, ExcelLoadError, _trim

spec = importlib.util.spec_from_file_location("make_sample", Path(__file__).parents[1] / "samples" / "make_sample.py")
make_sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_sample)


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    return ExcelBook(make_sample.make(tmp_path_factory.mktemp("x") / "s.xlsx"))


def test_sheets_hidden(book):
    assert [s.name for s in book.sheets()] == ["計測ログ", "集計", "空のシート"]
    assert [s.name for s in book.sheets(include_hidden=True)] == ["計測ログ", "集計", "設定値", "空のシート"]


def test_values_with_header(book):
    cols, rows = book.values("計測ログ").table(header_first_row=True)
    assert cols[0] == ROW_COLUMN and cols[1] == "時刻" and len(cols) == 6
    assert len(rows) == 1500
    assert rows[0][0] == 2 and isinstance(rows[0][1], dt.datetime)


def test_values_without_header_uses_letters(book):
    cols, rows = book.values("集計").table(header_first_row=False)
    assert cols == [ROW_COLUMN, "A", "B", "C"]  # 値のない末尾列（結合範囲のD列）は除く
    assert rows[0][:3] == [1, "項目", "値"]


def test_merged_cells_only_top_left(book):
    rows = book.values("集計").rows
    assert rows[2][2] == "結合セルの例→" and rows[3][2] is None


def test_formula_without_cached_value_is_blank(book):
    rows = book.values("集計").rows
    assert rows[4][0] == "計算式" and rows[4][1] is None


def test_empty_sheet(book):
    v = book.values("空のシート")
    assert v.size == (0, 0) and v.table(True) == ([], [])


def test_trim():
    assert _trim([[1, None, None], [None, 2, ""], [None, None, None]]) == [[1, None], [None, 2]]
    assert _trim([[None], [" "]]) == []


def test_errors(tmp_path):
    with pytest.raises(ExcelLoadError, match="対応していない"):
        ExcelBook(tmp_path / "a.xls")
    with pytest.raises(ExcelLoadError, match="見つかりません"):
        ExcelBook(tmp_path / "none.xlsx")
    bad = tmp_path / "bad.xlsx"
    bad.write_text("not excel")
    with pytest.raises(ExcelLoadError, match="読み込めません"):
        ExcelBook(bad)
