"""Standalone MintSpot Engine — 5 GHz P2P-GO Bridge, DNS Ad-Block, NAT, Block & Limit."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .config import (
    DNS_PRESETS,
    DNSMASQ_CONF,
    DNSMASQ_LEASES,
    DNSMASQ_PID,
    RUN_DIR,
    SYSTEMD_SERVICE,
    clear_state,
    ensure_password,
    load_config,
    load_state,
    save_config,
    save_state,
)
from .hardware import (
    client_interfaces,
    detect_report,
    list_interfaces,
    pick_channel,
    probe_capability,
    select_primary_interface,
)
from .wpa_p2p import WpaError, connect_wpa

NFT_TABLE = "mintspot"
NM_CONN_NAME = "MintSpot-AP"
ENGINE_EXEC = Path(__file__).resolve().parent.parent / "mintspot-engine"
MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


class EngineError(RuntimeError):
    """Actionable error surfaced to the MintSpot UI / CLI."""


def _run(argv: List[str], check: bool = False, stdin_text: Optional[str] = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(argv, input=stdin_text, capture_output=True, text=True, timeout=30)
    if check and proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or f"Command failed: {' '.join(argv)}").strip()
        raise EngineError(msg)
    return proc


def _require_root() -> None:
    if os.geteuid() != 0:
        raise EngineError("This operation requires root privileges (pkexec / sudo).")


def _normalize_mac(mac: str) -> str:
    cleaned = mac.strip().lower()
    if not MAC_RE.match(cleaned):
        raise EngineError(f"Invalid MAC address: {mac}")
    return cleaned


def _pid_alive(pidfile: Path) -> Optional[int]:
    if not pidfile.is_file():
        return None
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
        return pid
    except PermissionError:
        return pid
    except OSError:
        return None


def _stop_pidfile(pidfile: Path) -> None:
    pid = _pid_alive(pidfile)
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            else:
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    pidfile.unlink(missing_ok=True)


def _pick_subnet() -> ipaddress.IPv4Network:
    used = []
    out = _run(["ip", "-4", "-o", "addr", "show"]).stdout
    for m in re.finditer(r"inet\s+(\d+\.\d+\.\d+\.\d+/\d+)", out):
        try:
            used.append(ipaddress.ip_interface(m.group(1)).network)
        except ValueError:
            pass
    for third in (99, 100, 101, 102, 110, 120):
        cand = ipaddress.ip_network(f"10.42.{third}.0/24")
        if not any(cand.overlaps(u) for u in used):
            return cand
    return ipaddress.ip_network("10.42.199.0/24")


def _apply_nat(
    ap_iface: str,
    subnet_cidr: str,
    blocked_macs: Optional[List[str]] = None,
    device_limits: Optional[Dict[str, int]] = None,
) -> str:
    _run(["sysctl", "-w", "net.ipv4.ip_forward=1"])
    blocked = [m.lower() for m in (blocked_macs or []) if MAC_RE.match(m.lower())]
    limits = {
        m.lower(): int(mbps)
        for m, mbps in (device_limits or {}).items()
        if MAC_RE.match(m.lower()) and int(mbps) > 0
    }

    if shutil.which("nft"):
        _run(["nft", "delete", "table", "inet", NFT_TABLE])
        extra_rules: List[str] = []
        for mac in blocked:
            extra_rules.append(f'        iifname "{ap_iface}" ether saddr {mac} drop')
            extra_rules.append(f'        oifname "{ap_iface}" ether daddr {mac} drop')
        for mac, mbps in limits.items():
            kbytes = max(125, mbps * 125)  # 1 Mbps == 125 kbytes/second
            extra_rules.append(
                f'        iifname "{ap_iface}" ether saddr {mac} limit rate over {kbytes} kbytes/second drop'
            )
            extra_rules.append(
                f'        oifname "{ap_iface}" ether daddr {mac} limit rate over {kbytes} kbytes/second drop'
            )
        extra_block = ("\n".join(extra_rules) + "\n") if extra_rules else ""
        ruleset = f"""
