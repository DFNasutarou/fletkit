"""設定の保存・復元（CM-03, CM-04）。

設定はデータクラスで定義し、OS標準のユーザー設定フォルダに JSON で保存する。
- Windows: %APPDATA%/<app_id>/settings.json
- Linux:   $XDG_CONFIG_HOME/<app_id>/settings.json（未設定なら ~/.config）

ウィンドウ位置・サイズはユーザー設定とは別に "_window" キーに保存する。
"""

from __future__ import annotations

import dataclasses
import enum
import json
import logging
import os
import sys
import types
import typing
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")

log = logging.getLogger("fletkit.settings")

WINDOW_KEY = "_window"


def config_dir(app_id: str) -> Path:
    """アプリ用のユーザー設定フォルダを返す（作成はしない）。"""
    override = os.environ.get("FLETKIT_CONFIG_DIR")
    if override:
        return Path(override) / app_id
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / app_id
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_id
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / app_id


def to_jsonable(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return value


def _coerce(tp: Any, raw: Any) -> Any:
    """JSON の値を型ヒントに合わせて変換する。変換できなければ ValueError。"""
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is typing.Union or origin is types.UnionType:
        if raw is None and type(None) in args:
            return None
        for a in args:
            if a is type(None):
                continue
            try:
                return _coerce(a, raw)
            except (ValueError, TypeError):
                continue
        raise ValueError(f"{raw!r} は {tp} に変換できません")
    if origin in (list, tuple):
        if not isinstance(raw, list):
            raise ValueError("list ではありません")
        inner = args[0] if args else Any
        items = [_coerce(inner, v) for v in raw]
        return items if origin is list else tuple(items)
    if origin is dict:
        if not isinstance(raw, dict):
            raise ValueError("dict ではありません")
        return dict(raw)
    if tp is Any:
        return raw
    if isinstance(tp, type):
        if issubclass(tp, enum.Enum):
            return tp(raw)
        if issubclass(tp, Path):
            return Path(raw)
        if tp is bool:
            if isinstance(raw, bool):
                return raw
            raise ValueError("bool ではありません")
        if tp is int:
            if isinstance(raw, bool) or not isinstance(raw, (int, float)) or int(raw) != raw:
                raise ValueError("int ではありません")
            return int(raw)
        if tp is float:
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError("float ではありません")
            return float(raw)
        if tp is str:
            if not isinstance(raw, str):
                raise ValueError("str ではありません")
            return raw
    return raw


def from_dict(cls: type[T], data: dict[str, Any]) -> T:
    """dict からデータクラスを復元する。未知のキーは無視し、壊れた値は既定値に戻す。"""
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):  # type: ignore[arg-type]
        if f.name not in data:
            continue
        try:
            kwargs[f.name] = _coerce(hints.get(f.name, Any), data[f.name])
        except (ValueError, TypeError) as ex:
            log.warning("設定 %s の値 %r を読めないため既定値を使います: %s", f.name, data[f.name], ex)
    return cls(**kwargs)


class SettingsStore(Generic[T]):
    """設定データクラスとウィンドウ状態をファイルに保存・復元する。"""

    def __init__(self, app_id: str, cls: Optional[type[T]], path: Optional[Path] = None):
        self.cls = cls
        self.path = path or config_dir(app_id) / "settings.json"
        self._raw: dict[str, Any] = self._read()

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as ex:
            log.warning("設定ファイル %s を読めませんでした: %s", self.path, ex)
            return {}

    def load(self) -> Optional[T]:
        self._raw = self._read()
        if self.cls is None:
            return None
        user = {k: v for k, v in self._raw.items() if k != WINDOW_KEY}
        return from_dict(self.cls, user)

    def save(self, value: Optional[T]) -> None:
        data: dict[str, Any] = {}
        if value is not None:
            data.update(to_jsonable(value))
        if WINDOW_KEY in self._raw:
            data[WINDOW_KEY] = self._raw[WINDOW_KEY]
        self._raw = data
        self._write()

    @property
    def window(self) -> dict[str, float]:
        w = self._raw.get(WINDOW_KEY)
        return dict(w) if isinstance(w, dict) else {}

    def save_window(self, geometry: dict[str, float]) -> None:
        self._raw = self._read() | {WINDOW_KEY: geometry}
        self._write()

    def _write(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._raw, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as ex:
            log.error("設定ファイル %s に保存できませんでした: %s", self.path, ex)
