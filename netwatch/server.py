"""NETWATCH web server: JSON API + dashboard UI, protected by an operator login.

All settings (capture mode, interface, subnets, credentials) are managed from the UI and
saved to ~/.netwatch/config.json. Command-line flags are optional overrides.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import DEFAULT_PASS, Config, list_interfaces, validate_subnets
from ._version import __version__
from .engine import Engine
from .store import Store
from . import labels, router

STATIC = Path(__file__).parent / "static"
SESSION_TTL = 8 * 3600
MAX_FAILS = 5
LOCKOUT = 300
MIN_PASS = 6


class Auth:
    def __init__(self, config: Config):
        self.config = config
        self.sessions: dict[str, float] = {}
        self.fails: dict[str, list] = {}
        self.lock = threading.Lock()

    def locked(self, client: str) -> int:
        with self.lock:
            count, until = self.fails.get(client, [0, 0])
            return max(0, int(until - time.time())) if count >= MAX_FAILS else 0

    def _new_session(self) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = time.time() + SESSION_TTL
        return token

    def login(self, client: str, user: str, password: str) -> str | None:
        ok = self.config.check(user, password)
        with self.lock:
            if not ok:
                rec = self.fails.setdefault(client, [0, 0])
                if rec[0] >= MAX_FAILS and rec[1] < time.time():
                    rec[0] = 0
                rec[0] += 1
                if rec[0] >= MAX_FAILS:
                    rec[1] = time.time() + LOCKOUT
                return None
            self.fails.pop(client, None)
            return self._new_session()

    def setup(self, user: str, password: str) -> str:
        self.config.set_password(user, password)
        with self.lock:
            return self._new_session()

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        with self.lock:
            exp = self.sessions.get(token)
            if exp is None or exp < time.time():
                self.sessions.pop(token, None)
                return False
            return True

    def logout(self, token: str | None, everyone: bool = False) -> None:
        with self.lock:
            if everyone:
                self.sessions.clear()
            else:
                self.sessions.pop(token or "", None)


def _cookie(token: str) -> str:
    return f"nw_session={token}; HttpOnly; SameSite=Strict; Path=/"


def make_handler(store: Store, auth: Auth, engine: Engine, config: Config):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NETWATCH"

        def log_message(self, fmt, *args):  # quiet
            pass

        # ---- utils ------------------------------------------------------
        def _token(self) -> str | None:
            c = SimpleCookie(self.headers.get("Cookie", ""))
            return c["nw_session"].value if "nw_session" in c else None

        def _json(self, code: int, obj, headers: dict | None = None) -> None:
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 20_000:
                return {}
            try:
                b = json.loads(self.rfile.read(n) or b"{}")
                return b if isinstance(b, dict) else {}
            except json.JSONDecodeError:
                return {}

        def _same_origin(self) -> bool:
            """Reject cross-site POSTs (another web page talking to this local server)."""
            origin = self.headers.get("Origin")
            return not origin or urlparse(origin).netloc == self.headers.get("Host")

        def _config_view(self) -> dict:
            return {"mode": config["mode"], "iface": config["iface"], "subnets": config["subnets"],
                    "user": config["user"], "active": engine.active, "error": engine.error}

        # ---- routes -----------------------------------------------------
        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if not url.path.startswith("/api/"):
                return self._static(url.path)
            if url.path == "/api/session":
                return self._json(200, {"authenticated": auth.valid(self._token()),
                                        "setup_required": not config.has_password,
                                        "default_password": bool(config.data.get("default_password")),
                                        **engine.meta()})
            if not auth.valid(self._token()):
                return self._json(401, {"error": "unauthorized"})
            if url.path == "/api/status":
                return self._json(200, {**store.status(), **engine.meta(), "version": __version__,
                                        "default_password": bool(config.data.get("default_password"))})
            if url.path == "/api/devices":
                return self._json(200, store.list_devices())
            if url.path == "/api/device":
                d = store.device_detail(q.get("ip", ""))
                return self._json(200, d) if d else self._json(404, {"error": "target not observed"})
            if url.path == "/api/events":
                since = int(q.get("since", "0") or 0)
                return self._json(200, store.events_since(since, q.get("ip") or None))
            if url.path == "/api/config":
                return self._json(200, self._config_view())
            if url.path == "/api/interfaces":
                return self._json(200, list_interfaces())
            if url.path == "/api/labels":
                return self._json(200, labels.all_labels())
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            client = self.client_address[0]
            b = self._body()

            if url.path == "/api/setup":  # first run: create the operator account
                if config.has_password:
                    return self._json(409, {"error": "Operator already configured"})
                user, pw = str(b.get("username", "")).strip(), str(b.get("password", ""))
                if not user or len(pw) < MIN_PASS:
                    return self._json(400, {"error": f"Agent ID required, passphrase min {MIN_PASS} chars"})
                return self._json(200, {"ok": True}, {"Set-Cookie": _cookie(auth.setup(user, pw))})

            if url.path == "/api/login":
                if not config.has_password:
                    return self._json(409, {"error": "Setup required"})
                wait = auth.locked(client)
                if wait:
                    return self._json(429, {"error": f"Terminal locked. Retry in {wait}s."})
                token = auth.login(client, str(b.get("username", "")), str(b.get("password", "")))
                if not token:
                    return self._json(401, {"error": "ACCESS DENIED — invalid credentials"})
                return self._json(200, {"ok": True}, {"Set-Cookie": _cookie(token)})

            if url.path == "/api/logout":
                auth.logout(self._token())
                return self._json(200, {"ok": True}, {"Set-Cookie": "nw_session=; Max-Age=0; Path=/"})

            if not auth.valid(self._token()):
                return self._json(401, {"error": "unauthorized"})

            if url.path == "/api/config":
                mode = b.get("mode", config["mode"])
                if mode not in ("live", "demo"):
                    return self._json(400, {"error": "mode must be live or demo"})
                iface = str(b.get("iface", config["iface"]) or "")
                try:
                    subnets = validate_subnets(list(b.get("subnets", config["subnets"]) or []))
                except (ValueError, TypeError) as e:
                    return self._json(400, {"error": f"Invalid subnet: {e}"})
                config.data.update(mode=mode, iface=iface, subnets=subnets)
                config.save()
                try:
                    engine.apply(mode, iface, subnets)
                except RuntimeError as e:
                    return self._json(400, {"error": str(e), **self._config_view()})
                return self._json(200, {"ok": True, **self._config_view()})

            if url.path == "/api/credentials":
                if not config.check(config["user"], str(b.get("current", ""))):
                    return self._json(400, {"error": "Current passphrase is incorrect"})
                user = str(b.get("username") or config["user"]).strip()
                pw = str(b.get("password", ""))
                if len(pw) < MIN_PASS:
                    return self._json(400, {"error": f"New passphrase must be at least {MIN_PASS} chars"})
                if pw == DEFAULT_PASS:
                    return self._json(400, {"error": "Choose a passphrase different from the default"})
                config.set_password(user, pw)
                auth.logout(None, everyone=True)
                return self._json(200, {"ok": True, "relogin": True},
                                  {"Set-Cookie": "nw_session=; Max-Age=0; Path=/"})

            if url.path == "/api/purge":
                store.reset(clear=True)
                return self._json(200, {"ok": True})
            if url.path == "/api/label":
                labels.set_label(str(b.get("ip", "")), str(b.get("name", "")))
                return self._json(200, {"ok": True})
            if url.path == "/api/block":
                ip = str(b.get("ip", ""))
                if b.get("unblock"):
                    return self._json(200, router.unblock_ip(ip))
                return self._json(200, router.block_ip(ip))

            self._json(404, {"error": "not found"})

        def _static(self, path: str) -> None:
            rel = "index.html" if path in ("", "/") else path.lstrip("/")
            f = (STATIC / rel).resolve()
            if STATIC.resolve() not in f.parents or not f.is_file():
                self.send_error(404)
                return
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _relaunch_as_admin(argv: list[str]) -> bool:
    """On Windows, live capture needs Administrator: re-launch elevated (UAC prompt).

    Returns True when an elevated copy was started and this process should exit.
    """
    if sys.platform != "win32":
        return False
    import ctypes
    import subprocess
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return False
        frozen = getattr(sys, "frozen", False)  # NETWATCH.exe (PyInstaller) vs python -m netwatch
        params = subprocess.list2cmdline(argv if frozen else ["-m", "netwatch", *argv])
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, os.getcwd(), 1)
    except Exception:
        return False
    if rc > 32:
        print("[+] NETWATCH started in a new Administrator window.")
        return True
    print("[!] Administrator rights declined; live capture may fail (DEMO mode still works).")
    return False


def _fatal(msg: str) -> None:
    """Report a startup error; NETWATCH.exe has no console, so use a message box there."""
    if sys.platform == "win32" and (sys.stdout is None or getattr(sys, "frozen", False)):
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "NETWATCH", 0x10)
    else:
        print(f"[x] {msg}")
    sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="netwatch", description="Office network monitoring terminal. "
                                "All settings can be changed from the UI; flags below are optional.")
    p.add_argument("--subnet", action="append", help="Override office LAN range (CIDR), repeatable")
    p.add_argument("--iface", help="Override network interface to capture on")
    p.add_argument("--demo", action="store_true", help="Start in demo (simulated traffic) mode")
    p.add_argument("--host", default="127.0.0.1", help="Dashboard bind address (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--no-window", action="store_true",
                   help="Do not open the desktop window (server only, open the URL yourself)")
    p.add_argument("--version", action="version", version=f"NETWATCH {__version__}")
    p.add_argument("--no-elevate", action="store_true",
                   help="Windows: do not ask for Administrator rights on start")
    argv = sys.argv[1:] if argv is None else argv
    a = p.parse_args(argv)
    if not a.no_elevate and _relaunch_as_admin(argv):
        return

    config = Config()
    # Environment variables can pre-seed the operator account (e.g. for unattended installs).
    if os.environ.get("NETWATCH_PASS") and not config.has_password:
        config.set_password(os.environ.get("NETWATCH_USER", "admin"), os.environ["NETWATCH_PASS"])

    mode = "demo" if a.demo else config["mode"]
    iface = a.iface if a.iface is not None else config["iface"]
    subnets = a.subnet if a.subnet else config["subnets"]

    store = Store(subnets or ["192.168.1.0/24"])
    engine = Engine(store, config)
    try:
        engine.apply(mode, iface, subnets)
        print(f"[+] NETWATCH {engine.meta()['mode']} on {', '.join(engine.active['subnets'])}")
    except RuntimeError as e:
        print(f"[!] {e}\n    The dashboard is still available: fix it in SETTINGS.")

    try:
        srv = ThreadingHTTPServer((a.host, a.port), make_handler(store, Auth(config), engine, config))
    except OSError as e:
        engine.stop()
        _fatal(f"Cannot open the dashboard on port {a.port}: NETWATCH is probably already running.\n\n({e})")
    url = f"http://127.0.0.1:{a.port}" if a.host in ("0.0.0.0", "::") else f"http://{a.host}:{a.port}"
    print(f"[+] Dashboard: {url}")
    if config.data.get("default_password"):
        print("[!] Default login admin / admin123 is active. Change it in SETTINGS.")
    if a.no_window:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n[+] Shutting down")
        return
    from .window import open_window
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        open_window(url)
    except KeyboardInterrupt:
        pass
    print("[+] Window closed, shutting down")
    srv.shutdown()
    os._exit(0)  # stop capture threads immediately


if __name__ == "__main__":
    main()
