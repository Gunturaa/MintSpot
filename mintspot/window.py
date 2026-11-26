"""Main macOS / iOS-style application window for MintSpot."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

from gi.repository import Adw, Gdk, GLib, Gtk

from . import APP_NAME
from .backend import (
    BAND_KEYS,
    DNS_KEYS,
    IDLE_MINUTES,
    METHOD_KEYS,
    MintSpotBackend,
    Result,
    band_label,
    band_options,
    channel_options,
    dns_options,
    format_bytes,
    format_speed,
    generate_password,
    idle_options,
    limit_presets,
    method_options,
)
from .dev_preview import DevServer, UrlQrSheet, detect_dev_servers
from .graph import LiveTrafficGraph
from .i18n import SUPPORTED_LANGUAGES, get_language, set_language, tr
from .qr_dialog import ShareSheet
from .speedtest import SpeedTestResult, run_speedtest
from .style import install_css
from .tray import MintSpotTray

POLL_SECONDS = 5
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "mintspot.svg"
LIGHTNING_PATH = ASSETS_DIR / "lightning.svg"


def _clear_box(box: Gtk.Box) -> None:
    child = box.get_first_child()
    while child is not None:
        next_child = child.get_next_sibling()
        box.remove(child)
        child = next_child


def _copy_to_clipboard(widget: Gtk.Widget, text: str) -> None:
    display = widget.get_display()
    if display is not None:
        display.get_clipboard().set(text)


def _divider() -> Gtk.Box:
    return Gtk.Box(css_classes=["air-divider"])


def _section_label(text: str) -> Gtk.Label:
    return Gtk.Label(label=text.upper(), xalign=0, css_classes=["air-section-title"])


def _section_footer(text: str) -> Gtk.Label:
    return Gtk.Label(label=text, xalign=0, wrap=True, css_classes=["air-section-footer"])


def _replace_string_list(model: Gtk.StringList, items: List[str]) -> None:
    model.splice(0, model.get_n_items(), items)


class MintSpotWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            title=APP_NAME,
            default_width=476,
            default_height=740,
            **kwargs,
        )
        self.set_size_request(390, 560)
        install_css()
        self.add_css_class("air-window")

        self.backend = MintSpotBackend()
        self.data: dict = {}
        self.detect_data: dict = {}
        self.busy = False
        self._speedtesting = False
        self._speedtest_state = "idle"
        self._speedtest_error = ""
        self._syncing_ui = False
        self._dark_mode = False
        self._channel_choices: List[tuple] = channel_options("a")
        self._settings_dirty = False
        self._prev_traffic: Dict[str, Tuple[int, int, float]] = {}
        self._known_macs: Optional[Set[str]] = None
        self._expected_on: bool = False
        self._last_heal_attempt: float = 0.0
        self._dev_servers: List[DevServer] = []
        self._idle_since: Optional[float] = None
        self._quitting = False

        self._style_manager = Adw.StyleManager.get_default()
        self._apply_theme(self._style_manager.get_dark())

        self._build_layout()
        self._install_shortcuts()

        self.tray = MintSpotTray(
            on_activate=self._toggle_window_visibility,
            on_toggle_hotspot=self._tray_toggle_hotspot,
            on_quit=self._quit_app,
        )
        self.connect("close-request", self._on_close_request)

        GLib.idle_add(self.refresh)
        GLib.timeout_add_seconds(POLL_SECONDS, self._poll_tick)

    def _toggle_window_visibility(self) -> None:
        if self.get_visible() and self.is_active():
            self.set_visible(False)
        else:
            self.set_visible(True)
            self.present()

    def _tray_toggle_hotspot(self) -> None:
        if self.busy:
            return
        if self.data.get("hotspot"):
            self._expected_on = False
            self._run_privileged(self.backend.stop)
        else:
            self._expected_on = True
            self._run_privileged(self.backend.start)

    def _quit_app(self) -> None:
        self._quitting = True
        self.tray.close()
        app = self.get_application()
        if app is not None:
            app.quit()
        else:
            self.close()

    def _on_close_request(self, *_args) -> bool:
        if not self._quitting and self.tray.active:
            self.set_visible(False)
            return True
        self.tray.close()
        return False

    # ── Theme, Language & Shortcuts ───────────────────────────────────────────

    def _apply_theme(self, dark: bool) -> None:
        self._dark_mode = dark
        self._style_manager.set_color_scheme(
            Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.FORCE_LIGHT
        )
        if dark:
            self.add_css_class("air-dark")
        else:
            self.remove_css_class("air-dark")
        if hasattr(self, "theme_btn"):
            self.theme_btn.set_icon_name(
                "weather-clear-symbolic" if dark else "weather-clear-night-symbolic"
            )
            self.theme_btn.set_tooltip_text(
                tr("tooltip_switch_light") if dark else tr("tooltip_switch_dark")
            )
        if hasattr(self, "traffic_graph"):
            self.traffic_graph.set_dark(dark)

    def _notify_desktop(self, title: str, body: str) -> None:
        if shutil.which("notify-send"):
            try:
                subprocess.Popen(
                    ["notify-send", "-a", APP_NAME, "-i", "mintspot", title, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                pass

    def _toggle_theme(self, *_args) -> None:
        self._apply_theme(not self._dark_mode)

    def _toggle_language(self, *_args) -> None:
        next_lang = "id" if get_language() == "en" else "en"
        self._set_language(next_lang, announce=True)

    def _on_language_dropdown_changed(self, *_args) -> None:
        if self._syncing_ui:
            return
        idx = self.lang_dropdown.get_selected()
        if 0 <= idx < len(SUPPORTED_LANGUAGES):
            code = SUPPORTED_LANGUAGES[idx][0]
            if code != get_language():
                self._set_language(code, announce=True)

    def _set_language(self, lang: str, announce: bool = False) -> None:
        code = set_language(lang, persist=True)
        self._retranslate_ui(code)
        self.traffic_graph.queue_draw()
        self._apply_state(self.data, self.detect_data, quiet=True, dev_servers=self._dev_servers)
        self.tray.refresh_language()
        if announce:
            self.toast(tr("toast_lang_switched"))

    def _retranslate_ui(self, lang_code: str) -> None:
        # Header & navigation
        self._tab_buttons["hotspot"].set_label(tr("tab_hotspot"))
        self._tab_buttons["devices"].set_label(tr("tab_devices"))
        self._tab_buttons["settings"].set_label(tr("tab_settings"))
        self.refresh_btn.set_tooltip_text(tr("tooltip_refresh"))
        self.lang_btn.set_label(tr("lang_badge"))
        self.lang_btn.set_tooltip_text(tr("tooltip_switch_lang"))
        self.theme_btn.set_tooltip_text(
            tr("tooltip_switch_light") if self._dark_mode else tr("tooltip_switch_dark")
        )
        self.footer_label.set_label(tr("footer_credit"))

        # Hotspot page
        self.master_title.set_label(tr("master_title"))
        self.sec_bridge_lbl.set_label(tr("section_bridge").upper())
        self.uplink_kicker_lbl.set_label(tr("uplink_kicker"))
        self.out_kicker_lbl.set_label(tr("output_kicker"))
        self.iphone_bridge_title_lbl.set_label(tr("iphone_bridge_title"))
        self.iphone_bridge_desc_lbl.set_label(tr("iphone_bridge_desc"))

        self.sec_network_lbl.set_label(tr("section_network").upper())
        self.ssid_row_lbl.set_label(tr("network_name"))
        self.copy_ssid_btn.set_tooltip_text(tr("tooltip_copy_ssid"))
        self.qr_title_lbl.set_label(tr("wifi_pw_qr"))
        self.qr_subtitle_lbl.set_label(tr("scan_iphone_camera"))
        self.share_btn.set_label(tr("show_qr"))
        self.ch_row_lbl.set_label(tr("band_channel"))
        self.dev_row_lbl.set_label(tr("connected_devices"))
        self.view_dev_btn.set_tooltip_text(tr("tooltip_open_devices"))
        self.iface_row_lbl.set_label(tr("interface"))

        self.sec_speed_lbl.set_label(tr("section_speedtest").upper())
        self.speed_title_lbl.set_label(tr("uplink_speedtest"))
        if not self._speedtesting:
            self.speed_btn.set_label(tr("run_test"))
            if self._speedtest_state == "done":
                self.speed_status.set_label(tr("speedtest_done"))
            elif self._speedtest_state == "error" and self._speedtest_error:
                self.speed_status.set_label(self._speedtest_error)
            else:
                self.speed_status.set_label(tr("speedtest_idle"))
        else:
            self.speed_btn.set_label(tr("testing"))
        self.ping_tile_lbl.set_label(tr("metric_ping"))
        self.dl_tile_lbl.set_label(tr("metric_download"))
        self.ul_tile_lbl.set_label(tr("metric_upload"))

        self.sec_dev_lbl.set_label(tr("section_dev_preview").upper())
        self.port_row_lbl.set_label(tr("port_label"))
        self.custom_port_entry.set_placeholder_text(tr("port_placeholder"))
        self.custom_qr_btn.set_label(tr("safari_qr"))

        # Devices page
        self.sec_throughput_lbl.set_label(tr("section_throughput").upper())

        # Settings page
        self.sec_settings_net_lbl.set_label(tr("section_network").upper())
        self.settings_name_lbl.set_label(tr("settings_name"))
        self.ssid_entry.set_placeholder_text(tr("ssid_placeholder"))
        self.settings_pw_lbl.set_label(tr("settings_password"))
        self.pw_entry.set_property("placeholder-text", tr("pw_placeholder"))
        self.gen_pw_btn.set_label(tr("btn_generate"))
        self.hidden_row_lbl.set_label(tr("hidden_network"))

        self.sec_radio_lbl.set_label(tr("section_radio_privacy").upper())
        self.band_row_lbl.set_label(tr("settings_band"))
        self.method_row_lbl.set_label(tr("settings_method"))
        self.channel_row_lbl.set_label(tr("settings_channel"))
        self.dns_row_lbl.set_label(tr("settings_dns"))
        self.idle_row_lbl.set_label(tr("settings_idle"))
        self.dns_footer_lbl.set_label(tr("dns_footer"))
        self.save_btn.set_label(tr("save_settings"))

        self.sec_sys_lbl.set_label(tr("section_system").upper())
        self.lang_row_lbl.set_label(tr("settings_language"))
        self.boot_row_lbl.set_label(tr("autostart_boot"))
        self.hw_row_lbl.set_label(tr("wifi_adapter"))

        # Update Settings dropdown string lists while preserving selections
        prev_sync = self._syncing_ui
        self._syncing_ui = True
        try:
            band_sel = self.band_dropdown.get_selected()
            method_sel = self.method_dropdown.get_selected()
            ch_sel = self.channel_dropdown.get_selected()
            dns_sel = self.dns_dropdown.get_selected()
            idle_sel = self.idle_dropdown.get_selected()

            band_val = BAND_KEYS[band_sel] if 0 <= band_sel < len(BAND_KEYS) else "a"
            selected_ch_val = (
                self._channel_choices[ch_sel][0]
                if 0 <= ch_sel < len(self._channel_choices)
                else "auto"
            )

            _replace_string_list(self.band_model, [label for _, label in band_options()])
            self.band_dropdown.set_selected(band_sel)

            _replace_string_list(self.method_model, [label for _, label in method_options()])
            self.method_dropdown.set_selected(method_sel)

            self._rebuild_channels(band_val, selected_ch_val)

            _replace_string_list(self.dns_model, [label for _, label in dns_options()])
            self.dns_dropdown.set_selected(dns_sel)

            _replace_string_list(self.idle_model, [label for _, label in idle_options()])
            self.idle_dropdown.set_selected(idle_sel)

            lang_idx = next((i for i, item in enumerate(SUPPORTED_LANGUAGES) if item[0] == lang_code), 0)
            self.lang_dropdown.set_selected(lang_idx)
        finally:
            self._syncing_ui = prev_sync

    def _install_shortcuts(self) -> None:
        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(ctrl)

    def _on_key_pressed(self, _ctrl, keyval: int, _keycode: int, state) -> bool:
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval == Gdk.KEY_1:
                self._switch_tab("hotspot")
                return True
            if keyval == Gdk.KEY_2:
                self._switch_tab("devices")
                return True
            if keyval == Gdk.KEY_3:
                self._switch_tab("settings")
                return True
            if keyval in (Gdk.KEY_r, Gdk.KEY_R):
                self.refresh()
                return True
            if keyval in (Gdk.KEY_q, Gdk.KEY_Q):
                self._quit_app()
                return True
        return False

    # ── Layout Construction ───────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.toast_overlay = Adw.ToastOverlay()
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header = Adw.HeaderBar()
        header.add_css_class("air-headerbar")

        seg_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2, css_classes=["air-segmented"])
        self._tab_buttons = {}
        for tab_id, key in (("hotspot", "tab_hotspot"), ("devices", "tab_devices"), ("settings", "tab_settings")):
            btn = Gtk.Button(label=tr(key))
            btn.connect("clicked", lambda _b, tid=tab_id: self._switch_tab(tid))
            seg_box.append(btn)
            self._tab_buttons[tab_id] = btn
        header.set_title_widget(seg_box)

        self.refresh_btn = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text=tr("tooltip_refresh"),
        )
        self.refresh_btn.connect("clicked", lambda *_: self.refresh())
        header.pack_start(self.refresh_btn)

        self.theme_btn = Gtk.Button(
            icon_name="weather-clear-symbolic" if self._dark_mode else "weather-clear-night-symbolic",
            tooltip_text=tr("tooltip_switch_light") if self._dark_mode else tr("tooltip_switch_dark"),
        )
        self.theme_btn.connect("clicked", self._toggle_theme)
        header.pack_end(self.theme_btn)

        self.lang_btn = Gtk.Button(
            label=tr("lang_badge"),
            tooltip_text=tr("tooltip_switch_lang"),
            css_classes=["air-btn-secondary", "air-lang-btn"],
        )
        self.lang_btn.connect("clicked", self._toggle_language)
        header.pack_end(self.lang_btn)

        root.append(header)

        self.stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=150,
            vexpand=True,
        )
        self.stack.add_named(self._build_hotspot_page(), "hotspot")
        self.stack.add_named(self._build_devices_page(), "devices")
        self.stack.add_named(self._build_settings_page(), "settings")
        root.append(self.stack)

        footer_wrap = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            hexpand=True,
            halign=Gtk.Align.FILL,
            css_classes=["air-footer"],
        )
        inner_footer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            hexpand=True,
            halign=Gtk.Align.CENTER,
        )
        if LIGHTNING_PATH.is_file():
            bolt = Gtk.Image.new_from_file(str(LIGHTNING_PATH))
            bolt.set_pixel_size(14)
            inner_footer.append(bolt)
        self.footer_label = Gtk.Label(label=tr("footer_credit"), css_classes=["air-footer-text"])
        inner_footer.append(self.footer_label)
        footer_wrap.append(inner_footer)
        root.append(footer_wrap)

        self.toast_overlay.set_child(root)
        self.set_content(self.toast_overlay)
        self._switch_tab("hotspot")

    def _switch_tab(self, tab_id: str) -> None:
        self.stack.set_visible_child_name(tab_id)
        for tid, btn in self._tab_buttons.items():
            if tid == tab_id:
                btn.add_css_class("active-seg")
            else:
                btn.remove_css_class("active-seg")

    def _scrolled_container(self) -> tuple[Gtk.ScrolledWindow, Gtk.Box]:
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        clamp = Adw.Clamp(maximum_size=520, tightening_threshold=420)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin_top=14,
            margin_bottom=20,
            margin_start=16,
            margin_end=16,
        )
        clamp.set_child(box)
        scroll.set_child(clamp)
        return scroll, box

    # ── Hotspot Page ──────────────────────────────────────────────────────────

    def _build_hotspot_page(self) -> Gtk.Widget:
        scroll, page = self._scrolled_container()

        # 1. Master Personal Hotspot Card
        master = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, css_classes=["air-card-padded"])
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self.master_icon_box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        if LOGO_PATH.is_file():
            self.master_icon = Gtk.Image.new_from_file(str(LOGO_PATH))
            self.master_icon.set_pixel_size(44)
        else:
            self.master_icon_box.add_css_class("air-icon-badge")
            self.master_icon = Gtk.Image(icon_name="network-wireless-hotspot-symbolic", pixel_size=22)
        self.master_icon_box.append(self.master_icon)

        title_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
        title_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.master_title = Gtk.Label(label=tr("master_title"), xalign=0, css_classes=["air-hero-title"])
        self.status_pill = Gtk.Label(label=tr("status_off"), css_classes=["air-pill", "air-pill-off"])
        title_line.append(self.master_title)
        title_line.append(self.status_pill)
        self.master_subtitle = Gtk.Label(
            label=tr("checking_hardware"),
            xalign=0,
            wrap=True,
            css_classes=["air-subtitle"],
        )
        title_col.append(title_line)
        title_col.append(self.master_subtitle)

        self.spinner = Gtk.Spinner(valign=Gtk.Align.CENTER)
        self.spinner.set_visible(False)

        self.power_switch = Gtk.Switch(valign=Gtk.Align.CENTER, css_classes=["air-switch"])
        self.power_switch.connect("state-set", self._on_power_switch)

        top_row.append(self.master_icon_box)
        top_row.append(title_col)
        top_row.append(self.spinner)
        top_row.append(self.power_switch)
        master.append(top_row)
        page.append(master)

        # 2. Signal Bridge Card (2.4 GHz -> 5 GHz iPhone Bridge)
        self.sec_bridge_lbl = _section_label(tr("section_bridge"))
        page.append(self.sec_bridge_lbl)
        bridge_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["air-card"])

        nodes_wrap = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=14,
            margin_bottom=14,
            margin_start=14,
            margin_end=14,
        )
        uplink_node = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, css_classes=["air-bridge-node"])
        self.uplink_kicker_lbl = Gtk.Label(label=tr("uplink_kicker"), xalign=0, css_classes=["air-bridge-kicker"])
        self.uplink_name = Gtk.Label(label=tr("not_connected"), xalign=0, ellipsize=3, css_classes=["air-bridge-name"])
        self.uplink_band = Gtk.Label(label="--", xalign=0, css_classes=["air-bridge-band"])
        uplink_node.append(self.uplink_kicker_lbl)
        uplink_node.append(self.uplink_name)
        uplink_node.append(self.uplink_band)

        arrow = Gtk.Image(icon_name="go-next-symbolic", pixel_size=18, valign=Gtk.Align.CENTER)
        arrow.add_css_class("air-subtitle")

        out_node = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, css_classes=["air-bridge-node"])
        self.out_kicker_lbl = Gtk.Label(label=tr("output_kicker"), xalign=0, css_classes=["air-bridge-kicker"])
        self.out_name = Gtk.Label(label="MintSpot-5G", xalign=0, ellipsize=3, css_classes=["air-bridge-name"])
        self.out_band = Gtk.Label(label="5 GHz · P2P", xalign=0, css_classes=["air-bridge-band"])
        out_node.append(self.out_kicker_lbl)
        out_node.append(self.out_name)
        out_node.append(self.out_band)

        nodes_wrap.append(uplink_node)
        nodes_wrap.append(arrow)
        nodes_wrap.append(out_node)
        bridge_card.append(nodes_wrap)
        bridge_card.append(_divider())

        iphone_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        iphone_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        self.iphone_bridge_title_lbl = Gtk.Label(
            label=tr("iphone_bridge_title"), xalign=0, css_classes=["air-row-title"]
        )
        self.iphone_bridge_desc_lbl = Gtk.Label(
            label=tr("iphone_bridge_desc"),
            xalign=0,
            wrap=True,
            css_classes=["air-subtitle"],
        )
        iphone_text.append(self.iphone_bridge_title_lbl)
        iphone_text.append(self.iphone_bridge_desc_lbl)
        self.iphone_bridge_switch = Gtk.Switch(valign=Gtk.Align.CENTER, css_classes=["air-switch"])
        self.iphone_bridge_switch.connect("state-set", self._on_iphone_bridge_toggled)
        iphone_row.append(iphone_text)
        iphone_row.append(self.iphone_bridge_switch)
        bridge_card.append(iphone_row)
        page.append(bridge_card)

        # 3. Network & Quick Join Card
        self.sec_network_lbl = _section_label(tr("section_network"))
        page.append(self.sec_network_lbl)
        net_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["air-card"])

        ssid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-row"])
        self.ssid_row_lbl = Gtk.Label(label=tr("network_name"), xalign=0, css_classes=["air-row-title"])
        ssid_row.append(self.ssid_row_lbl)
        self.ssid_val = Gtk.Label(label="--", xalign=1, hexpand=True, ellipsize=3, css_classes=["air-value"])
        self.copy_ssid_btn = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text=tr("tooltip_copy_ssid"),
            css_classes=["air-btn-secondary"],
        )
        self.copy_ssid_btn.connect("clicked", self._on_copy_ssid)
        ssid_row.append(self.ssid_val)
        ssid_row.append(self.copy_ssid_btn)
        net_card.append(ssid_row)
        net_card.append(_divider())

        qr_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-row"])
        qr_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        self.qr_title_lbl = Gtk.Label(label=tr("wifi_pw_qr"), xalign=0, css_classes=["air-row-title"])
        self.qr_subtitle_lbl = Gtk.Label(label=tr("scan_iphone_camera"), xalign=0, css_classes=["air-subtitle"])
        qr_text.append(self.qr_title_lbl)
        qr_text.append(self.qr_subtitle_lbl)
        self.share_btn = Gtk.Button(label=tr("show_qr"), css_classes=["air-btn-primary"])
        self.share_btn.connect("clicked", lambda *_: self._open_share_sheet())
        qr_row.append(qr_text)
        qr_row.append(self.share_btn)
        net_card.append(qr_row)
        net_card.append(_divider())

        ch_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-row"])
        self.ch_row_lbl = Gtk.Label(label=tr("band_channel"), xalign=0, css_classes=["air-row-title"])
        ch_row.append(self.ch_row_lbl)
        self.channel_val = Gtk.Label(label="--", xalign=1, hexpand=True, css_classes=["air-value"])
        ch_row.append(self.channel_val)
        net_card.append(ch_row)
        net_card.append(_divider())

        dev_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-row"])
        self.dev_row_lbl = Gtk.Label(label=tr("connected_devices"), xalign=0, css_classes=["air-row-title"])
        dev_row.append(self.dev_row_lbl)
        self.clients_count_val = Gtk.Label(label="0", xalign=1, hexpand=True, css_classes=["air-value"])
        self.view_dev_btn = Gtk.Button(
            icon_name="go-next-symbolic",
            tooltip_text=tr("tooltip_open_devices"),
            css_classes=["air-btn-secondary"],
        )
        self.view_dev_btn.connect("clicked", lambda *_: self._switch_tab("devices"))
        dev_row.append(self.clients_count_val)
        dev_row.append(self.view_dev_btn)
        net_card.append(dev_row)
        net_card.append(_divider())

        iface_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-row"])
        self.iface_row_lbl = Gtk.Label(label=tr("interface"), xalign=0, css_classes=["air-row-title"])
        iface_row.append(self.iface_row_lbl)
        self.iface_val = Gtk.Label(label="--", xalign=1, hexpand=True, ellipsize=3, css_classes=["air-mono"])
        iface_row.append(self.iface_val)
        net_card.append(iface_row)
        page.append(net_card)

        # 4. Built-in Speed Test Card
        self.sec_speed_lbl = _section_label(tr("section_speedtest"))
        page.append(self.sec_speed_lbl)
        speed_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, css_classes=["air-card-padded"])

        speed_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        speed_titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        self.speed_title_lbl = Gtk.Label(label=tr("uplink_speedtest"), xalign=0, css_classes=["air-row-title"])
        speed_titles.append(self.speed_title_lbl)
        self.speed_status = Gtk.Label(label=tr("speedtest_idle"), xalign=0, css_classes=["air-subtitle"])
        speed_titles.append(self.speed_status)
        self.speed_btn = Gtk.Button(label=tr("run_test"), css_classes=["air-btn-secondary"])
        self.speed_btn.connect("clicked", self._on_run_speedtest)
        speed_head.append(speed_titles)
        speed_head.append(self.speed_btn)
        speed_card.append(speed_head)

        metrics_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
        self.ping_tile_lbl, self.ping_val = self._metric_tile(metrics_row, tr("metric_ping"), "-- ms")
        self.dl_tile_lbl, self.dl_val = self._metric_tile(metrics_row, tr("metric_download"), "-- Mbps")
        self.ul_tile_lbl, self.ul_val = self._metric_tile(metrics_row, tr("metric_upload"), "-- Mbps")
        speed_card.append(metrics_row)
        page.append(speed_card)

        # 5. Local Dev Preview Card (Safari QR for localhost servers)
        self.sec_dev_lbl = _section_label(tr("section_dev_preview"))
        page.append(self.sec_dev_lbl)
        dev_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["air-card"])
        self.dev_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dev_card.append(self.dev_list_box)
        dev_card.append(_divider())

        custom_port_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, css_classes=["air-row"])
        self.port_row_lbl = Gtk.Label(label=tr("port_label"), xalign=0, css_classes=["air-row-title"])
        custom_port_row.append(self.port_row_lbl)
        self.custom_port_entry = Gtk.Entry(hexpand=True, placeholder_text=tr("port_placeholder"))
        self.custom_port_entry.connect("activate", self._on_custom_port_qr)
        self.custom_qr_btn = Gtk.Button(label=tr("safari_qr"), css_classes=["air-btn-secondary"])
        self.custom_qr_btn.connect("clicked", self._on_custom_port_qr)
        custom_port_row.append(self.custom_port_entry)
        custom_port_row.append(self.custom_qr_btn)
        dev_card.append(custom_port_row)
        page.append(dev_card)

        # 6. Contextual runtime note
        self.notice_label = Gtk.Label(
            label="",
            xalign=0,
            wrap=True,
            selectable=True,
            margin_top=14,
            css_classes=["air-notice"],
        )
        self.notice_label.set_visible(False)
        page.append(self.notice_label)

        return scroll

    def _metric_tile(self, parent: Gtk.Box, label: str, initial: str) -> Tuple[Gtk.Label, Gtk.Label]:
        tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["air-stat-tile"])
        lbl = Gtk.Label(label=label, xalign=0.5, css_classes=["air-stat-label"])
        val = Gtk.Label(label=initial, xalign=0.5, css_classes=["air-stat-value"])
        tile.append(lbl)
        tile.append(val)
        parent.append(tile)
        return lbl, val

    # ── Devices Page ──────────────────────────────────────────────────────────

    def _build_devices_page(self) -> Gtk.Widget:
        scroll, page = self._scrolled_container()

        # Live Speed Graph
        self.sec_throughput_lbl = _section_label(tr("section_throughput"))
        page.append(self.sec_throughput_lbl)
        graph_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["air-card-padded"])
        legend = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.graph_dl_lbl = Gtk.Label(label="↓ 0 KB/s", xalign=0, css_classes=["air-row-title"])
        self.graph_ul_lbl = Gtk.Label(label="↑ 0 KB/s", xalign=0, css_classes=["air-subtitle"])
        legend.append(self.graph_dl_lbl)
        legend.append(self.graph_ul_lbl)
        graph_card.append(legend)

        self.traffic_graph = LiveTrafficGraph(max_points=36)
        self.traffic_graph.set_dark(self._dark_mode)
        graph_card.append(self.traffic_graph)
        page.append(graph_card)

        self.devices_header = _section_label(tr("devices_header", count=0))
        page.append(self.devices_header)

        self.devices_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["air-card"])
        page.append(self.devices_card)

        self.devices_footer = _section_footer("")
        page.append(self.devices_footer)
        return scroll

    # ── Settings Page ─────────────────────────────────────────────────────────

    def _build_settings_page(self) -> Gtk.Widget:
        scroll, page = self._scrolled_container()

        # Network section
        self.sec_settings_net_lbl = _section_label(tr("section_network"))
        page.append(self.sec_settings_net_lbl)
        net_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["air-card"])

        ssid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.settings_name_lbl = Gtk.Label(
            label=tr("settings_name"), xalign=0, width_chars=10, css_classes=["air-row-title"]
        )
        ssid_row.append(self.settings_name_lbl)
        self.ssid_entry = Gtk.Entry(hexpand=True, placeholder_text=tr("ssid_placeholder"))
        self.ssid_entry.connect("changed", self._mark_settings_dirty)
        ssid_row.append(self.ssid_entry)
        net_card.append(ssid_row)
        net_card.append(_divider())

        pw_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, css_classes=["air-row"])
        self.settings_pw_lbl = Gtk.Label(
            label=tr("settings_password"), xalign=0, width_chars=10, css_classes=["air-row-title"]
        )
        pw_row.append(self.settings_pw_lbl)
        self.pw_entry = Gtk.PasswordEntry(
            hexpand=True,
            show_peek_icon=True,
            placeholder_text=tr("pw_placeholder"),
        )
        self.pw_entry.connect("changed", self._mark_settings_dirty)
        self.gen_pw_btn = Gtk.Button(label=tr("btn_generate"), css_classes=["air-btn-secondary"])
        self.gen_pw_btn.connect("clicked", self._on_generate_password)
        pw_row.append(self.pw_entry)
        pw_row.append(self.gen_pw_btn)
        net_card.append(pw_row)
        net_card.append(_divider())

        hidden_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.hidden_row_lbl = Gtk.Label(
            label=tr("hidden_network"), xalign=0, hexpand=True, css_classes=["air-row-title"]
        )
        hidden_row.append(self.hidden_row_lbl)
        self.hidden_switch = Gtk.Switch(valign=Gtk.Align.CENTER, css_classes=["air-switch"])
        self.hidden_switch.connect("notify::active", self._mark_settings_dirty)
        hidden_row.append(self.hidden_switch)
        net_card.append(hidden_row)
        page.append(net_card)

        # Radio & Privacy section
        self.sec_radio_lbl = _section_label(tr("section_radio_privacy"))
        page.append(self.sec_radio_lbl)
        radio_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["air-card"])

        band_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.band_row_lbl = Gtk.Label(label=tr("settings_band"), xalign=0, hexpand=True, css_classes=["air-row-title"])
        band_row.append(self.band_row_lbl)
        self.band_model = Gtk.StringList.new([label for _, label in band_options()])
        self.band_dropdown = Gtk.DropDown(model=self.band_model)
        self.band_dropdown.connect("notify::selected", self._on_band_changed)
        band_row.append(self.band_dropdown)
        radio_card.append(band_row)
        radio_card.append(_divider())

        method_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.method_row_lbl = Gtk.Label(
            label=tr("settings_method"), xalign=0, hexpand=True, css_classes=["air-row-title"]
        )
        method_row.append(self.method_row_lbl)
        self.method_model = Gtk.StringList.new([label for _, label in method_options()])
        self.method_dropdown = Gtk.DropDown(model=self.method_model)
        self.method_dropdown.connect("notify::selected", self._mark_settings_dirty)
        method_row.append(self.method_dropdown)
        radio_card.append(method_row)
        radio_card.append(_divider())

        ch_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.channel_row_lbl = Gtk.Label(
            label=tr("settings_channel"), xalign=0, hexpand=True, css_classes=["air-row-title"]
        )
        ch_row.append(self.channel_row_lbl)
        self.channel_model = Gtk.StringList.new([label for _, label in self._channel_choices])
        self.channel_dropdown = Gtk.DropDown(model=self.channel_model)
        self.channel_dropdown.connect("notify::selected", self._mark_settings_dirty)
        ch_row.append(self.channel_dropdown)
        radio_card.append(ch_row)
        radio_card.append(_divider())

        dns_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.dns_row_lbl = Gtk.Label(label=tr("settings_dns"), xalign=0, hexpand=True, css_classes=["air-row-title"])
        dns_row.append(self.dns_row_lbl)
        self.dns_model = Gtk.StringList.new([label for _, label in dns_options()])
        self.dns_dropdown = Gtk.DropDown(model=self.dns_model)
        self.dns_dropdown.connect("notify::selected", self._mark_settings_dirty)
        dns_row.append(self.dns_dropdown)
        radio_card.append(dns_row)
        radio_card.append(_divider())

        idle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.idle_row_lbl = Gtk.Label(label=tr("settings_idle"), xalign=0, hexpand=True, css_classes=["air-row-title"])
        idle_row.append(self.idle_row_lbl)
        self.idle_model = Gtk.StringList.new([label for _, label in idle_options()])
        self.idle_dropdown = Gtk.DropDown(model=self.idle_model)
        self.idle_dropdown.connect("notify::selected", self._mark_settings_dirty)
        idle_row.append(self.idle_dropdown)
        radio_card.append(idle_row)
        page.append(radio_card)

        self.dns_footer_lbl = _section_footer(tr("dns_footer"))
        page.append(self.dns_footer_lbl)

        self.save_btn = Gtk.Button(
            label=tr("save_settings"),
            margin_top=14,
            css_classes=["air-btn-primary"],
        )
        self.save_btn.set_sensitive(False)
        self.save_btn.connect("clicked", self._on_save_settings)
        page.append(self.save_btn)

        # System section
        self.sec_sys_lbl = _section_label(tr("section_system"))
        page.append(self.sec_sys_lbl)
        sys_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["air-card"])

        lang_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.lang_row_lbl = Gtk.Label(
            label=tr("settings_language"), xalign=0, hexpand=True, css_classes=["air-row-title"]
        )
        lang_row.append(self.lang_row_lbl)
        self.lang_dropdown = Gtk.DropDown.new_from_strings([label for _, label in SUPPORTED_LANGUAGES])
        cur_lang = get_language()
        self.lang_dropdown.set_selected(
            next((i for i, item in enumerate(SUPPORTED_LANGUAGES) if item[0] == cur_lang), 0)
        )
        self.lang_dropdown.connect("notify::selected", self._on_language_dropdown_changed)
        lang_row.append(self.lang_dropdown)
        sys_card.append(lang_row)
        sys_card.append(_divider())

        boot_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["air-row"])
        self.boot_row_lbl = Gtk.Label(
            label=tr("autostart_boot"), xalign=0, hexpand=True, css_classes=["air-row-title"]
        )
        boot_row.append(self.boot_row_lbl)
        self.autostart_switch = Gtk.Switch(valign=Gtk.Align.CENTER, css_classes=["air-switch"])
        self.autostart_switch.connect("state-set", self._on_autostart_toggled)
        boot_row.append(self.autostart_switch)
        sys_card.append(boot_row)
        sys_card.append(_divider())

        hw_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-row"])
        self.hw_row_lbl = Gtk.Label(label=tr("wifi_adapter"), xalign=0, css_classes=["air-row-title"])
        hw_row.append(self.hw_row_lbl)
        self.hw_val = Gtk.Label(
            label=tr("detecting"), xalign=1, hexpand=True, ellipsize=3, css_classes=["air-value"]
        )
        hw_row.append(self.hw_val)
        sys_card.append(hw_row)

        page.append(sys_card)
        return scroll

    # ── Async Worker & Polling ────────────────────────────────────────────────

    def _poll_tick(self) -> bool:
        if not self.busy:
            self.refresh(quiet=True)
        return True

    def refresh(self, quiet: bool = False) -> None:
        if not self.backend.available():
            self.master_subtitle.set_label(tr("engine_missing"))
            return

        def worker() -> None:
            status = self.backend.status()
            detect = self.detect_data or self.backend.detect()
            dev_servers = detect_dev_servers()
            GLib.idle_add(self._apply_state, status, detect, quiet, dev_servers)

        threading.Thread(target=worker, daemon=True).start()

    def _run_privileged(self, fn: Callable[[], Result], after: Optional[Callable[[Result], None]] = None) -> None:
        if self.busy:
            return
        self._set_busy(True)

        def worker() -> None:
            res = fn()
            status = self.backend.status()
            GLib.idle_add(self._finish_privileged, res, status, after)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_privileged(
        self,
        res: Result,
        status: dict,
        after: Optional[Callable[[Result], None]],
    ) -> None:
        self._set_busy(False)
        self._apply_state(status, self.detect_data, quiet=True)
        if res.message:
            self.toast(res.message)
        if after:
            after(res)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.spinner.set_visible(busy)
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()
        self.power_switch.set_sensitive(not busy)
        self.iphone_bridge_switch.set_sensitive(not busy)
        self.share_btn.set_sensitive(not busy)
        self.save_btn.set_sensitive(not busy and self._settings_dirty)

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast.new(message))

    # ── State Rendering ───────────────────────────────────────────────────────

    def _localized_runtime_notes(self, hotspot: Optional[dict]) -> List[str]:
        if not hotspot:
            return []
        method = hotspot.get("method")
        if method == "nmcli":
            return [tr("nmcli_note")]
        if method == "p2p":
            uplink = self._uplink_ssid() or hotspot.get("sta_ssid_at_start")
            uplink_band = self._uplink_band_label()
            out_band = band_label(hotspot.get("band"))
            if uplink and uplink_band in ("2.4 GHz", "5 GHz") and uplink_band != out_band:
                dns_note = tr("bridge_note_adguard") if hotspot.get("dns_mode") == "adguard" else ""
                return [
                    tr(
                        "bridge_note",
                        uplink=uplink,
                        uplink_band=uplink_band,
                        ssid=hotspot.get("ssid", "MintSpot-5G"),
                        out_band=out_band,
                        ch=hotspot.get("channel", "?"),
                        dns_note=dns_note,
                    )
                ]
        return list(hotspot.get("notes") or [])

    def _apply_state(
        self,
        status: dict,
        detect: dict,
        quiet: bool,
        dev_servers: Optional[List[DevServer]] = None,
    ) -> None:
        self.data = status or {}
        if detect:
            self.detect_data = detect
        if dev_servers is not None:
            self._dev_servers = dev_servers

        hotspot = self.data.get("hotspot")
        cfg = self.data.get("config") or {}
        clients = self.data.get("clients") or []
        uplink_ssid = self._uplink_ssid()
        uplink_band = self._uplink_band_label()

        # Track expected state & Auto-Heal Watchdog
        if hotspot:
            self._expected_on = True
        elif self._expected_on and uplink_ssid and not self.busy:
            now_mono = time.monotonic()
            if (now_mono - self._last_heal_attempt) >= 30.0:
                self._last_heal_attempt = now_mono
                self._notify_desktop(tr("notify_watchdog_title"), tr("notify_watchdog_body"))
                self._run_privileged(self.backend.start)

        # New Device Alert (desktop notification when an unseen MAC joins)
        current_macs = {c.get("mac") for c in clients if c.get("mac")}
        if self._known_macs is None:
            self._known_macs = set(current_macs)
        else:
            new_macs = current_macs - self._known_macs
            for client in clients:
                mac = client.get("mac")
                if mac in new_macs:
                    name = client.get("hostname") or mac
                    ip = client.get("ip") or tr("connecting_ip")
                    self._notify_desktop(
                        tr("notify_new_device_title"),
                        tr("notify_new_device_body", name=name, ip=ip),
                    )
            self._known_macs = set(current_macs)

        # Idle auto-off check
        idle_mins = int(cfg.get("idle_off_minutes") or 0)
        if hotspot and idle_mins > 0 and len(clients) == 0:
            now = time.monotonic()
            if self._idle_since is None:
                self._idle_since = now
            elif (now - self._idle_since) >= idle_mins * 60 and not self.busy:
                self._idle_since = None
                self._expected_on = False
                self.toast(tr("toast_idle_off", mins=idle_mins))
                self._run_privileged(self.backend.stop)
        else:
            self._idle_since = None

        self._syncing_ui = True
        try:
            is_on = bool(hotspot)
            self.power_switch.set_active(is_on)
            self.power_switch.set_state(is_on)

            for cls in ("air-pill-live", "air-pill-off"):
                self.status_pill.remove_css_class(cls)
            if is_on:
                b_lbl = band_label(hotspot.get("band"))
                self.status_pill.set_label(tr("status_live", band=b_lbl))
                self.status_pill.add_css_class("air-pill-live")
                self.master_subtitle.set_label(
                    tr(
                        "broadcasting_on",
                        ssid=hotspot.get("ssid", "MintSpot-5G"),
                        channel=hotspot.get("channel", "?"),
                    )
                )
            else:
                self.status_pill.set_label(tr("status_off"))
                self.status_pill.add_css_class("air-pill-off")
                self.master_subtitle.set_label(
                    tr("ready_to_bridge", ssid=uplink_ssid) if uplink_ssid else tr("hotspot_turned_off")
                )

            self.uplink_name.set_label(uplink_ssid or tr("no_wifi"))
            self.uplink_band.set_label(uplink_band if uplink_ssid else tr("disconnected"))

            active_ssid = (hotspot or {}).get("ssid") or cfg.get("ssid") or "MintSpot-5G"
            active_band = band_label((hotspot or {}).get("band") or cfg.get("band") or "a")
            active_method = (hotspot or {}).get("method") or cfg.get("method") or "p2p"
            self.out_name.set_label(active_ssid)
            method_tag = tr("method_wifi_direct") if active_method == "p2p" else active_method
            self.out_band.set_label(f"{active_band} · {method_tag}")

            is_bridge_mode = cfg.get("method") == "p2p" and cfg.get("band") == "a"
            self.iphone_bridge_switch.set_active(is_bridge_mode)
            self.iphone_bridge_switch.set_state(is_bridge_mode)

            self.ssid_val.set_label(active_ssid)
            if is_on:
                self.channel_val.set_label(f"{active_band} · Ch {hotspot.get('channel', '?')}")
                subnet = hotspot.get("subnet") or ""
                iface_text = f"{hotspot.get('ap_interface', '')} ({hotspot.get('method', '')})"
                self.iface_val.set_label(f"{iface_text} · {subnet}" if subnet else iface_text)
            else:
                self.channel_val.set_label(tr("band_configured", band=active_band))
                self.iface_val.set_label(tr("inactive"))
            self.clients_count_val.set_label(str(len(clients)))

            notes = self._localized_runtime_notes(hotspot)
            if notes:
                self.notice_label.set_label("\n".join(notes))
                self.notice_label.set_visible(True)
            elif not self.data and not quiet:
                self.notice_label.set_label(tr("status_read_error"))
                self.notice_label.set_visible(True)
            else:
                self.notice_label.set_visible(False)

            self._render_dev_servers(hotspot)
            self._render_devices(clients, hotspot)

            if not self._settings_dirty and cfg:
                self.ssid_entry.set_text(cfg.get("ssid") or "")
                self.hidden_switch.set_active(bool(cfg.get("hidden")))
                band_val = cfg.get("band") or "a"
                self.band_dropdown.set_selected(
                    next((i for i, k in enumerate(BAND_KEYS) if k == band_val), 0)
                )
                self._rebuild_channels(band_val, str(cfg.get("channel") or "auto"))
                method_val = cfg.get("method") or "p2p"
                self.method_dropdown.set_selected(
                    next((i for i, k in enumerate(METHOD_KEYS) if k == method_val), 0)
                )
                dns_val = cfg.get("dns_mode") or "cloudflare"
                self.dns_dropdown.set_selected(
                    next((i for i, k in enumerate(DNS_KEYS) if k == dns_val), 0)
                )
                self.idle_dropdown.set_selected(
                    next((i for i, mins in enumerate(IDLE_MINUTES) if mins == idle_mins), 0)
                )
            self.autostart_switch.set_active(bool(self.data.get("autostart")))
            self.autostart_switch.set_state(bool(self.data.get("autostart")))

            cap = (self.detect_data or {}).get("capability") or {}
            chipset = cap.get("chipset") or cap.get("driver") or tr("unknown_adapter")
            p2p_ok = tr("p2p_ready") if cap.get("p2p_go_own_channel") else tr("single_channel")
            self.hw_val.set_label(f"{chipset} ({p2p_ok})")

            self.tray.update(
                is_on=is_on,
                ssid=active_ssid,
                band=active_band,
                clients_count=len(clients),
            )
        finally:
            self._syncing_ui = False

    def _uplink_ssid(self) -> Optional[str]:
        for iface in self.data.get("interfaces") or []:
            if iface.get("connected_ssid"):
                return iface["connected_ssid"]
        hotspot = self.data.get("hotspot") or {}
        return hotspot.get("sta_ssid_at_start")

    def _uplink_band_label(self) -> str:
        for iface in self.data.get("interfaces") or []:
            if iface.get("connected_ssid"):
                freq = iface.get("freq") or 0
                if freq >= 5000:
                    return "5 GHz"
                if freq >= 2400:
                    return "2.4 GHz"
        return tr("connected")

    def _render_dev_servers(self, hotspot: Optional[dict]) -> None:
        _clear_box(self.dev_list_box)
        gateway = (hotspot or {}).get("gateway") or "10.42.99.1"

        if not self._dev_servers:
            self.dev_list_box.append(
                Gtk.Label(
                    label=tr("no_dev_server"),
                    xalign=0,
                    wrap=True,
                    css_classes=["air-subtitle", "air-row"],
                )
            )
            return

        for idx, srv in enumerate(self._dev_servers):
            if idx > 0:
                self.dev_list_box.append(_divider())
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-row"])
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            info.append(Gtk.Label(label=f"{srv.label} (:{srv.port})", xalign=0, css_classes=["air-row-title"]))
            url = f"http://{gateway}:{srv.port}"
            info.append(Gtk.Label(label=url, xalign=0, ellipsize=3, css_classes=["air-mono"]))
            row.append(info)

            btn = Gtk.Button(label=tr("safari_qr"), css_classes=["air-btn-primary"])
            btn.connect("clicked", lambda _b, p=srv.port, lbl=srv.label: self._open_dev_qr(p, lbl))
            row.append(btn)
            self.dev_list_box.append(row)

    def _on_custom_port_qr(self, *_args) -> None:
        raw = self.custom_port_entry.get_text().strip()
        if not raw.isdigit() or not (1 <= int(raw) <= 65535):
            self.toast(tr("invalid_port"))
            return
        self._open_dev_qr(int(raw), tr("local_server_port", port=raw))

    def _open_dev_qr(self, port: int, label: str) -> None:
        hotspot = self.data.get("hotspot")
        if not hotspot:
            self.toast(tr("turn_on_hotspot_dev"))
            return
        gateway = hotspot.get("gateway") or "10.42.99.1"
        url = f"http://{gateway}:{port}"
        sheet = UrlQrSheet(
            self,
            title=label,
            url=url,
            subtitle=tr("dev_qr_subtitle"),
            dark=self._dark_mode,
            on_copied=self.toast,
        )
        sheet.present()

    def _render_devices(self, clients: list, hotspot: Optional[dict]) -> None:
        self.devices_header.set_label(tr("devices_header", count=len(clients)))
        _clear_box(self.devices_card)

        if not hotspot:
            self.traffic_graph.reset()
            self.graph_dl_lbl.set_label("↓ 0 KB/s")
            self.graph_ul_lbl.set_label("↑ 0 KB/s")
            empty = Gtk.Label(
                label=tr("devices_hotspot_off"),
                xalign=0,
                wrap=True,
                css_classes=["air-subtitle", "air-row"],
            )
            self.devices_card.append(empty)
            self.devices_footer.set_label("")
            return

        if not clients:
            self.traffic_graph.push(0.0, 0.0)
            self.graph_dl_lbl.set_label("↓ 0 KB/s")
            self.graph_ul_lbl.set_label("↑ 0 KB/s")
            empty = Gtk.Label(
                label=tr("devices_empty"),
                xalign=0,
                wrap=True,
                css_classes=["air-subtitle", "air-row"],
            )
            self.devices_card.append(empty)
            self.devices_footer.set_label("")
            return

        now = time.monotonic()
        total_dl_rate = 0.0
        total_ul_rate = 0.0
        presets = limit_presets()
        for idx, client in enumerate(clients):
            if idx > 0:
                self.devices_card.append(_divider())

            mac = client.get("mac") or ""
            rx = int(client.get("rx_bytes") or 0)
            tx = int(client.get("tx_bytes") or 0)
            dl_rate = 0.0
            ul_rate = 0.0
            if mac in self._prev_traffic:
                prev_rx, prev_tx, prev_t = self._prev_traffic[mac]
                dt = max(now - prev_t, 0.5)
                # AP tx_bytes == client download; AP rx_bytes == client upload
                dl_rate = max(0.0, (tx - prev_tx) / dt)
                ul_rate = max(0.0, (rx - prev_rx) / dt)
            self._prev_traffic[mac] = (rx, tx, now)
            total_dl_rate += dl_rate
            total_ul_rate += ul_rate

            row_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["air-row"])

            top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)

            name_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            default_name = tr("device_default_name")
            name = client.get("hostname") or default_name
            name_line.append(Gtk.Label(label=name, xalign=0, css_classes=["air-row-title"]))
            if client.get("blocked"):
                name_line.append(Gtk.Label(label=tr("pill_paused"), css_classes=["air-pill", "air-pill-off"]))
            elif client.get("limit_mbps"):
                name_line.append(
                    Gtk.Label(
                        label=tr("pill_cap", mbps=client["limit_mbps"]),
                        css_classes=["air-pill", "air-pill-accent"],
                    )
                )
            info.append(name_line)

            meta = [client.get("ip") or tr("pending_ip"), mac]
            if client.get("signal_dbm") is not None:
                meta.append(f"{client['signal_dbm']} dBm")
            info.append(Gtk.Label(label=" · ".join(p for p in meta if p), xalign=0, css_classes=["air-subtitle"]))
            top.append(info)

            traffic_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
            traffic_col.append(
                Gtk.Label(
                    label=f"↓ {format_speed(dl_rate)}  ↑ {format_speed(ul_rate)}",
                    xalign=1,
                    css_classes=["air-row-title"],
                )
            )
            traffic_col.append(
                Gtk.Label(
                    label=tr("total_traffic", size=format_bytes(tx + rx)),
                    xalign=1,
                    css_classes=["air-subtitle"],
                )
            )
            top.append(traffic_col)
            row_wrap.append(top)

            # Action bar: Rename | Speed Limit | Pause/Resume Internet
            if mac:
                actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                rename_btn = Gtk.Button(label=tr("btn_rename"), css_classes=["air-btn-secondary"])
                rename_btn.connect(
                    "clicked",
                    lambda _b, m=mac, cur=(client.get("hostname") or ""): self._open_rename_dialog(m, cur),
                )
                actions.append(rename_btn)

                limit_dd = Gtk.DropDown.new_from_strings([lbl for _, lbl in presets])
                cur_limit = int(client.get("limit_mbps") or 0)
                sel_idx = next((i for i, p in enumerate(presets) if p[0] == cur_limit), 0)
                limit_dd.set_selected(sel_idx)
                limit_dd.connect(
                    "notify::selected",
                    lambda dd, _pspec, m=mac, orig=sel_idx: self._on_limit_changed(dd, m, orig),
                )
                actions.append(limit_dd)

                is_blocked = bool(client.get("blocked"))
                pause_btn = Gtk.Button(
                    label=tr("btn_resume") if is_blocked else tr("btn_pause"),
                    css_classes=["air-btn-primary" if is_blocked else "air-btn-danger"],
                )
                pause_btn.connect(
                    "clicked",
                    lambda _b, m=mac, blk=not is_blocked: self._run_privileged(lambda: self.backend.block_device(m, blk)),
                )
                actions.append(pause_btn)
                row_wrap.append(actions)

            self.devices_card.append(row_wrap)

        self.traffic_graph.push(total_dl_rate, total_ul_rate)
        self.graph_dl_lbl.set_label(f"↓ {format_speed(total_dl_rate)}")
        self.graph_ul_lbl.set_label(f"↑ {format_speed(total_ul_rate)}")
        self.devices_footer.set_label(tr("devices_footer"))

    # ── User Actions ──────────────────────────────────────────────────────────

    def _on_power_switch(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._syncing_ui:
            return False
        self._expected_on = state
        if state:
            self._run_privileged(self.backend.start)
        else:
            self._run_privileged(self.backend.stop)
        return True

    def _on_iphone_bridge_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._syncing_ui:
            return False
        is_running = bool(self.data.get("hotspot"))

        def apply_bridge() -> Result:
            res = self.backend.enable_iphone_5ghz_bridge() if state else self.backend.disable_iphone_5ghz_bridge()
            if res.ok and is_running:
                self.backend.stop()
                return self.backend.start()
            return res

        self._run_privileged(apply_bridge)
        return True

    def _on_copy_ssid(self, *_args) -> None:
        ssid = self.ssid_val.get_label()
        if ssid and ssid != "--":
            _copy_to_clipboard(self, ssid)
            self.toast(tr("toast_ssid_copied"))

    def _open_share_sheet(self) -> None:
        def after(res: Result) -> None:
            if not res.ok:
                return
            ssid = (self.data.get("hotspot") or {}).get("ssid") or res.data.get("ssid") or ""
            password = res.data.get("password") or ""
            hidden = bool(res.data.get("hidden"))
            if not ssid or not password:
                self.toast(tr("toast_set_creds_first"))
                return
            sheet = ShareSheet(
                self,
                ssid=ssid,
                password=password,
                hidden=hidden,
                dark=self._dark_mode,
                on_copied=self.toast,
            )
            sheet.present()

        self._run_privileged(self.backend.secrets, after=after)

    def _on_run_speedtest(self, *_args) -> None:
        if self._speedtesting:
            return
        self._speedtesting = True
        self._speedtest_state = "running"
        self._speedtest_error = ""
        self.speed_btn.set_sensitive(False)
        self.speed_btn.set_label(tr("testing"))
        self.ping_val.set_label("...")
        self.dl_val.set_label("...")
        self.ul_val.set_label("...")

        def on_stage(msg: str) -> None:
            GLib.idle_add(self.speed_status.set_label, msg)

        def worker() -> None:
            res = run_speedtest(on_stage=on_stage)
            GLib.idle_add(self._finish_speedtest, res)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_speedtest(self, res: SpeedTestResult) -> None:
        self._speedtesting = False
        self.speed_btn.set_sensitive(True)
        self.speed_btn.set_label(tr("run_test"))
        if res.ok:
            self._speedtest_state = "done"
            self.ping_val.set_label(f"{res.ping_ms} ms")
            self.dl_val.set_label(f"{res.download_mbps} Mbps")
            self.ul_val.set_label(f"{res.upload_mbps} Mbps")
            self.speed_status.set_label(tr("speedtest_done"))
        else:
            self._speedtest_state = "error"
            self._speedtest_error = res.error
            self.ping_val.set_label("-- ms")
            self.dl_val.set_label("-- Mbps")
            self.ul_val.set_label("-- Mbps")
            self.speed_status.set_label(res.error)
            self.toast(res.error)

    def _on_limit_changed(self, dropdown: Gtk.DropDown, mac: str, orig_idx: int) -> None:
        if self._syncing_ui:
            return
        presets = limit_presets()
        idx = dropdown.get_selected()
        if idx == orig_idx or not (0 <= idx < len(presets)):
            return
        mbps = presets[idx][0]
        self._run_privileged(lambda: self.backend.limit_device(mac, mbps))

    def _open_rename_dialog(self, mac: str, current_name: str) -> None:
        win = Adw.Window(
            transient_for=self,
            modal=True,
            title=tr("rename_title"),
            default_width=340,
            resizable=False,
        )
        win.add_css_class("air-window")
        if self._dark_mode:
            win.add_css_class("air-dark")

        key_ctrl = Gtk.EventControllerKey()

        def on_key(_ctrl, keyval: int, _keycode: int, _state) -> bool:
            if keyval == Gdk.KEY_Escape:
                win.close()
                return True
            return False

        key_ctrl.connect("key-pressed", on_key)
        win.add_controller(key_ctrl)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hdr = Adw.HeaderBar()
        hdr.add_css_class("air-headerbar")
        hdr.set_title_widget(Gtk.Label(label=tr("rename_title"), css_classes=["air-row-title"]))
        root.append(hdr)

        body = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=16,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        body.append(Gtk.Label(label=tr("rename_hint", mac=mac), xalign=0, css_classes=["air-subtitle"]))
        entry = Gtk.Entry(text=current_name, placeholder_text=tr("rename_placeholder"))
        body.append(entry)

        save = Gtk.Button(label=tr("save_name"), css_classes=["air-btn-primary"])

        def do_save(*_a) -> None:
            new_name = entry.get_text().strip()
            win.close()
            self._run_privileged(lambda: self.backend.rename_device(mac, new_name))

        entry.connect("activate", do_save)
        save.connect("clicked", do_save)
        body.append(save)
        root.append(body)
        win.set_content(root)
        win.present()

    def _mark_settings_dirty(self, *_args) -> None:
        if self._syncing_ui:
            return
        self._settings_dirty = True
        self.save_btn.set_sensitive(not self.busy)

    def _on_band_changed(self, *_args) -> None:
        if self._syncing_ui:
            return
        idx = self.band_dropdown.get_selected()
        band_val = BAND_KEYS[idx] if 0 <= idx < len(BAND_KEYS) else "a"
        self._rebuild_channels(band_val, "auto")
        self._mark_settings_dirty()

    def _rebuild_channels(self, band: str, selected_channel: str) -> None:
        self._channel_choices = channel_options(band)
        _replace_string_list(self.channel_model, [label for _, label in self._channel_choices])
        ch_idx = next((i for i, c in enumerate(self._channel_choices) if c[0] == selected_channel), 0)
        self.channel_dropdown.set_selected(ch_idx)

    def _on_generate_password(self, *_args) -> None:
        self.pw_entry.set_text(generate_password(12))
        self.toast(tr("toast_pw_generated"))

    def _on_save_settings(self, *_args) -> None:
        ssid = self.ssid_entry.get_text().strip()
        password = self.pw_entry.get_text()
        if not ssid:
            self.toast(tr("toast_ssid_empty"))
            return
        if password and len(password) < 8:
            self.toast(tr("toast_pw_short"))
            return

        band_idx = self.band_dropdown.get_selected()
        method_idx = self.method_dropdown.get_selected()
        ch_idx = self.channel_dropdown.get_selected()
        dns_idx = self.dns_dropdown.get_selected()
        idle_idx = self.idle_dropdown.get_selected()

        band_val = BAND_KEYS[band_idx] if 0 <= band_idx < len(BAND_KEYS) else "a"
        method_val = METHOD_KEYS[method_idx] if 0 <= method_idx < len(METHOD_KEYS) else "p2p"
        channel_val = self._channel_choices[ch_idx][0] if 0 <= ch_idx < len(self._channel_choices) else "auto"
        dns_val = DNS_KEYS[dns_idx] if 0 <= dns_idx < len(DNS_KEYS) else "cloudflare"
        idle_val = IDLE_MINUTES[idle_idx] if 0 <= idle_idx < len(IDLE_MINUTES) else 0
        hidden = self.hidden_switch.get_active()

        def after(res: Result) -> None:
            if res.ok:
                self._settings_dirty = False
                self.pw_entry.set_text("")
                self.save_btn.set_sensitive(False)

        self._run_privileged(
            lambda: self.backend.save_config(
                ssid=ssid,
                password=password,
                band=band_val,
                method=method_val,
                channel=channel_val,
                hidden=hidden,
                dns_mode=dns_val,
                idle_off_minutes=idle_val,
            ),
            after=after,
        )

    def _on_autostart_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._syncing_ui:
            return False
        self._run_privileged(lambda: self.backend.set_autostart(state))
        return True
