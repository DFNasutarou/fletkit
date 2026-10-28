# CLAUDE.md

fletkit は Flet 1.0 系のラッパーライブラリ（利用者はオーナー本人のみ、業務ツール用、Windows / Ubuntu デスクトップ）。

**作業を始める前に `docs/requirements.md` を読むこと。** ヒアリング結果、要件と実装状況、決定事項、未決事項、次にやることがまとまっている。作業で状況が変わったら同ファイルを更新する。使い方は README.md。

## 守ること

- `import flet` してよいのは `src/fletkit/_backend/` と `tests/contract/` だけ。`components/` `core/` `services/` と各アプリは Flet に依存させない
- ロジック（ソート・フィルタ・検証・保存など）は Flet なしでテストできる場所に置き、`tests/unit/` でテストする
- 部品を追加したら：`components/` に部品クラス → `_backend/render.py` に Renderer（`@renders`）→ `tests/contract/test_render.py` に契約テスト → `examples/catalog/main.py` に追加
- UI の文言・コメント・ドキュメントは日本語
- Flet の固定範囲は `pyproject.toml` の `flet>=1.0,<1.1`。勝手に広げない

## コマンド

```bash
pip install -e ".[dev]"
pytest                      # 全テスト
pytest tests/contract       # Flet 版上げ時に最初に実行
```

画面の確認（ヘッドレス環境）：`FLET_FORCE_WEB_SERVER=1` を付けて `app.run(web=True, port=8550)` で起動し、ブラウザで開く。
web 表示では CDN を使わないため日本語フォントが出ない。`App(assets_dir=..., font=...)` で日本語フォントを指定すると確認しやすい。
