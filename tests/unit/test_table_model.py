import datetime as dt

from fletkit import TableModel, format_cell


def test_format_cell():
    assert format_cell(None) == ""
    assert format_cell(True) == "TRUE"
    assert format_cell(3.0) == "3"
    assert format_cell(0.1) == "0.1"
    assert format_cell(dt.datetime(2026, 10, 28, 13, 5)) == "2026-10-28 13:05:00"
    assert format_cell(dt.date(2026, 1, 2)) == "2026-01-02"
    assert format_cell(dt.time(9, 30)) == "09:30:00"


def test_dict_rows_and_columns():
    m = TableModel([{"a": 1}, {"a": 2, "b": 3}])
    assert m.columns == ["a", "b"]
    assert m.page_rows() == [["1", ""], ["2", "3"]]


def test_list_rows_are_padded():
    m = TableModel([[1], [1, 2, 3]], columns=["x"])
    assert m.columns == ["x", "2", "3"]
    assert m.page_rows()[0] == ["1", "", ""]


def test_sort_mixed_types_blanks_last():
    m = TableModel([[3], ["b"], [None], [1], ["A"]], columns=["v"])
    m.sort_by(0)
    assert [r[0] for r in m.view_rows()] == ["1", "3", "A", "b", ""]
    m.sort_by(0)  # 同じ列でもう一度 → 降順
    assert m.sort_asc is False
    assert [r[0] for r in m.view_rows()] == ["b", "A", "3", "1", ""]


def test_filter_is_case_insensitive_and_resets_page():
    m = TableModel([["Apple"], ["banana"], ["APPLE pie"]], columns=["f"], page_size=1)
    m.set_page(2)
    m.set_filter("apple")
    assert m.page == 0 and m.filtered_count == 2 and m.total == 3


def test_paging():
    m = TableModel([[i] for i in range(25)], columns=["n"], page_size=10)
    assert m.page_count == 3 and m.page_range() == (1, 10)
    m.set_page(5)
    assert m.page == 2 and m.page_range() == (21, 25)
    m.set_filter("zzz")
    assert m.page_count == 1 and m.page_range() == (0, 0)


def test_csv_uses_filtered_sorted_rows(tmp_path):
    m = TableModel([["b", 2], ["a", 1], ["c", 3]], columns=["k", "v"])
    m.set_filter("a")  # "a" だけ残る
    assert m.to_csv() == "k,v\r\na,1\r\n"
    m.set_filter("")
    m.sort_by(1, ascending=False)
    p = tmp_path / "out.csv"
    m.to_csv(p)
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM 付き UTF-8
    assert raw.decode("utf-8-sig").splitlines() == ["k,v", "c,3", "b,2", "a,1"]
