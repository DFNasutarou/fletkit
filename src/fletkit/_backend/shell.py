"""アプリの外枠（ヘッダ・サイドメニュー・ステータスバー）とダイアログの実装。"""

from __future__ import annotations

import asyncio
import logging
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

import flet as ft

from ..components.base import Component
from ..components.logview import LogView
from ..core.app import App, PageSpec
from ..core.context import Context, ShellPort
from ..services.logs import LogBuffer, setup_logging
from ..services.settings import SettingsStore
from .handlers import call_handler
from .render import icon, render
from .runtime import set_current_shell

log = logging.getLogger("fletkit")

LOG_ROUTE = "/_log"


class _Progress:
    def __init__(self, shell: "Shell", title: str, message: str):
        self.shell = shell
        self.text = ft.Text(message)
        self.bar = ft.ProgressBar(width=360, value=None)
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Column([self.text, self.bar], tight=True, spacing=12),
        )

    def update(self, message: Optional[str] = None, value: Optional[float] = None) -> None:
        if message is not None:
            self.text.value = message
        self.bar.value = value
        self.shell.request_update()


class Shell(ShellPort):
    def __init__(self, app: App, page: ft.Page, ctx: Context, buffer: LogBuffer, store: SettingsStore[Any]):
        self.app = app
        self.page = page
        self.ctx = ctx
        self.buffer = buffer
        self.store = store
        self.pages: list[PageSpec] = list(app.pages)
        if app.log_viewer:
            self.pages.append(PageSpec(LOG_ROUTE, "ログ", "receipt_long", lambda ctx: LogView()))
        self._built: dict[str, ft.Control] = {}
        self._current: Optional[str] = None
        self._geometry: dict[str, float] = {}
        self.file_picker: Optional[ft.FilePicker] = None

    # ------------------------------------------------------------ 起動
    def build(self) -> None:
        page = self.page
        page.title = self.app.title
        page.padding = 0
        page.spacing = 0
        page.theme_mode = ft.ThemeMode.LIGHT
        font_family = None
        if self.app.font:
            page.fonts = {"fletkit-app": self.app.font}
            font_family = "fletkit-app"
        page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO, font_family=font_family)

        self.title = ft.Text(self.app.title, size=16, weight=ft.FontWeight.W_600)
        self.subtitle = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT, no_wrap=True, expand=True)
        header = ft.Container(
            ft.Row([self.title, self.subtitle], spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )
        self.status_text = ft.Text("準備完了", size=12, color=ft.Colors.ON_SURFACE_VARIANT, no_wrap=True)
        status = ft.Container(
            self.status_text,
            padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )
        self.content = ft.Container(expand=True)

        body: list[ft.Control] = []
        if len(self.pages) > 1:
            self.rail = ft.NavigationRail(
                selected_index=0,
                label_type=ft.NavigationRailLabelType.ALL,
                min_width=80,
                destinations=[
                    ft.NavigationRailDestination(icon=icon(p.icon) or ft.Icons.CIRCLE_OUTLINED, label=p.label)
                    for p in self.pages
                ],
                on_change=self._on_rail,
            )
            body = [self.rail, ft.VerticalDivider(width=1), self.content]
        else:
            self.rail = None
            body = [self.content]

        page.add(
            ft.Column(
                [header, ft.Row(body, expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH), status],
                expand=True,
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        )
        self.file_picker = ft.FilePicker()
        self._setup_window()
        self.navigate(self.pages[0].route)

    def _setup_window(self) -> None:
        page = self.page
        if page.web:
            return
        win = page.window
        geo = self.store.window
        w, h = self.app.window_size
        win.width = geo.get("width", w)
        win.height = geo.get("height", h)
        if "left" in geo and "top" in geo:
            win.left = geo["left"]
            win.top = geo["top"]
        win.maximized = bool(geo.get("maximized", False))
        win.min_width, win.min_height = 640, 400
        win.prevent_close = True
        self._geometry = {k: v for k, v in geo.items()}
        win.on_event = self._on_window_event

    async def _on_window_event(self, e: Any) -> None:
        win = self.page.window
        t = e.type
        if t in (ft.WindowEventType.RESIZED, ft.WindowEventType.MOVED, ft.WindowEventType.MAXIMIZE, ft.WindowEventType.UNMAXIMIZE):
            if not win.maximized:
                for k in ("width", "height", "left", "top"):
                    v = getattr(win, k)
                    if v is not None:
                        self._geometry[k] = float(v)
            self._geometry["maximized"] = bool(win.maximized)
        elif t == ft.WindowEventType.CLOSE:
            await self._shutdown()

    async def _shutdown(self) -> None:
        try:
            if self._geometry:
                self.store.save_window(self._geometry)
        except Exception:
            log.exception("ウィンドウ状態の保存に失敗しました")
        log.info("終了します")
        await self.page.window.destroy()

    # ------------------------------------------------------------ 画面遷移
    def _on_rail(self, e: Any) -> None:
        idx = int(e.control.selected_index)
        self.navigate(self.pages[idx].route)

    def navigate(self, route: str) -> None:
        spec = next((p for p in self.pages if p.route == route), None)
        if spec is None:
            log.warning("未登録のページです: %s", route)
            return
        if route not in self._built:
            try:
                comp = spec.builder(self.ctx)
                if not isinstance(comp, Component):
                    raise TypeError(f"ページ {route} の関数が部品を返していません: {comp!r}")
                self._built[route] = render(comp, self)
            except Exception as ex:
                log.exception("ページ %s の作成に失敗しました", route)
                self._built[route] = ft.Container(
                    ft.Text(f"ページを表示できません：{ex}", color=ft.Colors.ERROR, selectable=True), padding=24
                )
        self._current = route
        self.content.content = self._built[route]
        if self.rail is not None:
            self.rail.selected_index = self.pages.index(spec)
        self.request_update()

    # ------------------------------------------------------------ ShellPort
    def set_status(self, text: str) -> None:
        self.status_text.value = text
        self.request_update()

    def set_subtitle(self, text: str) -> None:
        self.subtitle.value = text
        self.request_update()

    def close(self) -> None:
        if self.page.web:
            return
        self.page.run_task(self._shutdown)

    # ------------------------------------------------------------ Renderer 向け
    def request_update(self) -> None:
        try:
            self.page.update()
        except Exception:  # 起動前・終了後など
            pass

    def call_soon(self, fn: Callable[[], None]) -> None:
        try:
            self.page.loop.call_soon_threadsafe(fn)
        except Exception:
            pass

    def subscribe_log(self, fn: Callable[[str], None]) -> Callable[[], None]:
        return self.buffer.subscribe(fn)

    def recent_logs(self) -> list[str]:
        return list(self.buffer.records)

    def toast(self, text: str) -> None:
        try:
            self.page.show_dialog(ft.SnackBar(ft.Text(text), duration=ft.Duration(seconds=2)))
        except Exception:
            log.info(text)

    def handler(self, fn: Optional[Callable[..., Any]], *extractors: Callable[[Any], Any]) -> Any:
        """Flet のイベントからユーザーハンドラを呼ぶ関数を作る。extractor はイベントを引数に変換する。"""
        if fn is None and not extractors:
            return None

        async def on_event(e: Any) -> None:
            args = [ex(e) for ex in extractors]
            if fn is not None:
                await self.invoke(fn, *args)

        return on_event

    async def invoke(self, fn: Callable[..., Any], *args: Any) -> Any:
        try:
            return await call_handler(fn, *args)
        except Exception as ex:
            log.exception("処理中にエラーが発生しました")
            await self.dialog_message("エラー", str(ex) or type(ex).__name__, kind="error", detail=traceback.format_exc())
            return None

    # ------------------------------------------------------------ ダイアログ
    async def _show_and_wait(self, dialog: ft.AlertDialog, fut: "asyncio.Future[Any]") -> Any:
        self.page.show_dialog(dialog)
        try:
            return await fut
        finally:
            try:
                self.page.pop_dialog()
            except Exception:
                pass

    async def dialog_message(self, title: str, message: str, kind: str = "info", detail: str = "") -> None:
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        def close(e: Any) -> None:
            if not fut.done():
                fut.set_result(None)

        body: list[ft.Control] = [ft.Text(message, selectable=True)]
        if detail:
            body.append(
                ft.ExpansionTile(
                    title=ft.Text("詳細", size=12),
                    controls=[ft.Container(ft.Column([ft.Text(detail, size=11, selectable=True)], scroll=ft.ScrollMode.AUTO), height=200)],
                )
            )
        dlg = ft.AlertDialog(
            modal=True,
            icon=ft.Icon(ft.Icons.ERROR_OUTLINE if kind == "error" else ft.Icons.INFO_OUTLINE,
                         color=ft.Colors.ERROR if kind == "error" else None),
            title=ft.Text(title),
            content=ft.Column(body, tight=True, width=480),
            actions=[ft.FilledButton(content="OK", on_click=close)],
        )
        await self._show_and_wait(dlg, fut)

    async def dialog_confirm(self, title: str, message: str, ok: str, cancel: str) -> bool:
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        def answer(v: bool) -> Callable[[Any], None]:
            def f(e: Any) -> None:
                if not fut.done():
                    fut.set_result(v)

            return f

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton(content=cancel, on_click=answer(False)), ft.FilledButton(content=ok, on_click=answer(True))],
        )
        return bool(await self._show_and_wait(dlg, fut))

    def _picker(self) -> ft.FilePicker:
        assert self.file_picker is not None
        return self.file_picker

    @staticmethod
    def _type(ext: Optional[list[str]]) -> dict[str, Any]:
        if ext:
            return {"file_type": ft.FilePickerFileType.CUSTOM, "allowed_extensions": [x.lstrip(".") for x in ext]}
        return {"file_type": ft.FilePickerFileType.ANY}

    async def dialog_open_files(self, ext: Optional[list[str]], initial_dir: Optional[str], title: Optional[str], multiple: bool = True) -> list[Path]:
        files = await self._picker().pick_files(
            dialog_title=title, initial_directory=initial_dir, allow_multiple=multiple, **self._type(ext)
        )
        out = [Path(f.path) for f in files or [] if f.path]
        if files and not out:
            await self.dialog_message("お知らせ", "ブラウザ表示ではファイルのパスを取得できません。デスクトップで起動してください。")
        return out

    async def dialog_open_file(self, ext: Optional[list[str]], initial_dir: Optional[str], title: Optional[str]) -> Optional[Path]:
        files = await self.dialog_open_files(ext, initial_dir, title, multiple=False)
        return files[0] if files else None

    async def dialog_save_file(self, file_name: str, ext: Optional[list[str]], initial_dir: Optional[str], title: Optional[str]) -> Optional[Path]:
        if self.page.web:
            await self.dialog_message("お知らせ", "ブラウザ表示では保存先を選べません。デスクトップで起動してください。")
            return None
        path = await self._picker().save_file(
            dialog_title=title, file_name=file_name or None, initial_directory=initial_dir, **self._type(ext)
        )
        return Path(path) if path else None

    async def dialog_pick_folder(self, initial_dir: Optional[str], title: Optional[str]) -> Optional[Path]:
        if self.page.web:
            return None
        path = await self._picker().get_directory_path(dialog_title=title, initial_directory=initial_dir)
        return Path(path) if path else None

    async def dialog_progress_open(self, title: str, message: str) -> _Progress:
        p = _Progress(self, title, message)
        self.page.show_dialog(p.dialog)
        await asyncio.sleep(0)  # ダイアログを先に描画させる
        return p

    async def dialog_progress_close(self, handle: _Progress) -> None:
        try:
            self.page.pop_dialog()
        except Exception:
            pass
        self.request_update()


def launch(app: App, args: list[str], *, web: bool = False, port: int = 0) -> None:
    logger, buffer, log_path = setup_logging(app.app_id, to_file=app.log_file)
    store: SettingsStore[Any] = SettingsStore(app.app_id, app.settings_cls)
    settings = store.load()
    ctx = Context(app, store, settings, logger, args, log_path)
    log.info("%s を起動します（設定: %s）", app.title, store.path)

    async def main(page: ft.Page) -> None:
        shell = Shell(app, page, ctx, buffer, store)
        ctx._shell = shell
        set_current_shell(shell)
        shell.build()
        if app.on_start is not None:
            await shell.invoke(app.on_start, ctx)

    # web 表示では CanvasKit などを CDN から取らず、同梱のものを配信する（社内ネットワーク向け）
    kwargs: dict[str, Any] = {}
    if app.assets_dir:
        kwargs["assets_dir"] = app.assets_dir
    ft.run(main, view=ft.AppView.WEB_BROWSER if web else ft.AppView.FLET_APP, port=port, no_cdn=web, **kwargs)
