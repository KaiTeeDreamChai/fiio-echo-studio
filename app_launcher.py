#!/usr/bin/env python3
"""
FiiO Echo Studio - Native Desktop App Launcher
Powers the standalone macOS Application using WKWebView (pywebview)
and a background HTTP engine.

On macOS the launcher also builds a real application menu (AppKit NSMenu) whose
items drive the web UI through a `fiio:menu` CustomEvent, so ⌘R/⌘B/⌘T/⌘O work
like native actions instead of dead menu entries.

Usage:
    FiiO Echo Studio                      # normal GUI window
    FiiO Echo Studio --headless --port 58999
                                          # API only (for smoke tests / CI), no window
    FiiO Echo Studio --dump-menu          # print the native menu tree and exit
"""
import argparse
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.core.bin_resolver import get_bundle_dir
from engine.server import StudioAPIHandler

APP_NAME = "FiiO Echo Studio"
PROJECT_URL = "https://github.com/KaiTeeDreamChai/fiio-echo-studio"


def find_free_port(preferred: int = 57123) -> int:
    """Checks if preferred port is free, otherwise finds an available ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def start_server_in_thread(port: int):
    """Runs the API & static asset server in background thread."""
    httpd = ThreadingHTTPServer(("127.0.0.1", port), StudioAPIHandler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


# --------------------------------------------------------------------------- menu
def _dispatch_menu_action(action: str) -> None:
    """Forward a native menu action to the React app (or handle it directly)."""
    if action == "homepage":
        webbrowser.open(PROJECT_URL)
        return

    try:
        import webview

        if not webview.windows:
            return
        window = webview.windows[0]
        payload = json.dumps(action)
        window.evaluate_js(
            "window.dispatchEvent(new CustomEvent('fiio:menu', { detail: %s }))" % payload
        )
    except Exception as exc:  # never let a menu action crash the app
        print(f"[menu] dispatch failed: {exc}", file=sys.stderr)


_MENU_TARGET = None


def build_macos_menu(emitter=None):
    """Build and install the native macOS menu bar. Returns the NSMenu."""
    global _MENU_TARGET

    if sys.platform != "darwin":
        return None

    import AppKit
    import objc
    from Foundation import NSObject

    app = AppKit.NSApplication.sharedApplication()
    emit = emitter or _dispatch_menu_action

    class _MenuTarget(NSObject):
        def handleMenu_(self, sender):
            try:
                emit(str(sender.representedObject()))
            except Exception as exc:
                print(f"[menu] {exc}", file=sys.stderr)

    target = _MenuTarget.alloc().init()
    target.retain()
    _MENU_TARGET = target

    command = AppKit.NSCommandKeyMask
    shift = AppKit.NSShiftKeyMask
    control = AppKit.NSControlKeyMask

    def add(menu, title, action=None, key="", mask=None, rep=None, use_target=True):
        item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, action or "", key
        )
        if mask is not None:
            item.setKeyEquivalentModifierMask_(mask)
        if action and use_target:
            item.setTarget_(target)
        if rep is not None:
            item.setRepresentedObject_(rep)
        menu.addItem_(item)
        return item

    def submenu(parent, title):
        item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "", "")
        menu = AppKit.NSMenu.alloc().init()
        menu.setTitle_(title)
        item.setSubmenu_(menu)
        parent.addItem_(item)
        return menu

    main_menu = AppKit.NSMenu.alloc().init()

    # Application menu
    app_item = AppKit.NSMenuItem.alloc().init()
    app_item.setTitle_(APP_NAME)
    main_menu.addItem_(app_item)
    app_menu = AppKit.NSMenu.alloc().init()
    app_item.setSubmenu_(app_menu)

    add(app_menu, f"关于 {APP_NAME}", "orderFrontStandardAboutPanel:", "")
    app_menu.addItem_(AppKit.NSMenuItem.separatorItem())

    services_menu = AppKit.NSMenu.alloc().init()
    app.setServicesMenu_(services_menu)
    services_item = add(app_menu, "服务", None, "")
    services_item.setSubmenu_(services_menu)
    app_menu.addItem_(AppKit.NSMenuItem.separatorItem())

    add(app_menu, f"隐藏 {APP_NAME}", "hide:", "h", command, use_target=False)
    hide_others = add(app_menu, "隐藏其他", "hideOtherApplications:", "h", command, use_target=False)
    hide_others.setKeyEquivalentModifierMask_(command | AppKit.NSAlternateKeyMask)
    add(app_menu, "显示全部", "unhideAllApplications:", "", use_target=False)
    app_menu.addItem_(AppKit.NSMenuItem.separatorItem())
    add(app_menu, f"退出 {APP_NAME}", "terminate:", "q", command, use_target=False)

    # File menu
    file_menu = submenu(main_menu, "文件")
    add(file_menu, "重新探测", "handleMenu:", "r", command, "rescan")
    add(file_menu, "构建乐库", "handleMenu:", "b", command, "build")
    add(file_menu, "选择输出目录…", "handleMenu:", "o", command, "choose-root")
    file_menu.addItem_(AppKit.NSMenuItem.separatorItem())
    add(file_menu, "关闭窗口", "performClose:", "w", command, use_target=False)

    # Edit menu (required for text fields)
    edit_menu = submenu(main_menu, "编辑")
    add(edit_menu, "撤销", "undo:", "z", command, use_target=False)
    add(edit_menu, "重做", "redo:", "z", command | shift, use_target=False)
    edit_menu.addItem_(AppKit.NSMenuItem.separatorItem())
    add(edit_menu, "剪切", "cut:", "x", command, use_target=False)
    add(edit_menu, "复制", "copy:", "c", command, use_target=False)
    add(edit_menu, "粘贴", "paste:", "v", command, use_target=False)
    add(edit_menu, "全选", "selectAll:", "a", command, use_target=False)

    # View menu
    view_menu = submenu(main_menu, "视图")
    add(view_menu, "切换主题", "handleMenu:", "t", command, "theme")
    add(view_menu, "重新加载界面", "handleMenu:", "r", command | shift, "reload")
    view_menu.addItem_(AppKit.NSMenuItem.separatorItem())
    add(
        view_menu,
        "进入全屏",
        "toggleFullScreen:",
        "f",
        control | command,
        use_target=False,
    )

    # Window menu
    window_menu = submenu(main_menu, "窗口")
    add(window_menu, "最小化", "performMiniaturize:", "m", command, use_target=False)
    add(window_menu, "缩放", "performZoom:", "", use_target=False)
    window_menu.addItem_(AppKit.NSMenuItem.separatorItem())
    add(window_menu, "前置全部窗口", "arrangeInFront:", "", use_target=False)

    # Help menu
    help_menu = submenu(main_menu, "帮助")
    add(help_menu, "项目主页", "handleMenu:", "", None, "homepage")
    add(help_menu, f"关于 {APP_NAME}", "orderFrontStandardAboutPanel:", "", use_target=False)

    app.setMainMenu_(main_menu)
    return main_menu


def _install_macos_menu() -> None:
    try:
        build_macos_menu()
        print("[menu] native menu installed", flush=True)
    except Exception as exc:
        print(f"[menu] failed to install native menu: {exc}", file=sys.stderr)


def _install_macos_menu_on_main_thread() -> None:
    """pywebview runs start(func=...) in a worker thread; AppKit needs the main one."""
    try:
        from PyObjCTools import AppHelper

        AppHelper.callAfter(_install_macos_menu)
    except Exception:
        _install_macos_menu()


def _dump_menu(menu, depth: int = 0) -> None:
    if menu is None:
        print("(no menu)")
        return
    for item in menu.itemArray():
        title = str(item.title())
        key = str(item.keyEquivalent() or "")
        action = str(item.action() or "")
        represented = item.representedObject()
        suffix = f" [{represented}]" if represented else ""
        print("  " * depth + f"- {title!r} key={key!r} action={action!r}{suffix}")
        submenu = item.submenu()
        if submenu is not None:
            _dump_menu(submenu, depth + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="FiiO Echo Studio desktop app")
    parser.add_argument("--headless", action="store_true", help="run the API only (no window)")
    parser.add_argument("--port", type=int, default=0, help="fixed port (default: auto)")
    parser.add_argument("--dump-menu", action="store_true", help="print the native menu and exit")
    args = parser.parse_args()

    if args.dump_menu:
        _dump_menu(build_macos_menu(emitter=lambda action: None))
        return

    port = args.port or find_free_port()
    httpd = start_server_in_thread(port)
    print(f"Starting FiiO Echo Studio Engine on http://127.0.0.1:{port} ...", flush=True)
    time.sleep(0.2)

    if args.headless:
        print("Headless mode: press Ctrl+C to stop.", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("Shutting down...", flush=True)
        finally:
            httpd.shutdown()
            httpd.server_close()
        return

    import webview

    webview.create_window(
        title=APP_NAME,
        url=f"http://127.0.0.1:{port}",
        width=1340,
        height=840,
        min_size=(980, 640),
        text_select=True,
    )
    webview.start(debug=False, func=_install_macos_menu_on_main_thread)
    print("Application window closed.")


if __name__ == "__main__":
    main()
