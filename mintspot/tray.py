"""Native Linux Mint (Cinnamon/xapp-sn-watcher) StatusNotifierItem tray indicator.

Uses Gio.DBus directly inside the GTK4 main loop (zero extra dependencies) with
a crisp white macOS-style Personal Hotspot icon and right-click DBusMenu.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from gi.repository import Gio, GLib

from .i18n import tr

SNI_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="u" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
"""

DBUSMENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="Status" type="s" access="read"/>
    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg name="id" type="i" direction="in"/>
      <arg name="name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent" type="i"/>
    </signal>
  </interface>
</node>
"""

# Menu item IDs
ITEM_STATUS = 1
ITEM_SEP1 = 2
ITEM_TOGGLE = 3
ITEM_OPEN = 4
ITEM_SEP2 = 5
ITEM_QUIT = 6


class MintSpotTray:
    def __init__(
        self,
        on_activate: Callable[[], None],
        on_toggle_hotspot: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_activate = on_activate
        self._on_toggle = on_toggle_hotspot
        self._on_quit = on_quit

        self._bus: Optional[Gio.DBusConnection] = None
        self._sni_reg_id: int = 0
        self._menu_reg_id: int = 0
        self._bus_name: str = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self._name_owner_id: int = 0

        self._is_on: bool = False
        self._ssid: str = ""
        self._band: str = "5 GHz"
        self._clients_count: int = 0
        self._status_text: str = tr("tray_off_short")
        self._tooltip_body: str = tr("tray_click_open")
        self._revision: int = 1
        self.active: bool = False

        self._start()

    def _start(self) -> None:
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            return

        sni_info = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
        menu_info = Gio.DBusNodeInfo.new_for_xml(DBUSMENU_XML)

        try:
            self._sni_reg_id = self._bus.register_object(
                SNI_PATH,
                sni_info.interfaces[0],
                self._sni_method,
                self._sni_get_prop,
                None,
            )
            self._menu_reg_id = self._bus.register_object(
                MENU_PATH,
                menu_info.interfaces[0],
                self._menu_method,
                self._menu_get_prop,
                None,
            )
        except GLib.Error:
            return

        self._name_owner_id = Gio.bus_own_name_on_connection(
            self._bus,
            self._bus_name,
            Gio.BusNameOwnerFlags.NONE,
            self._on_name_acquired,
            None,
        )

    def _on_name_acquired(self, conn: Gio.DBusConnection, name: str) -> None:
        for watcher in ("org.kde.StatusNotifierWatcher", "org.freedesktop.StatusNotifierWatcher"):
            try:
                conn.call_sync(
                    watcher,
                    "/StatusNotifierWatcher",
                    watcher,
                    "RegisterStatusNotifierItem",
                    GLib.Variant("(s)", (name,)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
                self.active = True
                return
            except GLib.Error:
                continue

    def update(self, is_on: bool, ssid: str = "", band: str = "5 GHz", clients_count: int = 0) -> None:
        self._is_on = is_on
        self._ssid = ssid
        self._band = band
        self._clients_count = clients_count
        if is_on:
            dev = (
                tr("tray_device_singular", count=clients_count)
                if clients_count == 1
                else tr("tray_device_plural", count=clients_count)
            )
            self._status_text = tr("tray_live_status", ssid=ssid or "MintSpot", band=band, devices=dev)
            self._tooltip_body = tr("tray_live_tooltip", band=band, devices=dev)
        else:
            self._status_text = tr("tray_off_status")
            self._tooltip_body = tr("tray_off_tooltip")

        self._revision += 1
        if self._bus is None:
            return
        try:
            self._bus.emit_signal(None, SNI_PATH, "org.kde.StatusNotifierItem", "NewIcon", None)
            self._bus.emit_signal(None, SNI_PATH, "org.kde.StatusNotifierItem", "NewToolTip", None)
            self._bus.emit_signal(
                None,
                MENU_PATH,
                "com.canonical.dbusmenu",
                "LayoutUpdated",
                GLib.Variant("(ui)", (self._revision, 0)),
            )
        except GLib.Error:
            pass

    def refresh_language(self) -> None:
        self.update(self._is_on, self._ssid, self._band, self._clients_count)

    def close(self) -> None:
        if self._bus is not None:
            if self._sni_reg_id:
                self._bus.unregister_object(self._sni_reg_id)
                self._sni_reg_id = 0
            if self._menu_reg_id:
                self._bus.unregister_object(self._menu_reg_id)
                self._menu_reg_id = 0
        if self._name_owner_id:
            Gio.bus_unown_name(self._name_owner_id)
            self._name_owner_id = 0
        self.active = False

    # ── StatusNotifierItem handlers ───────────────────────────────────────────

    def _sni_get_prop(self, _conn, _sender, _path, _iface, prop_name: str):
        icon_name = "mintspot-tray-on" if self._is_on else "mintspot-tray-off"
        props = {
            "Category": GLib.Variant("s", "SystemServices"),
            "Id": GLib.Variant("s", "mintspot"),
            "Title": GLib.Variant("s", "MintSpot"),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("u", 0),
            "IconThemePath": GLib.Variant("s", str(ASSETS_DIR)),
            "IconName": GLib.Variant("s", icon_name),
            "ToolTip": GLib.Variant(
                "(sa(iiay)ss)",
                (icon_name, [], "MintSpot", self._tooltip_body),
            ),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_PATH),
        }
        return props.get(prop_name)

    def _sni_method(self, _conn, _sender, _path, _iface, method_name: str, _params, invocation):
        if method_name in ("Activate", "SecondaryActivate"):
            GLib.idle_add(self._on_activate)
        invocation.return_value(None)

    # ── DBusMenu handlers ─────────────────────────────────────────────────────

    def _menu_items(self) -> list:
        toggle_label = tr("tray_turn_off") if self._is_on else tr("tray_turn_on")
        return [
            (ITEM_STATUS, {"label": GLib.Variant("s", self._status_text), "enabled": GLib.Variant("b", False)}, []),
            (ITEM_SEP1, {"type": GLib.Variant("s", "separator")}, []),
            (ITEM_TOGGLE, {"label": GLib.Variant("s", toggle_label), "enabled": GLib.Variant("b", True)}, []),
            (ITEM_OPEN, {"label": GLib.Variant("s", tr("tray_open")), "enabled": GLib.Variant("b", True)}, []),
            (ITEM_SEP2, {"type": GLib.Variant("s", "separator")}, []),
            (ITEM_QUIT, {"label": GLib.Variant("s", tr("tray_quit")), "enabled": GLib.Variant("b", True)}, []),
        ]

    def _menu_get_prop(self, _conn, _sender, _path, _iface, prop_name: str):
        if prop_name == "Version":
            return GLib.Variant("u", 3)
        if prop_name == "Status":
            return GLib.Variant("s", "normal")
        return None

    def _menu_method(self, _conn, _sender, _path, _iface, method_name: str, params, invocation):
        if method_name == "GetLayout":
            children = [GLib.Variant("(ia{sv}av)", item) for item in self._menu_items()]
            root = (0, {"children-display": GLib.Variant("s", "submenu")}, children)
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self._revision, root)))
        elif method_name == "GetGroupProperties":
            ids = set(params.unpack()[0])
            out = []
            for item_id, props, _ in self._menu_items():
                if not ids or item_id in ids:
                    out.append((item_id, props))
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (out,)))
        elif method_name == "GetProperty":
            item_id, prop = params.unpack()
            val = GLib.Variant("s", "")
            for iid, props, _ in self._menu_items():
                if iid == item_id and prop in props:
                    val = props[prop]
                    break
            invocation.return_value(GLib.Variant("(v)", (val,)))
        elif method_name == "Event":
            item_id, event_id, _data, _ts = params.unpack()
            if event_id == "clicked":
                if item_id == ITEM_TOGGLE:
                    GLib.idle_add(self._on_toggle)
                elif item_id == ITEM_OPEN:
                    GLib.idle_add(self._on_activate)
                elif item_id == ITEM_QUIT:
                    GLib.idle_add(self._on_quit)
            invocation.return_value(None)
        elif method_name == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        else:
            invocation.return_value(None)
