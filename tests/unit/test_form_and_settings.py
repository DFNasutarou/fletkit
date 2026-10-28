import asyncio
import enum
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fletkit as fk
from fletkit._backend.handlers import accepted_args, call_handler
from fletkit.components.form import form_fields, validate
from fletkit.services.settings import SettingsStore, config_dir


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


@dataclass
class S:
    name: str = field(default="", metadata=fk.meta("名前", pattern=r"[a-z]+"))
    count: int = field(default=1, metadata=fk.meta(min=1, max=9))
    ratio: Optional[float] = None
    on: bool = False
    color: Color = Color.RED
    path: Path = Path("/tmp")
    recent: list[str] = field(default_factory=list)


def test_form_fields_skip_unsupported():
    names = [f.name for f in form_fields(S)]
    assert names == ["name", "count", "ratio", "on", "color", "path"]


def test_validate_ok_and_errors():
    obj = S()
    new, err = validate(obj, {"name": "abc", "count": "3", "ratio": "", "color": "blue", "on": True})
    assert err == {} and new.count == 3 and new.ratio is None and new.color is Color.BLUE and new.on is True
    assert obj.count == 1  # 元は変えない
    new, err = validate(obj, {"name": "ABC", "count": "x"})
    assert new is None and set(err) == {"name", "count"}
    _, err = validate(obj, {"count": "10"})
    assert err == {"count": "9 以下にしてください"}


def test_settings_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    store = SettingsStore("x", S, p)
    assert store.load() == S()
    store.save(S(name="a", count=2, color=Color.BLUE, recent=["r1"]))
    store.save_window({"width": 800.0, "height": 600.0})
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["color"] == "blue" and data["_window"]["width"] == 800.0
    store2 = SettingsStore("x", S, p)
    s = store2.load()
    assert s.count == 2 and s.color is Color.BLUE and s.recent == ["r1"]
    assert store2.window == {"width": 800.0, "height": 600.0}
    # ユーザー設定を保存してもウィンドウ状態は残る
    store2.save(s)
    assert SettingsStore("x", S, p).window["height"] == 600.0


def test_settings_broken_values_fall_back(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"count": "many", "color": "green", "unknown": 1, "name": "ok"}), encoding="utf-8")
    s = SettingsStore("x", S, p).load()
    assert s.count == 1 and s.color is Color.RED and s.name == "ok"
    p.write_text("{broken", encoding="utf-8")
    assert SettingsStore("x", S, p).load() == S()


def test_config_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("FLETKIT_CONFIG_DIR", str(tmp_path))
    assert config_dir("app") == tmp_path / "app"


def test_call_handler_passes_only_accepted_args():
    got = []
    asyncio.run(call_handler(lambda: got.append("none"), 1, 2))
    asyncio.run(call_handler(lambda v: got.append(v), 1, 2))

    async def a(v):
        got.append(("async", v))

    asyncio.run(call_handler(a, 3))
    assert got == ["none", 1, ("async", 3)]
    assert accepted_args(lambda *a: None) == 99
