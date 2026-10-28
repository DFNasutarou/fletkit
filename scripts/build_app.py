"""アプリを実行ファイルにビルドする。

    python scripts/build_app.py apps/excel_viewer windows   # Windows で実行
    python scripts/build_app.py apps/excel_viewer linux     # Ubuntu で実行

やること：
1. fletkit を アプリの src/ にコピーする（flet build がローカルのパッケージを確実に含めるため）
2. `flet build <platform>` を実行する
3. コピーした fletkit を消す
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[2] not in ("windows", "linux", "macos"):
        print(__doc__)
        return 2
    app_dir = (ROOT / sys.argv[1]).resolve()
    platform = sys.argv[2]
    src = app_dir / "src"
    vendored = src / "fletkit"
    if vendored.exists():
        shutil.rmtree(vendored)
    shutil.copytree(ROOT / "src" / "fletkit", vendored, ignore=shutil.ignore_patterns("__pycache__"))
    try:
        cmd = ["flet", "build", platform, *sys.argv[3:]]
        print("実行:", " ".join(cmd), "（場所:", app_dir, "）")
        return subprocess.call(cmd, cwd=app_dir)
    finally:
        shutil.rmtree(vendored, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
