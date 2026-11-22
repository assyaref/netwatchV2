"""Starts/stops the traffic source (live capture or demo) according to the current settings."""
from __future__ import annotations

import threading

from .config import Config, list_interfaces
from .store import Store


class Engine:
    def __init__(self, store: Store, config: Config):
        self.store = store
        self.config = config
        self.source = None
        self.error: str | None = None
        self.active: dict = {}
        self.lock = threading.Lock()

    def _resolve(self, mode: str, iface: str, subnets: list[str]) -> tuple[str, list[str]]:
        if mode == "demo":
            return "", ["192.168.1.0/24"]  # simulated office network
        if not subnets:
            info = list_interfaces()
            name = iface or info["default"]
            match = next((i for i in info["interfaces"] if i["name"] == name), None)
            subnets = (match or {}).get("subnets") or []
        if not subnets:
            raise ValueError("Could not detect the office subnet automatically. Enter it in SETTINGS.")
        return iface, subnets

    def apply(self, mode: str, iface: str, subnets: list[str], clear: bool = True) -> None:
        """Switch source. Raises on failure (and leaves the engine stopped with .error set)."""
        with self.lock:
            self.stop()
            try:
                iface, subnets = self._resolve(mode, iface, subnets)
                self.store.reset(subnets, clear=clear)
                if mode == "demo":
                    from .demo import Demo
                    src = Demo(self.store)
                else:
                    from .capture import Capture
                    src = Capture(self.store, iface or None)
                src.start()
            except Exception as e:  # PermissionError, Npcap missing, bad iface, ...
                self.error = _friendly(e)
                self.active = {"mode": mode, "iface": iface, "subnets": subnets}
                raise RuntimeError(self.error) from e
            self.source, self.error = src, None
            self.active = {"mode": mode, "iface": iface, "subnets": subnets}

    def stop(self) -> None:
        if self.source is not None:
            try:
                self.source.stop()
            except Exception:
                pass
            self.source = None

    def meta(self) -> dict:
        mode = self.active.get("mode", "live")
        if self.error:
            label = "OFFLINE"
        else:
            label = "DEMO / SIMULATION" if mode == "demo" else "LIVE CAPTURE"
        return {"mode": label, "iface": self.active.get("iface") or "default", "error": self.error}


def _friendly(e: Exception) -> str:
    msg = str(e) or e.__class__.__name__
    low = msg.lower()
    if isinstance(e, PermissionError) or "permission" in low or "operation not permitted" in low:
        return "Capture needs Administrator/root rights. Restart NETWATCH as Administrator, or use DEMO mode."
    if "winpcap" in low or "npcap" in low or "libpcap" in low:
        return "Npcap/libpcap is not installed (https://npcap.com). Install it, or use DEMO mode."
    if "no such device" in low or "interface" in low and "not found" in low:
        return f"Network interface not found: {msg}"
    return f"Capture failed: {msg}"