table inet {NFT_TABLE} {{
    chain forward {{
        type filter hook forward priority -10; policy accept;
{extra_block}        iifname "{ap_iface}" accept
        oifname "{ap_iface}" ct state established,related accept
    }}
    chain postrouting {{
        type nat hook postrouting priority srcnat; policy accept;
        ip saddr {subnet_cidr} oifname != "{ap_iface}" masquerade
    }}
}}
"""
        _run(["nft", "-f", "-"], check=True, stdin_text=ruleset)
        return "nftables"

    _run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", subnet_cidr, "!", "-o", ap_iface, "-j", "MASQUERADE"], check=True)
    _run(["iptables", "-I", "FORWARD", "-i", ap_iface, "-j", "ACCEPT"], check=True)
    _run(["iptables", "-I", "FORWARD", "-o", ap_iface, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"], check=True)
    return "iptables"


def _revert_nat(ap_iface: str, subnet_cidr: str, fw_kind: str) -> None:
    if fw_kind == "nftables" and shutil.which("nft"):
        _run(["nft", "delete", "table", "inet", NFT_TABLE])
    elif fw_kind == "iptables" and shutil.which("iptables"):
        _run(["iptables", "-t", "nat", "-D", "POSTROUTING", "-s", subnet_cidr, "!", "-o", ap_iface, "-j", "MASQUERADE"])
        _run(["iptables", "-D", "FORWARD", "-i", ap_iface, "-j", "ACCEPT"])
        _run(["iptables", "-D", "FORWARD", "-o", ap_iface, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"])


def _start_dnsmasq(ap_iface: str, net: ipaddress.IPv4Network, dns_mode: str = "cloudflare") -> str:
    hosts = list(net.hosts())
    gateway = str(hosts[0])
    dhcp_start = str(hosts[9])
    dhcp_end = str(hosts[199])
    dns1, dns2 = DNS_PRESETS.get(dns_mode, DNS_PRESETS["cloudflare"])

    _run(["ip", "addr", "flush", "dev", ap_iface])
    _run(["ip", "addr", "add", f"{gateway}/{net.prefixlen}", "dev", ap_iface], check=True)
    _run(["ip", "link", "set", ap_iface, "up"], check=True)

    DNSMASQ_LEASES.unlink(missing_ok=True)
    conf = "\n".join([
        f"interface={ap_iface}",
        "bind-dynamic",
        f"listen-address={gateway}",
        "except-interface=lo",
        f"dhcp-range={dhcp_start},{dhcp_end},12h",
        f"dhcp-option=option:router,{gateway}",
        f"dhcp-option=option:dns-server,{gateway}",
        "no-resolv",
        f"server={dns1}",
        f"server={dns2}",
        f"dhcp-leasefile={DNSMASQ_LEASES}",
        "no-hosts",
        "",
    ])
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    DNSMASQ_CONF.write_text(conf, encoding="utf-8")
    _stop_pidfile(DNSMASQ_PID)
    _run(["dnsmasq", "--test", f"--conf-file={DNSMASQ_CONF}"], check=True)
    proc = subprocess.Popen(
        ["dnsmasq", f"--conf-file={DNSMASQ_CONF}", f"--pid-file={DNSMASQ_PID}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        rc = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise EngineError("dnsmasq took too long to start.")
    if rc != 0:
        err = (proc.stderr.read() if proc.stderr else "").strip()
        raise EngineError(err or f"dnsmasq exited with code {rc}.")
    if proc.stderr:
        proc.stderr.close()
    return gateway


def _p2p_group_ifaces(phy: str) -> Dict[str, Optional[str]]:
    return {
        i.name: i.connected_ssid
        for i in list_interfaces()
        if i.iftype == "P2P-GO" and i.phy == phy
    }


def _wait_p2p_group(phy: str, before: set, timeout: float = 15.0) -> Optional[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for name, ssid in _p2p_group_ifaces(phy).items():
            if name not in before and ssid:
                return name
        time.sleep(0.4)
    return None


def _is_alive(state: Dict[str, object]) -> bool:
    ap = str(state.get("ap_interface") or "")
    if not ap or not Path(f"/sys/class/net/{ap}").exists():
        return False
    if state.get("method") == "p2p":
        return _pid_alive(DNSMASQ_PID) is not None
    return True


def _parse_station_dump(ap_iface: str) -> Dict[str, dict]:
    out = _run(["iw", "dev", ap_iface, "station", "dump"]).stdout
    stats: Dict[str, dict] = {}
    cur_mac: Optional[str] = None
    for raw in out.splitlines():
        line = raw.strip()
        if line.startswith("Station "):
            cur_mac = line.split()[1].lower()
            stats[cur_mac] = {}
            continue
        if not cur_mac:
            continue
        if line.startswith("signal:"):
            m = re.search(r"(-?\d+)\s+dBm", line)
            if m:
                stats[cur_mac]["signal_dbm"] = int(m.group(1))
        elif line.startswith("rx bytes:"):
            stats[cur_mac]["rx_bytes"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("tx bytes:"):
            stats[cur_mac]["tx_bytes"] = int(line.split(":", 1)[1].strip())
    return stats


def _list_clients(state: Optional[Dict[str, object]], cfg: Dict[str, object]) -> List[dict]:
    if not state or not _is_alive(state):
        return []
    ap = str(state.get("ap_interface") or "")
    station_stats = _parse_station_dump(ap)
    leases: Dict[str, dict] = {}
    if DNSMASQ_LEASES.is_file():
        try:
            for line in DNSMASQ_LEASES.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    mac = parts[1].lower()
                    ip = parts[2]
                    host = "" if parts[3] == "*" else parts[3]
                    leases[mac] = {"mac": mac, "ip": ip, "hostname": host}
        except OSError:
            pass

    names = cfg.get("device_names") or {}
    blocked = set(m.lower() for m in (cfg.get("blocked_macs") or []))
    limits = cfg.get("device_limits") or {}

    all_macs = sorted(set(leases.keys()) | set(station_stats.keys()))
    clients = []
    for mac in all_macs:
        entry = {
            "mac": mac,
            "ip": leases.get(mac, {}).get("ip", ""),
            "hostname": names.get(mac) or leases.get(mac, {}).get("hostname", ""),
            "blocked": mac in blocked,
            "limit_mbps": int(limits.get(mac, 0) or 0),
        }
        entry.update(station_stats.get(mac, {}))
        clients.append(entry)
    return clients


def _autostart_enabled() -> bool:
    return _run(["systemctl", "is-enabled", "mintspot.service"]).returncode == 0


def _reapply_live_firewall(cfg: Dict[str, object]) -> None:
    st = load_state()
    if st and _is_alive(st) and st.get("method") == "p2p" and st.get("subnet"):
        _apply_nat(
            str(st["ap_interface"]),
            str(st["subnet"]),
            blocked_macs=cfg.get("blocked_macs") or [],
            device_limits=cfg.get("device_limits") or {},
        )


def cmd_status() -> dict:
    st = load_state()
    hotspot = st if (st and _is_alive(st)) else None
    stale = bool(st and hotspot is None)
    cfg = load_config(include_password=False)
    return {
        "hotspot": hotspot,
        "stale": stale,
        "config": cfg,
        "interfaces": [asdict(i) for i in client_interfaces()],
        "clients": _list_clients(hotspot, cfg),
        "autostart": _autostart_enabled(),
    }


def cmd_start(method_override: Optional[str] = None) -> dict:
    _require_root()
    existing = load_state()
    if existing:
        if _is_alive(existing):
            raise EngineError(f"MintSpot is already running on {existing['ap_interface']} ({existing['ssid']}).")
        cmd_stop()

    cfg = load_config(include_password=True)
    ensure_password(cfg)
    ssid = str(cfg["ssid"])
    password = str(cfg["password"])
    band = str(cfg.get("band") or "a")
    method = method_override or str(cfg.get("method") or "p2p")
    wanted_ch = str(cfg.get("channel") or "auto")
    hidden = bool(cfg.get("hidden"))
    dns_mode = str(cfg.get("dns_mode") or "cloudflare")

    base = select_primary_interface(cfg.get("interface"))
    if base is None:
        raise EngineError("No Wi-Fi interface found on this computer.")
    cap = probe_capability(base)

    if method == "auto":
        method = "p2p" if cap.p2p_go_own_channel else "nmcli"

    rollbacks: List[Callable[[], None]] = []
    try:
        if method == "p2p":
            if not cap.p2p_go_own_channel:
                raise EngineError("Your Wi-Fi adapter does not support Wi-Fi Direct on a separate channel.")
            if not shutil.which("dnsmasq"):
                raise EngineError("dnsmasq is not installed. Run: sudo apt install dnsmasq-base")

            wpa = connect_wpa(base.name)
            if wpa is None:
                raise EngineError(f"Could not connect to wpa_supplicant P2P for {base.name} (socket or D-Bus).")

            for stale_go in list(_p2p_group_ifaces(base.phy).keys()):
                wpa.remove_group(stale_go)
                _run(["iw", "dev", stale_go, "del"])

            ch_num, freq_mhz = pick_channel(cap, band, wanted_ch)
            before = set(_p2p_group_ifaces(base.phy).keys())
            net_id = wpa.add_group_network(ssid, password, hidden)
            rollbacks.append(lambda: wpa.forget_all(net_id, ssid))

            wpa.start_group(net_id, freq_mhz)

            def _remove_p2p() -> None:
                for name in set(_p2p_group_ifaces(base.phy).keys()) - before:
                    wpa.remove_group(name)
                    _run(["iw", "dev", name, "del"])

            rollbacks.append(_remove_p2p)
            ap_iface = _wait_p2p_group(base.phy, before)
            if not ap_iface:
                raise EngineError(f"Wi-Fi Direct group did not come up on channel {ch_num} ({freq_mhz} MHz).")

            _run(["nmcli", "device", "set", ap_iface, "managed", "no"])
            net = _pick_subnet()
            gateway = _start_dnsmasq(ap_iface, net, dns_mode=dns_mode)
            rollbacks.append(lambda: _stop_pidfile(DNSMASQ_PID))

            fw_kind = _apply_nat(
                ap_iface,
                str(net),
                blocked_macs=cfg.get("blocked_macs") or [],
                device_limits=cfg.get("device_limits") or {},
            )
            rollbacks.append(lambda: _revert_nat(ap_iface, str(net), fw_kind))

            notes = []
            if base.connected_ssid and base.freq and ((base.freq < 5000 and band == "a") or (base.freq >= 5000 and band == "bg")):
                uplink_b = "2.4 GHz" if base.freq < 5000 else "5 GHz"
                out_b = "5 GHz" if band == "a" else "2.4 GHz"
                dns_note = " · AdGuard Ad-Block DNS" if dns_mode == "adguard" else ""
                notes.append(
                    f"Bridging {base.connected_ssid} ({uplink_b}) -> {ssid} ({out_b}, Ch {ch_num}){dns_note}."
                )

            state = {
                "method": "p2p",
                "base_interface": base.name,
                "ap_interface": ap_iface,
                "ssid": ssid,
                "band": band,
                "channel": ch_num,
                "freq": freq_mhz,
                "dns_mode": dns_mode,
                "subnet": str(net),
                "gateway": gateway,
                "firewall": fw_kind,
                "p2p_backend": wpa.kind,
                "p2p_network": net_id,
                "sta_ssid_at_start": base.connected_ssid,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "notes": notes,
            }
            save_state(state)
            return state

        elif method == "nmcli":
            _run(["nmcli", "connection", "delete", NM_CONN_NAME])
            nm_band = "a" if band == "a" else "bg"
            args = [
                "nmcli", "device", "wifi", "hotspot",
                "ifname", base.name,
                "con-name", NM_CONN_NAME,
                "ssid", ssid,
                "band", nm_band,
                "password", password,
            ]
            _run(args, check=True)
            rollbacks.append(lambda: _run(["nmcli", "connection", "delete", NM_CONN_NAME]))
            state = {
                "method": "nmcli",
                "base_interface": base.name,
                "ap_interface": base.name,
                "ssid": ssid,
                "band": band,
                "channel": base.channel or (36 if band == "a" else 6),
                "subnet": "10.42.0.0/24",
                "gateway": "10.42.0.1",
                "firewall": "nmcli",
                "sta_ssid_at_start": base.connected_ssid,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "notes": ["Running via NetworkManager hotspot."],
            }
            save_state(state)
            return state

        else:
            raise EngineError(f"Unsupported hotspot method: {method}")
    except Exception:
        for undo in reversed(rollbacks):
            try:
                undo()
            except Exception:
                pass
        raise


def cmd_stop() -> None:
    _require_root()
    st = load_state()
    if not st:
        _stop_pidfile(DNSMASQ_PID)
        if shutil.which("nft"):
            _run(["nft", "delete", "table", "inet", NFT_TABLE])
        return

    method = st.get("method")
    ap = str(st.get("ap_interface") or "")
    base = str(st.get("base_interface") or "")

    if method == "p2p":
        if st.get("subnet") and st.get("firewall"):
            _revert_nat(ap, str(st["subnet"]), str(st["firewall"]))
        _stop_pidfile(DNSMASQ_PID)
        DNSMASQ_CONF.unlink(missing_ok=True)
        DNSMASQ_LEASES.unlink(missing_ok=True)
        if base:
            wpa = connect_wpa(base, preferred_kind=st.get("p2p_backend"))
            if wpa is not None:
                if ap:
                    wpa.remove_group(ap)
                wpa.forget_all(st.get("p2p_network"), str(st.get("ssid") or ""))
        if ap and Path(f"/sys/class/net/{ap}").exists():
            _run(["iw", "dev", ap, "del"])
    elif method == "nmcli":
        _run(["nmcli", "connection", "down", NM_CONN_NAME])
        _run(["nmcli", "connection", "delete", NM_CONN_NAME])

    clear_state()


def cmd_config(sets: List[str], password_stdin: bool) -> dict:
    _require_root()
    cfg = load_config(include_password=True)
    dns_changed = False
    for item in sets:
        if "=" not in item:
            raise EngineError(f"Invalid --set argument: {item}")
        key, val = item.split("=", 1)
        if key == "ssid":
            if not val.strip() or len(val.encode("utf-8")) > 32:
                raise EngineError("SSID must be 1 to 32 bytes.")
            cfg["ssid"] = val.strip()
        elif key == "band":
            if val not in ("a", "bg"):
                raise EngineError("Band must be 'a' (5 GHz) or 'bg' (2.4 GHz).")
            cfg["band"] = val
        elif key == "method":
            if val not in ("p2p", "auto", "nmcli"):
                raise EngineError("Method must be 'p2p', 'auto', or 'nmcli'.")
            cfg["method"] = val
        elif key == "channel":
            cfg["channel"] = val
        elif key == "hidden":
            cfg["hidden"] = val.lower() in ("yes", "true", "1")
        elif key == "interface":
            cfg["interface"] = val
        elif key == "dns_mode":
            if val not in DNS_PRESETS:
                raise EngineError(f"DNS mode must be one of: {', '.join(DNS_PRESETS)}.")
            if cfg.get("dns_mode") != val:
                dns_changed = True
            cfg["dns_mode"] = val
        elif key == "idle_off_minutes":
            try:
                mins = int(val)
                if mins < 0 or mins > 240:
                    raise ValueError
                cfg["idle_off_minutes"] = mins
            except ValueError:
                raise EngineError("idle_off_minutes must be an integer between 0 and 240.")
        else:
            raise EngineError(f"Unknown config key: {key}")

    if password_stdin:
        pw = sys.stdin.readline().rstrip("\r\n")
        if len(pw) < 8 or len(pw) > 63:
            raise EngineError("WPA2 password must be 8 to 63 characters.")
        cfg["password"] = pw

    saved = save_config(cfg)
    if dns_changed:
        st = load_state()
        if st and _is_alive(st) and st.get("method") == "p2p" and st.get("subnet"):
            _start_dnsmasq(str(st["ap_interface"]), ipaddress.ip_network(str(st["subnet"])), dns_mode=saved["dns_mode"])
            st["dns_mode"] = saved["dns_mode"]
            save_state(st)
    return saved


def cmd_block(mac: str, block: bool) -> dict:
    _require_root()
    norm = _normalize_mac(mac)
    cfg = load_config(include_password=True)
    blocked = set(m.lower() for m in (cfg.get("blocked_macs") or []))
    if block:
        blocked.add(norm)
    else:
        blocked.discard(norm)
    cfg["blocked_macs"] = sorted(blocked)
    saved = save_config(cfg)
    _reapply_live_firewall(saved)
    return {"mac": norm, "blocked": block}


def cmd_limit(mac: str, mbps: int) -> dict:
    _require_root()
    norm = _normalize_mac(mac)
    if mbps < 0 or mbps > 500:
        raise EngineError("Speed limit must be 0 (unlimited) to 500 Mbps.")
    cfg = load_config(include_password=True)
    limits = dict(cfg.get("device_limits") or {})
    if mbps == 0:
        limits.pop(norm, None)
    else:
        limits[norm] = mbps
    cfg["device_limits"] = limits
    saved = save_config(cfg)
    _reapply_live_firewall(saved)
    return {"mac": norm, "limit_mbps": mbps}


def cmd_rename(mac: str, name: str) -> dict:
    _require_root()
    norm = _normalize_mac(mac)
    cfg = load_config(include_password=True)
    names = dict(cfg.get("device_names") or {})
    cleaned = name.strip()[:32]
    if cleaned:
        names[norm] = cleaned
    else:
        names.pop(norm, None)
    cfg["device_names"] = names
    save_config(cfg)
    return {"mac": norm, "name": cleaned}


def cmd_enable_autostart(enabled: bool) -> None:
    _require_root()
    if enabled:
        unit = f"""[Unit]
