"""Persistent settings (~/.netwatch/config.json) and network interface discovery."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("NETWATCH_HOME") or Path.home() / ".netwatch")
CONFIG_FILE = CONFIG_DIR / "config.json"
PBKDF2_ROUNDS = 240_000
DEFAULT_USER = "admin"
DEFAULT_PASS = "admin123"

DEFAULTS = {
    "mode": "live",          # "live" | "demo"
    "iface": "",             # "" = system default interface
    "subnets": [],           # [] = auto-detect from the interface
    "user": "admin",
    "pass_salt": "",
    "pass_hash": "",
    "default_password": False,
}


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()


class Config:
    def __init__(self):
        self.data = dict(DEFAULTS)
        try:
            self.data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        if not self.has_password:  # first run: default operator admin / admin123
            self.set_password(DEFAULT_USER, DEFAULT_PASS, default=True)

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        os.replace(tmp, CONFIG_FILE)

    def __getitem__(self, k):
        return self.data[k]

    # ---- credentials ------------------------------------------------------
    @property
    def has_password(self) -> bool:
        return bool(self.data["pass_hash"])

    def set_password(self, user: str, password: str, default: bool = False) -> None:
        salt = secrets.token_hex(16)
        self.data.update(user=user, pass_salt=salt, pass_hash=_hash(password, salt),
                         default_password=default)
        self.save()

    def check(self, user: str, password: str) -> bool:
        if not self.has_password:
            return False
        ok_user = hmac.compare_digest(user.encode(), self.data["user"].encode())
        ok_pass = hmac.compare_digest(_hash(password, self.data["pass_salt"]), self.data["pass_hash"])
        return ok_user and ok_pass


def validate_subnets(items: list[str]) -> list[str]:
    out = []
    for s in items:
        s = str(s).strip()
        if not s:
            continue
        net = ipaddress.ip_network(s, strict=False)  # raises ValueError
        if net.version != 4:
            raise ValueError(f"{s}: only IPv4 subnets are supported")
        if str(net) not in out:
            out.append(str(net))
    return out


def list_interfaces() -> dict:
    """Interfaces with their IP and directly-connected subnets. Needs scapy (+Npcap on Windows)."""
    try:
        from scapy.all import conf
    except Exception as e:  # scapy missing or Npcap not installed
        return {"interfaces": [], "default": "", "error": f"Cannot list interfaces: {e}"}

    subnets: dict[str, list[str]] = {}
    for net, mask, gw, iface, addr, _metric in conf.route.routes:
        name = getattr(iface, "name", iface)
        if gw != "0.0.0.0" or not mask:
            continue
        prefix = bin(mask).count("1")
        if not 8 <= prefix <= 30:
            continue
        n = ipaddress.ip_network((net, prefix), strict=False)
        if n.is_loopback or n.is_multicast or n.is_link_local:
            continue
        subnets.setdefault(name, [])
        if str(n) not in subnets[name]:
            subnets[name].append(str(n))

    out = []
    for i in conf.ifaces.values():
        ip = getattr(i, "ip", "") or ""
        if ip.startswith("127.") or i.name in ("lo", "Loopback Pseudo-Interface 1"):
            continue
        nets = subnets.get(i.name, [])
        if not nets and ip and not ip.startswith("169.254."):
            nets = [str(ipaddress.ip_network(f"{ip}/24", strict=False))]
        out.append({"name": i.name, "description": getattr(i, "description", "") or "",
                    "ip": ip, "mac": getattr(i, "mac", "") or "", "subnets": nets})
    out.sort(key=lambda x: (not x["ip"], x["name"].lower()))
    default = getattr(conf.iface, "name", str(conf.iface or ""))
    return {"interfaces": out, "default": default, "error": None}
