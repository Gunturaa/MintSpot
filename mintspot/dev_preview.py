"""Local Dev Server detector and Safari QR preview modal for MintSpot."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from gi.repository import Adw, Gdk, Gtk

from .i18n import tr
from .qr_dialog import _copy_text, _qr_texture

KNOWN_DEV_PORTS = {
    3000: "Next.js / React",
    3001: "Dev Server",
    4173: "Vite Preview",
    4200: "Angular",
    4321: "Astro",
    5000: "Flask / API",
    5173: "Vite",
    5174: "Vite",
    8000: "Django / Python",
    8080: "HTTP Dev",
    8081: "Expo / Metro",
    8888: "Jupyter / Dev",
    9000: "Dev Server",
}


@dataclass
class DevServer:
    port: int
    label: str
    bind_addr: str


def detect_dev_servers() -> List[DevServer]:
    """Detect local HTTP dev servers listening on TCP ports via `ss -tln`."""
    try:
        proc = subprocess.run(["ss", "-tlnH"], capture_output=True, text=True, timeout=3)
        if proc.returncode != 0:
            return []
    except (OSError, subprocess.SubprocessError):
        return []

    found: dict[int, DevServer] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local_addr = parts[3]
        m = re.search(r":(\d+)$", local_addr)
        if not m:
            continue
        port = int(m.group(1))
        if port in KNOWN_DEV_PORTS or (3000 <= port <= 9999 and port not in (5353, 5387, 631)):
            bind = local_addr[: -(len(m.group(0)))]
            # Prefer wildcard / LAN-reachable bindings over localhost-only
            if port not in found or bind in ("*", "0.0.0.0", "[::]", "::"):
                label = KNOWN_DEV_PORTS.get(port, tr("local_server_port", port=port))
                found[port] = DevServer(port=port, label=label, bind_addr=bind)

    return sorted(found.values(), key=lambda s: s.port)


class UrlQrSheet(Adw.Window):
    """Modal sheet showing a scannable URL QR code to open directly in iPhone Safari."""

    def __init__(
        self,
        parent: Gtk.Window,
        title: str,
        url: str,
        subtitle: Optional[str] = None,
        dark: bool = False,
        on_copied=None,
    ) -> None:
        subtitle = subtitle or tr("url_qr_default_subtitle")
        super().__init__(
            transient_for=parent,
            modal=True,
            title=title,
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
        header.set_title_widget(Gtk.Label(label=title, css_classes=["air-row-title"]))
        root.append(header)

        body = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=18,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        texture = _qr_texture(url)
        if texture is not None:
            frame = Gtk.Box(halign=Gtk.Align.CENTER, css_classes=["air-qr-frame"])
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_size_request(210, 210)
            frame.append(picture)
            body.append(frame)

        body.append(
            Gtk.Label(
                label=subtitle,
                wrap=True,
                justify=Gtk.Justification.CENTER,
                css_classes=["air-subtitle"],
            )
        )

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["air-card", "air-row"])
        url_lbl = Gtk.Label(label=url, xalign=0, hexpand=True, selectable=True, ellipsize=3, css_classes=["air-mono"])
        copy_btn = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text=tr("tooltip_copy_url"),
            css_classes=["air-btn-secondary"],
        )
        copy_btn.connect("clicked", lambda *_: self._do_copy(url))
        card.append(url_lbl)
        card.append(copy_btn)
        body.append(card)

        root.append(body)
        self.set_content(root)

    def _do_copy(self, url: str) -> None:
        _copy_text(self, url)
        if self._on_copied:
            self._on_copied(tr("toast_url_copied"))

    def _on_key(self, _ctrl, keyval: int, _keycode: int, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
