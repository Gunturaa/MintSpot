"""Pure-Python wpa_supplicant P2P-GO controller (Unix socket + System D-Bus via jeepney)."""

from __future__ import annotations

import itertools
import os
import socket
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import RUN_DIR, WPA_CTRL_DIR

_counter = itertools.count()

BUS_NAME = "fi.w1.wpa_supplicant1"
ROOT_PATH = "/fi/w1/wpa_supplicant1"
P2P_IFACE = "fi.w1.wpa_supplicant1.Interface.P2PDevice"


class WpaError(RuntimeError):
    """Raised when wpa_supplicant rejects a P2P-GO operation."""


def _is_raw_psk(password: str) -> bool:
    return len(password) == 64 and all(c in "0123456789abcdefABCDEF" for c in password)


def _format_psk(password: str) -> str:
    return password.lower() if _is_raw_psk(password) else f'"{password}"'


def _ssid_matches(value: str, ssid: str) -> bool:
    v = value.strip()
    return v == f'"{ssid}"' or v.lower() == ssid.encode("utf-8").hex()


def p2p_socket_path(base_iface: str) -> Path:
    return WPA_CTRL_DIR / f"p2p-dev-{base_iface}"


class BaseP2PController(ABC):
    kind: str = ""

    def __init__(self, base_iface: str) -> None:
        self.base_iface = base_iface

    @abstractmethod
    def add_group_network(self, ssid: str, password: str, hidden: bool = False) -> str:
        """Create a persistent P2P-GO network block and return its handle."""

    @abstractmethod
    def start_group(self, handle: str, freq_mhz: int) -> None:
        """Start the P2P-GO group on the requested frequency."""

    @abstractmethod
    def remove_group(self, group_iface: str) -> bool:
        """Tear down the active P2P-GO interface."""

    @abstractmethod
    def forget_all(self, handle: Optional[str], ssid: str) -> None:
        """Remove our persistent group block and any in-memory copies."""


# ── Backend 1: Unix Control Socket ────────────────────────────────────────────


class SocketP2PController(BaseP2PController):
    kind = "socket"

    def __init__(self, base_iface: str) -> None:
        super().__init__(base_iface)
        self.sock_path = p2p_socket_path(base_iface)

    def available(self) -> bool:
        try:
            return self.sock_path.is_socket()
        except OSError:
            return False

    def request(self, command: str, timeout: float = 10.0) -> str:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        local = RUN_DIR / f"wpa-ctrl-{os.getpid()}-{next(_counter)}"
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            local.unlink(missing_ok=True)
            sock.bind(str(local))
            sock.settimeout(timeout)
            sock.connect(str(self.sock_path))
            sock.send(command.encode("utf-8"))
            while True:
                reply = sock.recv(4096).decode("utf-8", errors="replace")
                if not reply.startswith("<"):
                    break
        except OSError as exc:
            verb = command.split(" ", 1)[0]
            raise WpaError(f"wpa_supplicant socket failed on {verb}: {exc}") from exc
        finally:
            sock.close()
            local.unlink(missing_ok=True)
        return reply.strip()

    def _expect_ok(self, command: str, what: str) -> None:
        reply = self.request(command)
        if reply != "OK":
            raise WpaError(f"wpa_supplicant refused {what} ({reply or 'empty reply'}).")

    def add_group_network(self, ssid: str, password: str, hidden: bool = False) -> str:
        net_id = self.request("ADD_NETWORK")
        if not net_id.isdigit():
            raise WpaError(f"Could not allocate P2P network block ({net_id or 'empty'}).")
        settings: List[Tuple[str, str]] = [
            ("ssid", ssid.encode("utf-8").hex()),
            ("psk", _format_psk(password)),
            ("key_mgmt", "WPA-PSK"),
            ("proto", "RSN"),
            ("pairwise", "CCMP"),
            ("mode", "3"),
            ("disabled", "2"),
        ]
        if hidden:
            settings.append(("ignore_broadcast_ssid", "1"))
        try:
            for key, val in settings:
                self._expect_ok(f"SET_NETWORK {net_id} {key} {val}", key)
        except WpaError:
            self.remove_network(net_id)
            raise
        return net_id

    def start_group(self, handle: str, freq_mhz: int) -> None:
        self._expect_ok(
            f"P2P_GROUP_ADD persistent={handle} freq={freq_mhz}",
            f"starting 5 GHz Wi-Fi Direct group on {freq_mhz} MHz",
        )

    def remove_group(self, group_iface: str) -> bool:
        try:
            return self.request(f"P2P_GROUP_REMOVE {group_iface}") == "OK"
        except WpaError:
            return False

    def remove_network(self, net_id: str) -> bool:
        try:
            return self.request(f"REMOVE_NETWORK {net_id}") == "OK"
        except WpaError:
            return False

    def forget_all(self, handle: Optional[str], ssid: str) -> None:
        if handle:
            self.remove_network(handle)
        try:
            listing = self.request("LIST_NETWORKS")
            for line in listing.splitlines()[1:]:
                fields = line.split("\t")
                if len(fields) >= 4 and fields[0].isdigit() and "[P2P-PERSISTENT]" in fields[3]:
                    if _ssid_matches(self.request(f"GET_NETWORK {fields[0]} ssid"), ssid):
                        self.remove_network(fields[0])
        except WpaError:
            pass


