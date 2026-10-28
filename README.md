# fletkit

業務ツールを少ないコードで作るための、自分用の [Flet](https://flet.dev/) ラッパーライブラリです。
アプリ側のコードは `import fletkit as fk` だけを使い、Flet を直接 import しません。
Flet の版上げで直す場所は `src/fletkit/_backend/` に限られます。

- 対応 Flet：**1.0 系**（`flet>=1.0,<1.1` に固定）
- Python：3.12 以上
- 動作環境：Windows / Ubuntu のデスクトップ

## 最小の例

```python
from dataclasses import dataclass, field
import fletkit as fk

@dataclass
class Settings:
    rows_per_page: int = field(default=100, metadata=fk.meta("1ページの行数", min=10, max=1000))

app = fk.App("サンプル", settings=Settings)

@app.page("/", label="一覧", icon="table_view")
def list_page(ctx: fk.Context):
    table = fk.Table([{"名前": "A", "値": 1}, {"名前": "B", "値": 2}], page_size=ctx.settings.rows_per_page)
    return fk.Column(fk.Toolbar(fk.Button("CSV出力", table.export_csv, icon="download")), table, expand=True)

@app.page("/settings", label="設定", icon="settings")
def settings_page(ctx: fk.Context):
    return fk.Form(ctx.settings, on_submit=ctx.save_settings)

if __name__ == "__main__":
    app.run()
```

## 提供するもの

| 種類 | 内容 |
| --- | --- |
| 外枠 | ヘッダ（アプリ名＋サブタイトル）、サイドメニュー、ステータスバー。`@app.page` で登録した順に並ぶ |
| 部品 | `Text` `Button` `TextInput` `Checkbox` `Select` `Tabs` `Menu` `Column` `Row` `Toolbar` `Spacer` `Divider` |
| テーブル | `Table`：ソート、フィルタ、ページ送り、CSV 出力（UTF-8 BOM 付き） |
| フォーム | `Form`：データクラスから入力欄を自動生成。`fk.meta()` で表示名・必須・範囲・正規表現 |
| ダイアログ | `fk.dialog.info / error / confirm / open_file / open_files / save_file / pick_folder / progress` |
| 設定 | データクラスを JSON で保存。Windows は `%APPDATA%\<app_id>`、Ubuntu は `~/.config/<app_id>`。ウィンドウ位置・サイズも保存 |
| ログ | 標準 `logging`。ファイル（`<設定フォルダ>/logs/app.log`、1MB×5世代）と画面の「ログ」ページ |
| 逃げ道 | `fk.raw(flet_control)` で Flet の部品を直接置ける（版上げ時の確認対象） |

イベントハンドラは通常の関数でも async 関数でもかまいません。ハンドラ内で例外が起きると、ログに残したうえでエラーダイアログを出します。
重い処理は `await ctx.run_in_thread(関数, 引数...)` で別スレッドに逃がします。

## フォルダ構成

```
src/fletkit/
  core/         App, Context（ページ登録・設定・ステータス）
  components/   部品（Flet に依存しない）
  services/     設定の保存、ログ
  dialog.py     ダイアログ API
  _backend/     Flet への変換（ここだけ import flet）
tests/
  contract/     _backend の契約テスト（Flet 版上げ時に最初に実行）
  unit/         ロジックのテスト
examples/catalog/   全部品を並べたカタログアプリ
apps/excel_viewer/  最初の題材：Excel ビューア
scripts/build_app.py  実行ファイルのビルド
```

## 開発の始め方

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   Ubuntu: source .venv/bin/activate
pip install -e ".[dev]"
pytest                              # テスト（35件）
python examples/catalog/main.py     # 部品カタログ
python apps/excel_viewer/src/main.py [Excelファイル]
```

Ubuntu でファイル選択ダイアログを使うには zenity が必要です：`sudo apt install zenity`

## Excel ビューア

`apps/excel_viewer/`。Excel ファイルを開き、シートを切り替えてセルの値を表で見ます。

- 対応形式：.xlsx / .xlsm（.xls は対象外）
- 読むのはセルの値だけ。図形・コメント・書式・画像・グラフは扱わない
- 数式は最後に保存された計算結果。結合セルは左上だけに値を出す
- 時刻 0:00 の日時は日付だけ表示、それ以外は `2026-10-28 13:05:00` 形式
- 非表示シートは設定で表示可能。「1行目を見出しにする」で列名を切り替え
- 先頭列は Excel 上の行番号。フィルタ・ソート後の内容を CSV に出力
- 最近開いたファイル（5件）・最後に開いたフォルダを保存
- 起動引数にファイルパスを渡すとそのファイルを開く

動作確認用のサンプルは `python apps/excel_viewer/samples/make_sample.py` で作れます。

## ビルド（exe 化）

Windows 版は Windows で、Ubuntu 版は Ubuntu でビルドします（別 OS 向けはビルドできません）。
事前に Flutter SDK と、Windows なら Visual Studio（C++ によるデスクトップ開発）、Ubuntu なら GTK3 などの開発パッケージが必要です。`flet doctor` で確認できます。

```bash
pip install "flet-cli>=1.0,<1.1"
python scripts/build_app.py apps/excel_viewer windows   # → apps/excel_viewer/build/windows
python scripts/build_app.py apps/excel_viewer linux     # → apps/excel_viewer/build/linux
```

スクリプトは fletkit をアプリの `src/` に一時コピーしてから `flet build` を実行し、終わったらコピーを消します。

## Flet の版上げ手順

1. Flet の[破壊的変更一覧](https://flet.dev/docs/updates/breaking-changes/)を読む
2. `pyproject.toml` の固定範囲を上げて再インストール
3. `pytest tests/contract` を実行し、落ちたところを `_backend` で直す
4. `pytest` 全体を実行
5. カタログアプリと Excel ビューアを起動して目で確認
6. `grep -rn "fk.raw\|import flet" apps examples` で直接 Flet を使っている箇所を確認
