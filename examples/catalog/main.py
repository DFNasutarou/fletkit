"""部品カタログ：fletkit の全部品を並べたアプリ。Flet を版上げしたら目で確認する。

    python examples/catalog/main.py
"""

from __future__ import annotations

import asyncio
import enum
from dataclasses import dataclass, field

import fletkit as fk


class Mode(enum.Enum):
    NORMAL = "通常"
    DETAIL = "詳細"


@dataclass
class Settings:
    name: str = field(default="", metadata=fk.meta("名前", required=True))
    rows: int = field(default=100, metadata=fk.meta("行数", min=10, max=1000, help="10〜1000"))
    ratio: float = field(default=0.5, metadata=fk.meta("比率", min=0, max=1))
    enabled: bool = field(default=True, metadata=fk.meta("有効にする"))
    mode: Mode = field(default=Mode.NORMAL, metadata=fk.meta("モード"))


app = fk.App("fletkit カタログ", settings=Settings, app_id="fletkit-catalog")


@app.page("/", label="基本部品", icon="widgets")
def basics(ctx: fk.Context) -> fk.Component:
    out = fk.Text("ここに結果が出ます", style="muted")

    def show(text: str) -> None:
        out.set(text)
        ctx.status(text)

    async def ask() -> None:
        ok = await fk.dialog.confirm("続けますか？")
        show(f"確認ダイアログ: {ok}")

    async def work() -> None:
        async with fk.dialog.progress("処理中", "準備しています") as p:
            for i in range(5):
                p.update(f"{i + 1}/5 件目", (i + 1) / 5)
                await asyncio.sleep(0.3)
        show("進捗ダイアログ: 完了")

    async def pick() -> None:
        path = await fk.dialog.open_file()
        show(f"選んだファイル: {path}")

    def fail() -> None:
        raise ValueError("わざと起こしたエラーです")

    return fk.Column(
        fk.Text("ボタンとダイアログ", style="title"),
        fk.Row(
            fk.Button("確認", ask, primary=True),
            fk.Button("進捗", work, icon="hourglass_bottom"),
            fk.Button("ファイルを選ぶ", pick, icon="folder_open"),
            fk.Button("お知らせ", lambda: fk.dialog.info("お知らせの例です")),
            fk.Button("エラーを起こす", fail, icon="error_outline"),
        ),
        fk.Text("入力", style="title"),
        fk.Row(
            fk.TextInput("テキスト", on_change=lambda v: show(f"入力: {v}"), width=240),
            fk.Checkbox("チェック", on_change=lambda v: show(f"チェック: {v}")),
            fk.Select("選択", ["A", "B", "C"], "A", on_change=lambda v: show(f"選択: {v}"), width=160),
            fk.Menu("メニュー", [("x", "項目X"), ("y", "項目Y")], on_select=lambda v: show(f"メニュー: {v}")),
        ),
        fk.Tabs(["タブ1", "タブ2", "タブ3"], on_change=lambda i: show(f"タブ: {i}")),
        out,
        padding=24,
        spacing=16,
        scroll=True,
        expand=True,
    )


@app.page("/table", label="テーブル", icon="table_view")
def table(ctx: fk.Context) -> fk.Component:
    rows = [{"No": i, "名前": f"項目{i:03}", "値": i * 1.5, "偶数": i % 2 == 0} for i in range(1, 501)]
    t = fk.Table(rows, page_size=50)
    return fk.Column(
        fk.Toolbar(fk.Button("CSV出力", t.export_csv, icon="download")),
        fk.Column(t, expand=True, padding=12),
        spacing=0,
        expand=True,
    )


@app.page("/form", label="フォーム", icon="edit_note")
def form(ctx: fk.Context) -> fk.Component:
    return fk.Column(fk.Text("設定フォーム", style="title"), fk.Form(ctx.settings, on_submit=ctx.save_settings), padding=24)


if __name__ == "__main__":
    app.run()
