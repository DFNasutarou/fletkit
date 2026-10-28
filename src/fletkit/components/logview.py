"""画面内のログビューア（CM-05）。"""

from __future__ import annotations

from .base import Component


class LogView(Component):
    """アプリのログを新しい順ではなく発生順に表示する。最大 max_lines 行。"""

    def __init__(self, max_lines: int = 500):
        self.max_lines = max_lines
