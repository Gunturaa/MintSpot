"""Standalone MintSpot backend client calling mintspot-engine via pkexec."""

from __future__ import annotations

import json
import os
import re
import secrets
import string
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from .i18n import tr

ENGINE_BIN = str(Path(__file__).resolve().parent.parent / "mintspot-engine")

BAND_KEYS: List[str] = ["a", "bg"]
METHOD_KEYS: List[str] = ["p2p", "auto", "nmcli"]
DNS_KEYS: List[str] = ["cloudflare", "adguard", "google"]
IDLE_MINUTES: List[int] = [0, 15, 30, 60]
LIMIT_VALUES: List[int] = [0, 5, 10, 25]

BANDS: List[Tuple[str, str]] = [
    ("a", "5 GHz (iPhone / Fast)"),
    ("bg", "2.4 GHz (Legacy)"),
]

METHODS: List[Tuple[str, str, str]] = [
    ("p2p", "Wi-Fi Direct (5 GHz Bridge)", "Broadcasts 5 GHz while laptop stays on 2.4 GHz Wi-Fi"),
    ("auto", "Automatic", "Uses Wi-Fi Direct when supported, else NetworkManager"),
    ("nmcli", "NetworkManager", "Standard NetworkManager hotspot"),
]

DNS_OPTIONS: List[Tuple[str, str]] = [
    ("cloudflare", "Cloudflare (1.1.1.1 · Fast)"),
    ("adguard", "AdGuard DNS (Ad-Block for iPhone)"),
    ("google", "Google DNS (8.8.8.8)"),
]

IDLE_OPTIONS: List[Tuple[int, str]] = [
    (0, "Never"),
    (15, "After 15 minutes"),
    (30, "After 30 minutes"),
    (60, "After 60 minutes"),
]

LIMIT_PRESETS: List[Tuple[int, str]] = [
    (0, "Unlimited"),
    (5, "5 Mbps"),
    (10, "10 Mbps"),
    (25, "25 Mbps"),
]

CHANNELS = {
    "a": ["36", "40", "44", "48", "149", "153", "157", "161", "165"],
    "bg": [str(n) for n in range(1, 14)],
}


def band_options() -> List[Tuple[str, str]]:
    return [
        ("a", tr("band_5ghz")),
        ("bg", tr("band_24ghz")),
    ]


def method_options() -> List[Tuple[str, str]]:
    return [
        ("p2p", tr("method_p2p")),
        ("auto", tr("method_auto")),
        ("nmcli", tr("method_nmcli")),
    ]


def dns_options() -> List[Tuple[str, str]]:
    return [
        ("cloudflare", tr("dns_cloudflare")),
        ("adguard", tr("dns_adguard")),
        ("google", tr("dns_google")),
    ]


def idle_options() -> List[Tuple[int, str]]:
    return [
        (0, tr("idle_never")),
        (15, tr("idle_minutes", mins=15)),
        (30, tr("idle_minutes", mins=30)),
        (60, tr("idle_minutes", mins=60)),
    ]


def limit_presets() -> List[Tuple[int, str]]:
    return [
        (0, tr("limit_unlimited")),
        (5, tr("limit_mbps", mbps=5)),
        (10, tr("limit_mbps", mbps=10)),
        (25, tr("limit_mbps", mbps=25)),
    ]


def channel_options(band: str) -> List[Tuple[str, str]]:
    return [("auto", tr("channel_auto"))] + [
        (ch, tr("channel_num", ch=ch)) for ch in CHANNELS.get(band, CHANNELS["a"])
    ]


def band_label(band: Optional[str]) -> str:
    if band == "a":
        return "5 GHz"
    if band == "bg":
        return "2.4 GHz"
    return band or tr("unknown")


def format_bytes(num_bytes: Optional[int]) -> str:
    if not num_bytes:
        return "0 B"
    val = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if val < 1024 or unit == "GB":
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.1f} GB"


def format_speed(bytes_per_sec: float) -> str:
    if bytes_per_sec <= 10:
        return "0 KB/s"
    kbps = bytes_per_sec / 1024.0
    if kbps >= 1024.0:
        return f"{kbps / 1024.0:.1f} MB/s"
    return f"{kbps:.0f} KB/s"


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def escape_wifi_field(value: str) -> str:
    for ch in ("\\", ";", ",", ":", '"'):
        value = value.replace(ch, "\\" + ch)
    return value


def wifi_qr_payload(ssid: str, password: str, hidden: bool = False) -> str:
    if not ssid or not password:
        return ""
    tail = "H:true;" if hidden else ""
    return f"WIFI:T:WPA;S:{escape_wifi_field(ssid)};P:{escape_wifi_field(password)};{tail};"


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def first_error(text: str) -> str:
    for line in strip_ansi(text).splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:220]
    return tr("err_operation_failed")


