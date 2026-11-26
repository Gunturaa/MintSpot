"""Standalone Linux Wi-Fi hardware & interface discovery using iw and sysfs."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class WifiInterface:
    name: str
    phy: str
    mac: str = ""
    iftype: str = "managed"
    connected_ssid: Optional[str] = None
    channel: Optional[int] = None
    freq: Optional[int] = None
    state: str = "DOWN"


@dataclass
class HardwareCapability:
    interface: str
    phy: str
    driver: str = "unknown"
    chipset: str = "Wi-Fi Adapter"
    supports_ap: bool = False
    ap_sta: bool = False
    same_channel_required: bool = True
    p2p_go_own_channel: bool = False
    supports_5ghz_ap: bool = False
    ap_frequencies_24: List[Tuple[int, int]] = field(default_factory=list)  # (channel, freq_mhz)
    ap_frequencies_5: List[Tuple[int, int]] = field(default_factory=list)   # (channel, freq_mhz)


def _run_out(argv: List[str]) -> str:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return proc.stdout if proc.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _read_operstate(ifname: str) -> str:
    p = Path(f"/sys/class/net/{ifname}/operstate")
    try:
        return p.read_text(encoding="utf-8").strip().upper()
    except OSError:
        return "UNKNOWN"


def parse_iw_dev(text: str) -> List[WifiInterface]:
    interfaces: List[WifiInterface] = []
    current_phy = ""
    cur: Optional[WifiInterface] = None

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("phy#"):
            if cur is not None:
                interfaces.append(cur)
                cur = None
            current_phy = line.replace("#", "")
            continue
        if line.startswith("Unnamed/non-netdev interface"):
            if cur is not None:
                interfaces.append(cur)
                cur = None
            continue
        if line.startswith("Interface "):
            if cur is not None:
                interfaces.append(cur)
            name = line.split(None, 1)[1].strip()
            cur = WifiInterface(name=name, phy=current_phy, state=_read_operstate(name))
            continue
        if cur is None:
            continue
        if line.startswith("addr "):
            cur.mac = line.split(None, 1)[1].strip()
        elif line.startswith("type "):
            cur.iftype = line.split(None, 1)[1].strip()
        elif line.startswith("ssid "):
            cur.connected_ssid = line.split(None, 1)[1].strip()
        elif line.startswith("channel "):
            m = re.match(r"channel\s+(\d+)\s+\((\d+)\s+MHz\)", line)
            if m:
                cur.channel = int(m.group(1))
                cur.freq = int(m.group(2))

    if cur is not None:
        interfaces.append(cur)
    return interfaces


def list_interfaces() -> List[WifiInterface]:
    return parse_iw_dev(_run_out(["iw", "dev"]))


def client_interfaces() -> List[WifiInterface]:
    return [i for i in list_interfaces() if i.iftype == "managed"]


def select_primary_interface(wanted: Optional[str] = None) -> Optional[WifiInterface]:
    ifaces = client_interfaces()
    if not ifaces:
        return None
    if wanted and wanted != "auto":
        for iface in ifaces:
            if iface.name == wanted:
                return iface
    return sorted(ifaces, key=lambda i: (i.connected_ssid is None, i.state != "UP", i.name))[0]


def _driver_and_chipset(ifname: str) -> Tuple[str, str]:
    driver = "unknown"
    chipset = "Wi-Fi Adapter"
    drv_link = Path(f"/sys/class/net/{ifname}/device/driver")
    try:
        if drv_link.exists():
            driver = drv_link.resolve().name
    except OSError:
        pass

    uevent = Path(f"/sys/class/net/{ifname}/device/uevent")
    pci_slot = None
    try:
        for line in uevent.read_text(encoding="utf-8").splitlines():
            if line.startswith("PCI_SLOT_NAME="):
                pci_slot = line.split("=", 1)[1].strip()
    except OSError:
        pass

    if pci_slot:
        lspci = _run_out(["lspci", "-s", pci_slot]).strip()
        if ": " in lspci:
            chipset = lspci.split(": ", 1)[1].strip()
    elif driver != "unknown":
        chipset = f"{driver} Wi-Fi"
    return driver, chipset


def probe_capability(iface: WifiInterface) -> HardwareCapability:
    driver, chipset = _driver_and_chipset(iface.name)
    cap = HardwareCapability(
        interface=iface.name,
        phy=iface.phy,
        driver=driver,
        chipset=chipset,
    )
    info = _run_out(["iw", "phy", iface.phy, "info"])
    if not info:
        return cap

    in_modes = False
    in_combos = False
    combos: List[str] = []
    for raw in info.splitlines():
        line = raw.strip()
        if line.startswith("Supported interface modes:"):
            in_modes, in_combos = True, False
            continue
        if line.startswith("valid interface combinations:"):
            in_modes, in_combos = False, True
            continue
        if line.endswith(":") and not line.startswith("*"):
            in_modes = False
            in_combos = False
            continue

        if in_modes and line.startswith("* "):
            mode = line[2:].strip()
            if mode == "AP":
                cap.supports_ap = True

        if in_combos:
            if line.startswith("* "):
                combos.append(line[2:].strip())
            elif combos and line:
                combos[-1] = combos[-1] + " " + line

        # Parse usable AP frequencies (exclude disabled, no IR, radar detection)
        freq_match = re.match(r"\*\s+(\d+(?:\.\d+)?)\s+MHz\s+\[(\d+)\](.*)", line)
        if freq_match:
            freq = int(float(freq_match.group(1)))
            ch = int(freq_match.group(2))
            flags = freq_match.group(3).lower()
            if "disabled" in flags or "no ir" in flags or "radar detection" in flags:
                continue
            if 2412 <= freq <= 2484:
                cap.ap_frequencies_24.append((ch, freq))
            elif 5170 <= freq <= 5835:
                cap.ap_frequencies_5.append((ch, freq))

    for combo in combos:
        has_managed = "managed" in combo
        has_ap = bool(re.search(r"\bAP\b", combo))
        has_p2p_go = "P2P-GO" in combo
        ch_match = re.search(r"#channels\s*<=\s*(\d+)", combo)
        max_ch = int(ch_match.group(1)) if ch_match else 1
        if has_managed and has_ap:
            cap.ap_sta = True
            if max_ch >= 2:
                cap.same_channel_required = False
        if has_managed and has_p2p_go and max_ch >= 2:
            cap.p2p_go_own_channel = True

    cap.supports_5ghz_ap = bool(cap.ap_frequencies_5)
    return cap


def pick_channel(cap: HardwareCapability, band: str, wanted: str = "auto") -> Tuple[int, int]:
    """Return (channel_number, freq_mhz) for the requested band."""
    pool = cap.ap_frequencies_5 if band == "a" else cap.ap_frequencies_24
    # Fallback safe non-DFS frequencies if iw phy info did not report any
    if not pool:
        if band == "a":
            pool = [(36, 5180), (40, 5200), (44, 5220), (48, 5240), (149, 5745), (153, 5765)]
        else:
            pool = [(6, 2437), (1, 2412), (11, 2462)]

    if wanted and wanted != "auto":
        try:
            w = int(wanted)
            for ch, freq in pool:
                if ch == w:
                    return ch, freq
        except ValueError:
            pass

    # Prefer clean non-DFS 5 GHz channels (36, 40, 44, 48, 149) for iOS compatibility
    if band == "a":
        for pref in (36, 40, 44, 48, 149, 153, 157, 161):
            for ch, freq in pool:
                if ch == pref:
                    return ch, freq
    else:
        for pref in (6, 1, 11):
            for ch, freq in pool:
                if ch == pref:
                    return ch, freq

    return pool[0]


def detect_report() -> Dict[str, object]:
    ifaces = client_interfaces()
    primary = select_primary_interface()
    cap = probe_capability(primary) if primary else None
    return {
        "interfaces": [asdict(i) for i in ifaces],
        "capability": asdict(cap) if cap else {},
    }
