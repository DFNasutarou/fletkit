"""実行環境で使える機能の判定（Flet を import しない）。"""

from __future__ import annotations

import importlib.util
import os

DROP_PACKAGE = "flet_dropzone"


def drop_supported() -> bool:
    """ファイルのドラッグ&ドロップを受け付けられるか。

    flet-dropzone は Flutter 側の拡張なので、`flet build` で作った実行ファイルでしか動かない。
    `python main.py` で起動したときは Flet 同梱のクライアントが使われ、拡張が入っていない。
    - 環境変数 FLETKIT_DROP が "1" / "0" ならそれに従う（確認用）
    - それ以外は、ビルドした実行ファイル（FLET_PLATFORM が設定される）かつ flet-dropzone が入っているとき
    """
    override = os.environ.get("FLETKIT_DROP")
    if override in ("0", "1"):
        return override == "1" and importlib.util.find_spec(DROP_PACKAGE) is not None
    return os.environ.get("FLET_PLATFORM") is not None and importlib.util.find_spec(DROP_PACKAGE) is not None
