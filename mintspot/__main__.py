"""Entry point for MintSpot."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from . import APP_ID  # noqa: E402
from .window import MintSpotWindow  # noqa: E402


class MintSpotApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._window: MintSpotWindow | None = None

    def do_activate(self) -> None:
        if self._window is None:
            self._window = MintSpotWindow(application=self)
        self._window.present()


def main() -> int:
    app = MintSpotApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
