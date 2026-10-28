"""データクラスから入力フォームを自動生成する（UI-06, UI-07）。

対応する型：str / int / float / bool / Enum / Path（Optional も可）。
フィールドの表示名や入力チェックは ``meta()`` で dataclasses.field の metadata に書く。

    @dataclass
    class Settings:
        rows: int = field(default=100, metadata=fk.meta(label="1ページの行数", min=10, max=1000))
"""

from __future__ import annotations

import dataclasses
import enum
import re
import types
import typing
from pathlib import Path
from typing import Any, Callable, Optional

from .base import Component

META_KEY = "fletkit"


def meta(
    label: Optional[str] = None,
    *,
    help: str = "",
    required: bool = False,
    min: Optional[float] = None,
    max: Optional[float] = None,
    pattern: Optional[str] = None,
    hidden: bool = False,
) -> dict[str, Any]:
    """dataclasses.field(metadata=...) に渡す設定。"""
    return {
        META_KEY: {
            "label": label,
            "help": help,
            "required": required,
            "min": min,
            "max": max,
            "pattern": pattern,
            "hidden": hidden,
        }
    }


@dataclasses.dataclass
class FieldSpec:
    name: str
    kind: str  # "str" | "int" | "float" | "bool" | "enum" | "path"
    label: str
    optional: bool = False
    enum_type: Optional[type[enum.Enum]] = None
    help: str = ""
    required: bool = False
    min: Optional[float] = None
    max: Optional[float] = None
    pattern: Optional[str] = None


def _unwrap_optional(tp: Any) -> tuple[Any, bool]:
    origin = typing.get_origin(tp)
    if origin is typing.Union or origin is types.UnionType:
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return tp, False


def form_fields(cls: type) -> list[FieldSpec]:
    """フォームに出すフィールドの一覧。対応しない型と hidden のフィールドは除く。"""
    hints = typing.get_type_hints(cls)
    specs: list[FieldSpec] = []
    for f in dataclasses.fields(cls):
        m = dict(f.metadata.get(META_KEY, {}))
        if m.get("hidden"):
            continue
        tp, optional = _unwrap_optional(hints.get(f.name))
        kind: Optional[str] = None
        enum_type = None
        if tp is bool:
            kind = "bool"
        elif tp is int:
            kind = "int"
        elif tp is float:
            kind = "float"
        elif tp is str:
            kind = "str"
        elif isinstance(tp, type) and issubclass(tp, enum.Enum):
            kind, enum_type = "enum", tp
        elif isinstance(tp, type) and issubclass(tp, Path):
            kind = "path"
        if kind is None:
            continue
        specs.append(
            FieldSpec(
                name=f.name,
                kind=kind,
                label=m.get("label") or f.name,
                optional=optional,
                enum_type=enum_type,
                help=m.get("help") or "",
                required=bool(m.get("required")),
                min=m.get("min"),
                max=m.get("max"),
                pattern=m.get("pattern"),
            )
        )
    return specs


def to_input(spec: FieldSpec, value: Any) -> Any:
    """フィールドの値を入力欄の値に変換する（bool/enum 以外は文字列）。"""
    if spec.kind == "bool":
        return bool(value)
    if spec.kind == "enum":
        return value.value if isinstance(value, enum.Enum) else value
    if value is None:
        return ""
    if spec.kind == "float" and isinstance(value, float) and value.is_integer():
        return str(value)
    return str(value)


def parse_value(spec: FieldSpec, raw: Any) -> tuple[Any, Optional[str]]:
    """入力値を型に合わせて変換し、チェックする。戻り値は (値, エラーメッセージ)。"""
    if spec.kind == "bool":
        return bool(raw), None
    if spec.kind == "enum":
        assert spec.enum_type is not None
        if raw is None or raw == "":
            if spec.optional and not spec.required:
                return None, None
            return None, "選択してください"
        try:
            return spec.enum_type(raw), None
        except ValueError:
            return None, "選択肢にない値です"

    text = "" if raw is None else str(raw).strip()
    if text == "":
        if spec.required:
            return None, "入力してください"
        if spec.optional:
            return None, None
        if spec.kind in ("int", "float"):
            return None, "数値を入力してください"
        return ("" if spec.kind == "str" else Path("")), None

    value: Any
    if spec.kind == "int":
        try:
            value = int(text)
        except ValueError:
            return None, "整数を入力してください"
    elif spec.kind == "float":
        try:
            value = float(text)
        except ValueError:
            return None, "数値を入力してください"
    elif spec.kind == "path":
        value = Path(text)
    else:
        value = text

    if spec.kind in ("int", "float"):
        if spec.min is not None and value < spec.min:
            return None, f"{_num(spec.min)} 以上にしてください"
        if spec.max is not None and value > spec.max:
            return None, f"{_num(spec.max)} 以下にしてください"
    if spec.pattern and spec.kind in ("str", "path") and not re.fullmatch(spec.pattern, text):
        return None, "形式が正しくありません"
    return value, None


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def validate(obj: Any, inputs: dict[str, Any]) -> tuple[Any, dict[str, str]]:
    """入力値を検証し、問題がなければ新しいデータクラスを返す。

    戻り値は (新しいオブジェクト または None, {フィールド名: エラーメッセージ})。
    """
    errors: dict[str, str] = {}
    changes: dict[str, Any] = {}
    for spec in form_fields(type(obj)):
        if spec.name not in inputs:
            continue
        value, err = parse_value(spec, inputs[spec.name])
        if err:
            errors[spec.name] = err
        else:
            changes[spec.name] = value
    if errors:
        return None, errors
    return dataclasses.replace(obj, **changes), {}


class Form(Component):
    """データクラスのインスタンスから入力フォームを作る。

    on_submit には検証済みの新しいインスタンスが渡される（元のインスタンスは変更しない）。
    """

    def __init__(
        self,
        obj: Any,
        on_submit: Optional[Callable[[Any], Any]] = None,
        *,
        submit_label: str = "保存",
        width: int = 420,
    ):
        if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
            raise TypeError("Form にはデータクラスのインスタンスを渡してください")
        self.obj = obj
        self.on_submit = on_submit
        self.submit_label = submit_label
        self.width = width
        self.fields = form_fields(type(obj))
        self.inputs: dict[str, Any] = {s.name: to_input(s, getattr(obj, s.name)) for s in self.fields}
        self.errors: dict[str, str] = {}

    def set_object(self, obj: Any) -> None:
        self.obj = obj
        self.inputs = {s.name: to_input(s, getattr(obj, s.name)) for s in self.fields}
        self.errors = {}
        self.refresh()

    def submit_values(self) -> tuple[Any, dict[str, str]]:
        new, errors = validate(self.obj, self.inputs)
        self.errors = errors
        return new, errors