# ── Backend 2: System D-Bus via jeepney ───────────────────────────────────────


class DBusP2PController(BaseP2PController):
    kind = "dbus"

    def _call(self, obj_path: str, interface: str, method: str, sig: str = "", body: tuple = ()) -> tuple:
        try:
            from jeepney import DBusAddress, new_method_call
            from jeepney.io.blocking import open_dbus_connection
        except ImportError as exc:
            raise WpaError("python3-jeepney is required for D-Bus wpa_supplicant control.") from exc

        addr = DBusAddress(obj_path, bus_name=BUS_NAME, interface=interface)
        msg = new_method_call(addr, method, sig, body) if sig else new_method_call(addr, method)
        try:
            conn = open_dbus_connection(bus="SYSTEM")
            try:
                reply = conn.send_and_get_reply(msg, timeout=15.0)
            finally:
                conn.close()
        except Exception as exc:
            raise WpaError(f"D-Bus call {method} failed: {exc}") from exc

        if reply.header.message_type.name == "error":
            detail = reply.body[0] if reply.body else reply.header.fields.get(4, "D-Bus error")
            raise WpaError(f"wpa_supplicant D-Bus refused {method}: {detail}")
        return reply.body

    def _get_interface_path(self, ifname: str) -> str:
        body = self._call(ROOT_PATH, BUS_NAME, "GetInterface", "s", (ifname,))
        return str(body[0])

    def _p2p_interface_path(self) -> str:
        # Try p2p-dev-<iface> first, then fall back to <iface>
        for candidate in (f"p2p-dev-{self.base_iface}", self.base_iface):
            try:
                return self._get_interface_path(candidate)
            except WpaError:
                continue
        raise WpaError(f"wpa_supplicant D-Bus has no interface for {self.base_iface}.")

    def available(self) -> bool:
        try:
            self._p2p_interface_path()
            return True
        except WpaError:
            return False

    def add_group_network(self, ssid: str, password: str, hidden: bool = False) -> str:
        iface_path = self._p2p_interface_path()
        props: Dict[str, Tuple[str, object]] = {
            "ssid": ("ay", ssid.encode("utf-8")),
            "psk": ("ay", bytes.fromhex(password)) if _is_raw_psk(password) else ("s", password),
            "key_mgmt": ("s", "WPA-PSK"),
            "proto": ("s", "RSN"),
            "pairwise": ("s", "CCMP"),
            "mode": ("u", 3),
        }
        if hidden:
            props["ignore_broadcast_ssid"] = ("u", 1)
        body = self._call(iface_path, P2P_IFACE, "AddPersistentGroup", "a{sv}", (props,))
        return str(body[0])

    def start_group(self, handle: str, freq_mhz: int) -> None:
        iface_path = self._p2p_interface_path()
        args: Dict[str, Tuple[str, object]] = {
            "persistent": ("b", True),
            "persistent_group_object": ("o", handle),
            "frequency": ("i", int(freq_mhz)),
        }
        self._call(iface_path, P2P_IFACE, "GroupAdd", "a{sv}", (args,))

    def remove_group(self, group_iface: str) -> bool:
        try:
            group_path = self._get_interface_path(group_iface)
            self._call(group_path, P2P_IFACE, "Disconnect")
            return True
        except WpaError:
            return False

    def forget_all(self, handle: Optional[str], ssid: str) -> None:
        try:
            iface_path = self._p2p_interface_path()
        except WpaError:
            return
        if handle:
            try:
                self._call(iface_path, P2P_IFACE, "RemovePersistentGroup", "o", (handle,))
            except WpaError:
                pass
        # Clean up any duplicate persistent groups with matching SSID
        try:
            body = self._call(
                iface_path,
                "org.freedesktop.DBus.Properties",
                "Get",
                "ss",
                (P2P_IFACE, "PersistentGroups"),
            )
            groups = body[0][1] if body and isinstance(body[0], tuple) else []
            for gpath in groups:
                try:
                    pbody = self._call(
                        str(gpath),
                        "org.freedesktop.DBus.Properties",
                        "Get",
                        "ss",
                        ("fi.w1.wpa_supplicant1.PersistentGroup", "Properties"),
                    )
                    gprops = pbody[0][1] if pbody and isinstance(pbody[0], tuple) else {}
                    raw_ssid = gprops.get("ssid")
                    if raw_ssid is not None:
                        val = raw_ssid[1] if isinstance(raw_ssid, tuple) else raw_ssid
                        if isinstance(val, (bytes, bytearray)) and val == ssid.encode("utf-8"):
                            self._call(iface_path, P2P_IFACE, "RemovePersistentGroup", "o", (str(gpath),))
                        elif isinstance(val, str) and _ssid_matches(val, ssid):
                            self._call(iface_path, P2P_IFACE, "RemovePersistentGroup", "o", (str(gpath),))
                except WpaError:
                    continue
        except WpaError:
            pass


def connect_wpa(base_iface: str, preferred_kind: Optional[str] = None) -> Optional[BaseP2PController]:
    """Connect to wpa_supplicant via control socket first, then System D-Bus."""
    candidates: List[BaseP2PController] = [
        SocketP2PController(base_iface),
        DBusP2PController(base_iface),
    ]
    if preferred_kind == "dbus":
        candidates.reverse()
    for ctrl in candidates:
        if ctrl.available():
            return ctrl
    return None
