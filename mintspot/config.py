"""Standalone configuration & runtime state store for MintSpot."""

from __future__ import annotations

import json
import os
import secrets
import string
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_DIR = Path("/etc/mintspot")
CONFIG_FILE = CONFIG_DIR / "config.json"

RUN_DIR = Path("/run/mintspot")
STATE_FILE = RUN_DIR / "state.json"
PUBLIC_CONFIG_FILE = RUN_DIR / "public.json"
DNSMASQ_CONF = RUN_DIR / "dnsmasq.conf"
DNSMASQ_PID = RUN_DIR / "dnsmasq.pid"
DNSMASQ_LEASES = RUN_DIR / "dnsmasq.leases"
WPA_CTRL_DIR = Path("/run/wpa_supplicant")
SYSTEMD_SERVICE = Path("/etc/systemd/system/mintspot.service")

DNS_PRESETS = {
    "cloudflare": ("1.1.1.1", "1.0.0.1"),
    "adguard": ("94.140.14.14", "94.140.15.15"),
    "google": ("8.8.8.8", "8.8.4.4"),
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "ssid": "MintSpot-5G",
    "password": "",
    "band": "a",
    "method": "p2p",
    "channel": "auto",
    "hidden": False,
    "interface": "auto",
    "dns_mode": "cloudflare",
    "idle_off_minutes": 0,
    "device_names": {},
    "blocked_macs": [],
    "device_limits": {},  # mac -> mbps (int)
}


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _atomic_write_json(path: Path, data: dict, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.chmod(str(tmp), mode)
    os.replace(str(tmp), str(path))


def load_config(include_password: bool = True) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    cfg["device_names"] = {}
    cfg["blocked_macs"] = []
    cfg["device_limits"] = {}
    source = CONFIG_FILE if include_password else (CONFIG_FILE if os.access(CONFIG_FILE, os.R_OK) else PUBLIC_CONFIG_FILE)
    if source.is_file():
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg.update(raw)
        except (OSError, ValueError):
            pass
    if not include_password:
        cfg.pop("password", None)
    return cfg


def save_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    _atomic_write_json(CONFIG_FILE, merged, mode=0o600)
    public = {k: v for k, v in merged.items() if k != "password"}
    _atomic_write_json(PUBLIC_CONFIG_FILE, public, mode=0o644)
    return merged


def ensure_password(cfg: Dict[str, Any]) -> Optional[str]:
    if cfg.get("password"):
        return None
    pw = generate_password(12)
    cfg["password"] = pw
    save_config(cfg)
    return pw


def load_state() -> Optional[Dict[str, Any]]:
    if not STATE_FILE.is_file():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save_state(state: Dict[str, Any]) -> None:
    _atomic_write_json(STATE_FILE, state, mode=0o644)


def clear_state() -> None:
    STATE_FILE.unlink(missing_ok=True)
