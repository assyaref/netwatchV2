"""Open the dashboard in its own desktop window instead of a browser tab.

Order of preference:
  1. pywebview (native window, if installed: pip install pywebview)
  2. Microsoft Edge / Chrome / Chromium in "app" mode (borderless window without tabs
     or address bar; Edge is built into Windows 10/11, so this works with no extra install)
  3. the default browser, as a last resort
Returns when the window is closed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

TITLE = "NETWATCH // Network Surveillance Terminal"
SIZE = (1440, 920)


def _browser_candidates() -> list[str]:
    found: list[str] = []
    if sys.platform == "win32":
        roots = [os.environ.get(k) for k in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
        rels = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                r"BraveSoftware\Brave-Browser\Application\brave.exe"]
        found += [str(Path(r) / rel) for rel in rels for r in roots if r and (Path(r) / rel).is_file()]
    elif sys.platform == "darwin":
        for app in ("Microsoft Edge", "Google Chrome", "Chromium", "Brave Browser"):
            p = Path(f"/Applications/{app}.app/Contents/MacOS/{app}")
            if p.is_file():
                found.append(str(p))
    for name in ("microsoft-edge", "msedge", "google-chrome", "chromium", "chromium-browser", "brave-browser"):
        p = shutil.which(name)
        if p:
            found.append(p)
    return found


def _try_pywebview(url: str) -> bool:
    try:
        import webview  # type: ignore
    except ImportError:
        return False
    try:
        webview.create_window(TITLE, url, width=SIZE[0], height=SIZE[1], min_size=(900, 600),
                              background_color="#02080a")
        webview.start()
        return True
    except Exception as e:  # missing GUI backend etc. → fall back
        print(f"[!] pywebview unavailable ({e}); falling back to app-mode window")
        return False


def _try_app_mode(url: str) -> bool:
    for exe in _browser_candidates():
        # A dedicated profile makes this a separate process that stays alive until the
        # window is closed (otherwise the browser hands the URL to an existing instance).
        profile = Path(tempfile.gettempdir()) / "netwatch-window-profile"
        args = [exe, f"--app={url}", f"--user-data-dir={profile}",
                f"--window-size={SIZE[0]},{SIZE[1]}", "--no-first-run",
                "--no-default-browser-check", "--disable-extensions"]
        print(f"[+] Opening window via {Path(exe).stem} app mode. Close it to stop NETWATCH.")
        try:
            proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            continue
        started = time.monotonic()
        proc.wait()
        if time.monotonic() - started < 3:  # crashed / could not open a display: try next
            continue
        return True
    return False


def open_window(url: str) -> None:
    if sys.platform == "win32":  # own taskbar entry/icon instead of grouping under Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("NETWATCH.Terminal")
        except Exception:
            pass
    if _try_pywebview(url) or _try_app_mode(url):
        return
    print("[!] No embeddable browser found; opening default browser. Press Ctrl+C to stop.")
    webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