def pkexec_failure(returncode: int, stderr: str) -> Optional[str]:
    low = stderr.lower()
    if "no authentication agent" in low:
        return tr("err_no_polkit_agent")
    if returncode == 126:
        return tr("err_auth_cancelled")
    if returncode == 127 and ("not authorized" in low or "authorization" in low or not stderr.strip()):
        return tr("err_not_authorized")
    return None


@dataclass
class Result:
    ok: bool
    message: str
    data: dict = field(default_factory=dict)


def _run(argv: List[str], stdin: Optional[str] = None, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "NO_COLOR": "1"},
    )


class MintSpotBackend:
    def __init__(self, binary: str = ENGINE_BIN) -> None:
        self.binary = binary

    def available(self) -> bool:
        return os.path.isfile(self.binary) and os.access(self.binary, os.X_OK)

    def _json(self, *args: str) -> dict:
        try:
            proc = _run([self.binary, *args], timeout=30)
            return json.loads(proc.stdout) if proc.returncode == 0 else {}
        except (OSError, subprocess.SubprocessError, ValueError):
            return {}

    def status(self) -> dict:
        return self._json("status")

    def detect(self) -> dict:
        return self._json("detect")

    def privileged(self, *args: str, stdin: Optional[str] = None, success: Optional[str] = None) -> Result:
        try:
            proc = _run(["pkexec", self.binary, *args], stdin=stdin)
        except FileNotFoundError:
            return Result(False, tr("err_pkexec_missing"))
        except subprocess.TimeoutExpired:
            return Result(False, tr("err_timeout"))
        if proc.returncode == 0:
            msg = tr("msg_done") if success is None else success
            return Result(True, msg, {"stdout": proc.stdout})
        if not proc.stdout:
            reason = pkexec_failure(proc.returncode, proc.stderr)
            if reason:
                return Result(False, reason)
        return Result(False, first_error(proc.stderr or proc.stdout))

    def start(self, method: Optional[str] = None) -> Result:
        args = ["start"]
        if method:
            args += ["--method", method]
        return self.privileged(*args, success=tr("msg_hotspot_on"))

    def stop(self) -> Result:
        return self.privileged("stop", success=tr("msg_hotspot_off"))

    def enable_iphone_5ghz_bridge(self) -> Result:
        return self.privileged(
            "config",
            "--set",
            "method=p2p",
            "--set",
            "band=a",
            "--set",
            "channel=auto",
            success=tr("msg_bridge_enabled"),
        )

    def disable_iphone_5ghz_bridge(self) -> Result:
        return self.privileged(
            "config",
            "--set",
            "method=auto",
            success=tr("msg_bridge_disabled"),
        )

    def secrets(self) -> Result:
        result = self.privileged("secrets", success="")
        if result.ok:
            try:
                result.data = json.loads(result.data["stdout"])
            except (KeyError, ValueError):
                return Result(False, tr("err_parse_creds"))
        return result

    def save_config(
        self,
        ssid: str,
        password: str,
        band: str,
        method: str,
        channel: str,
        hidden: bool = False,
        dns_mode: str = "cloudflare",
        idle_off_minutes: int = 0,
    ) -> Result:
        args = [
            "config",
            "--set",
            f"ssid={ssid}",
            "--set",
            f"band={band}",
            "--set",
            f"method={method}",
            "--set",
            f"channel={channel}",
            "--set",
            f"hidden={'yes' if hidden else 'no'}",
            "--set",
            f"dns_mode={dns_mode}",
            "--set",
            f"idle_off_minutes={idle_off_minutes}",
        ]
        if password:
            args.append("--password-stdin")
        return self.privileged(
            *args,
            stdin=(password + "\n") if password else None,
            success=tr("msg_settings_saved"),
        )

    def set_autostart(self, enabled: bool) -> Result:
        if enabled:
            return self.privileged("enable", success=tr("msg_autostart_on"))
        return self.privileged("disable", success=tr("msg_autostart_off"))

    def block_device(self, mac: str, block: bool) -> Result:
        verb = "block" if block else "unblock"
        msg = tr("msg_device_paused") if block else tr("msg_device_resumed")
        return self.privileged(verb, mac, success=msg)

    def limit_device(self, mac: str, mbps: int) -> Result:
        msg = tr("msg_limit_removed") if mbps == 0 else tr("msg_limit_set", mbps=mbps)
        return self.privileged("limit", mac, str(mbps), success=msg)

    def rename_device(self, mac: str, name: str) -> Result:
        return self.privileged("rename", mac, name, success=tr("msg_renamed"))
