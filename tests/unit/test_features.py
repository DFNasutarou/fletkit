"""実行環境の判定（ドラッグ&ドロップを使えるか）。"""

from __future__ import annotations

import pytest

from fletkit._backend import features


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch):
    """flet-dropzone が入っているかを切り替える。"""

    def set_installed(value: bool) -> None:
        monkeypatch.setattr(features.importlib.util, "find_spec", lambda name: object() if value else None)

    monkeypatch.delenv("FLETKIT_DROP", raising=False)
    monkeypatch.delenv("FLET_PLATFORM", raising=False)
    return set_installed


def test_drop_only_in_built_app(installed, monkeypatch: pytest.MonkeyPatch) -> None:
    installed(True)
    assert features.drop_supported() is False  # python main.py で起動
    monkeypatch.setenv("FLET_PLATFORM", "windows")  # flet build で作った実行ファイル
    assert features.drop_supported() is True
    installed(False)
    assert features.drop_supported() is False


def test_drop_override(installed, monkeypatch: pytest.MonkeyPatch) -> None:
    installed(True)
    monkeypatch.setenv("FLETKIT_DROP", "1")
    assert features.drop_supported() is True
    monkeypatch.setenv("FLET_PLATFORM", "linux")
    monkeypatch.setenv("FLETKIT_DROP", "0")
    assert features.drop_supported() is False
    installed(False)
    monkeypatch.setenv("FLETKIT_DROP", "1")
    assert features.drop_supported() is False
