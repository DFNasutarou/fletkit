"""アプリ定義とページ登録（UI-01, CM-01）。"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from ..components.base import Component


@dataclass
class PageSpec:
    route: str
    label: str
    icon: Optional[str]
    builder: Callable[["Context"], Component]  # noqa: F821


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_-]+", "-", text).strip("-").lower()
    return s or "fletkit-app"


class App:
    """fletkit アプリ。

    Args:
        title: ウィンドウとヘッダに出すアプリ名。
        settings: 設定のデータクラス（省略可）。起動時に読み込み、ctx.settings で使える。
        app_id: 設定・ログの保存フォルダ名。省略時は title から作る（英数字以外は '-'）。
        log_file: ログをファイルにも出すか。
        log_viewer: サイドメニューに「ログ」ページを追加するか。
        window_size: 初回起動時のウィンドウサイズ（幅, 高さ）。
        assets_dir: 画像やフォントを置くフォルダ（省略時はアプリと同じ場所の "assets"）。
        font: 画面全体に使うフォントファイル。assets_dir からの相対パス（例 "fonts/BIZUDGothic.ttf"）。
    """

    def __init__(
        self,
        title: str,
        *,
        settings: Optional[type] = None,
        app_id: Optional[str] = None,
        log_file: bool = True,
        log_viewer: bool = True,
        window_size: tuple[int, int] = (1200, 800),
        assets_dir: Optional[str] = None,
        font: Optional[str] = None,
    ):
        self.title = title
        self.settings_cls = settings
        self.app_id = app_id or _slug(title)
        self.log_file = log_file
        self.log_viewer = log_viewer
        self.window_size = window_size
        self.assets_dir = assets_dir
        self.font = font
        self.pages: list[PageSpec] = []
        self.on_start: Optional[Callable[[Any], Any]] = None

    def page(self, route: str, *, label: Optional[str] = None, icon: Optional[str] = None):
        """ページを登録するデコレータ。登録順にサイドメニューに並ぶ。

        ページ関数は Context を受け取り、部品（Component）を返す。
        ページ関数は最初に表示したときに1回だけ呼ばれ、以後は状態が保たれる。
        """
        if not route.startswith("/"):
            raise ValueError("route は '/' で始めてください")
        if any(p.route == route for p in self.pages):
            raise ValueError(f"route {route} は登録済みです")

        def deco(fn: Callable[[Any], Component]):
            self.pages.append(PageSpec(route, label or route, icon, fn))
            return fn

        return deco

    def started(self, fn: Callable[[Any], Any]):
        """全ページ準備後、最初の画面表示の直後に呼ばれる関数を登録するデコレータ。"""
        self.on_start = fn
        return fn

    def run(self, argv: Optional[Sequence[str]] = None, *, web: bool = False, port: int = 0) -> None:
        """アプリを起動する。web=True でブラウザ表示（開発・確認用）。"""
        from .._backend.shell import launch

        if not self.pages:
            raise RuntimeError("ページが1つも登録されていません")
        launch(self, list(sys.argv[1:] if argv is None else argv), web=web, port=port)
