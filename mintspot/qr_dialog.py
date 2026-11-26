"""iOS-style Wi-Fi QR Code & credentials share sheet."""

from __future__ import annotations

from typing import Optional, Tuple

from gi.repository import Adw, Gdk, GLib, Gtk

from .backend import wifi_qr_payload
from .i18n import tr


def _qr_pixels(payload: str, scale: int = 8, border: int = 2) -> Optional[Tuple[int, bytes]]:
    try:
        import qrcode
    except ImportError:
        return None
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=border)
    qr.add_data(payload)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    dark = b"\x00\x00\x00" * scale
    light = b"\xff\xff\xff" * scale
    rgb = b"".join(b"".join(dark if cell else light for cell in row) * scale for row in matrix)
    return len(matrix) * scale, rgb


def _qr_texture(payload: str) -> Optional[Gdk.MemoryTexture]:
    drawn = _qr_pixels(payload)
    if drawn is None:
        return None
    side, rgb = drawn
    return Gdk.MemoryTexture.new(side, side, Gdk.MemoryFormat.R8G8B8, GLib.Bytes.new(rgb), side * 3)


def _copy_text(widget: Gtk.Widget, text: str) -> None:
    display = widget.get_display()
    if display is not None:
        display.get_clipboard().set(text)


class ShareSheet(Adw.Window):
    def __init__(
        self,
        parent: Gtk.Window,
        ssid: str,
        password: str,
        hidden: bool = False,
        dark: bool = False,
        on_copied=None,
    ) -> None:
        super().__init__(
            transient_for=parent,
            modal=True,
            title=tr("qr_join_title"),
            default_width=360,
            resizable=False,
        )
        self.add_css_class("air-window")
        if dark:
            self.add_css_class("air-dark")
        self._on_copied = on_copied

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self.add_controller(key_ctrl)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        header.add_css_class("air-headerbar")
        header.set_title_widget(Gtk.Label(label=tr("qr_join_title"), css_classes=["air-row-title"]))
        root.append(header)

        body = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=18,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        payload = wifi_qr_payload(ssid, password, hidden)
        texture = _qr_texture(payload) if payload else None
        if texture is not None:
            frame = Gtk.Box(halign=Gtk.Align.CENTER, css_classes=["air-qr-frame"])
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_size_request(210, 210)
            frame.append(picture)
            body.append(frame)
            hint = Gtk.Label(
                label=tr("qr_join_hint"),
                wrap=True,
                justify=Gtk.Justification.CENTER,
                css_classes=["air-subtitle"],
            )
        else:
            hint = Gtk.Label(
                label=tr("qr_missing_pkg"),
                wrap=True,
                justify=Gtk.Justification.CENTER,
                css_classes=["air-subtitle"],
            )
        body.append(hint)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["air-card"])
        card.append(self._cred_row(tr("qr_network_label"), ssid, tr("toast_ssid_copied")))
        card.append(Gtk.Box(css_classes=["air-divider"]))
        card.append(self._cred_row(tr("qr_password_label"), password, tr("toast_pw_copied")))
        body.append(card)

        root.append(body)
        self.set_content(root)

    def _cred_row(self, title: str, value: str, toast_msg: str) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-row"])
        lbl = Gtk.Label(label=title, xalign=0, css_classes=["air-row-title"])
        val = Gtk.Label(
            label=value,
            xalign=1,
            hexpand=True,
            selectable=True,
            ellipsize=3,
            css_classes=["air-mono"],
        )
        btn = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text=tr("tooltip_copy_field", label=title),
            css_classes=["air-btn-secondary"],
        )
        btn.connect("clicked", lambda *_: self._do_copy(value, toast_msg))
        row.append(lbl)
        row.append(val)
        row.append(btn)
        return row

    def _do_copy(self, value: str, toast_msg: str) -> None:
        _copy_text(self, value)
        if self._on_copied:
            self._on_copied(toast_msg)

    def _on_key(self, _ctrl, keyval: int, _keycode: int, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