Description=MintSpot 5 GHz Wi-Fi Direct Hotspot Bridge
After=network-online.target NetworkManager.service wpa_supplicant.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={ENGINE_EXEC} start
ExecStop={ENGINE_EXEC} stop

[Install]
WantedBy=multi-user.target
"""
        SYSTEMD_SERVICE.write_text(unit, encoding="utf-8")
        _run(["systemctl", "daemon-reload"], check=True)
        _run(["systemctl", "enable", "mintspot.service"], check=True)
    else:
        _run(["systemctl", "disable", "mintspot.service"])
        SYSTEMD_SERVICE.unlink(missing_ok=True)
        _run(["systemctl", "daemon-reload"])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="mintspot-engine", description="MintSpot standalone hotspot engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("detect")
    p_start = sub.add_parser("start")
    p_start.add_argument("--method", choices=["p2p", "auto", "nmcli"], default=None)
    sub.add_parser("stop")

    p_cfg = sub.add_parser("config")
    p_cfg.add_argument("--set", dest="sets", action="append", default=[])
    p_cfg.add_argument("--password-stdin", action="store_true")

    sub.add_parser("secrets")
    sub.add_parser("enable")
    sub.add_parser("disable")

    p_block = sub.add_parser("block")
    p_block.add_argument("mac")
    p_unblock = sub.add_parser("unblock")
    p_unblock.add_argument("mac")

    p_limit = sub.add_parser("limit")
    p_limit.add_argument("mac")
    p_limit.add_argument("mbps", type=int)

    p_rename = sub.add_parser("rename")
    p_rename.add_argument("mac")
    p_rename.add_argument("name")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "status":
            print(json.dumps(cmd_status()))
        elif args.cmd == "detect":
            print(json.dumps(detect_report()))
        elif args.cmd == "start":
            print(json.dumps(cmd_start(method_override=args.method)))
        elif args.cmd == "stop":
            cmd_stop()
            print(json.dumps({"ok": True}))
        elif args.cmd == "config":
            saved = cmd_config(args.sets, args.password_stdin)
            saved.pop("password", None)
            print(json.dumps(saved))
        elif args.cmd == "secrets":
            _require_root()
            cfg = load_config(include_password=True)
            ensure_password(cfg)
            print(json.dumps(cfg))
        elif args.cmd == "enable":
            cmd_enable_autostart(True)
            print(json.dumps({"autostart": True}))
        elif args.cmd == "disable":
            cmd_enable_autostart(False)
            print(json.dumps({"autostart": False}))
        elif args.cmd == "block":
            print(json.dumps(cmd_block(args.mac, True)))
        elif args.cmd == "unblock":
            print(json.dumps(cmd_block(args.mac, False)))
        elif args.cmd == "limit":
            print(json.dumps(cmd_limit(args.mac, args.mbps)))
        elif args.cmd == "rename":
            print(json.dumps(cmd_rename(args.mac, args.name)))
        return 0
    except (EngineError, WpaError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
