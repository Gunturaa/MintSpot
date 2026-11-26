"""Cairo-drawn macOS Activity Monitor-style live throughput graph for GTK4."""

from __future__ import annotations

from collections import deque
from typing import Deque, Tuple

import cairo
from gi.repository import Gtk

from .backend import format_speed
from .i18n import tr


class LiveTrafficGraph(Gtk.DrawingArea):
    def __init__(self, max_points: int = 40) -> None:
        super().__init__()
        self._max_points = max_points
        self._dl: Deque[float] = deque([0.0] * max_points, maxlen=max_points)
        self._ul: Deque[float] = deque([0.0] * max_points, maxlen=max_points)
        self._dark = False
        self.set_content_height(104)
        self.set_hexpand(True)
        self.set_draw_func(self._on_draw)

    def set_dark(self, dark: bool) -> None:
        if self._dark != dark:
            self._dark = dark
            self.queue_draw()

    def push(self, dl_bps: float, ul_bps: float) -> None:
        self._dl.append(max(0.0, dl_bps))
        self._ul.append(max(0.0, ul_bps))
        self.queue_draw()

    def reset(self) -> None:
        self._dl = deque([0.0] * self._max_points, maxlen=self._max_points)
        self._ul = deque([0.0] * self._max_points, maxlen=self._max_points)
        self.queue_draw()

    def _on_draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        if width <= 20 or height <= 20:
            return

        pad_l, pad_r, pad_t, pad_b = 8.0, 8.0, 18.0, 10.0
        plot_w = max(width - pad_l - pad_r, 1.0)
        plot_h = max(height - pad_t - pad_b, 1.0)

        peak = max(max(self._dl), max(self._ul), 64.0 * 1024.0)  # min scale 64 KB/s

        # Subtle horizontal reference lines (3 steps)
        grid_rgba = (1.0, 1.0, 1.0, 0.08) if self._dark else (0.24, 0.24, 0.26, 0.10)
        cr.set_source_rgba(*grid_rgba)
        cr.set_line_width(1.0)
        for frac in (0.0, 0.5, 1.0):
            y = pad_t + plot_h * frac
            cr.move_to(pad_l, y)
            cr.line_to(pad_l + plot_w, y)
        cr.stroke()

        # Peak scale label top-right
        ink = (0.68, 0.68, 0.70, 1.0) if self._dark else (0.35, 0.35, 0.37, 1.0)
        cr.set_source_rgba(*ink)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10.0)
        label = tr("graph_peak", speed=format_speed(peak))
        ext = cr.text_extents(label)
        cr.move_to(pad_l + plot_w - ext.width - 2, pad_t - 5)
        cr.show_text(label)

        # Draw upload first (emerald), then download on top (Apple blue)
        ul_col = (0.43, 0.91, 0.53) if self._dark else (0.09, 0.44, 0.20)
        dl_col = (0.39, 0.71, 1.0) if self._dark else (0.0, 0.40, 0.80)

        self._draw_series(cr, self._ul, peak, pad_l, pad_t, plot_w, plot_h, ul_col, fill_alpha=0.10)
        self._draw_series(cr, self._dl, peak, pad_l, pad_t, plot_w, plot_h, dl_col, fill_alpha=0.16)

    def _draw_series(
        self,
        cr: cairo.Context,
        values: Deque[float],
        peak: float,
        x0: float,
        y0: float,
        w: float,
        h: float,
        rgb: Tuple[float, float, float],
        fill_alpha: float,
    ) -> None:
        n = len(values)
        if n < 2:
            return
        step = w / (n - 1)
        pts = [
            (x0 + i * step, y0 + h - min(v / peak, 1.0) * h)
            for i, v in enumerate(values)
        ]

        # Area fill
        cr.new_path()
        cr.move_to(pts[0][0], y0 + h)
        for px, py in pts:
            cr.line_to(px, py)
        cr.line_to(pts[-1][0], y0 + h)
        cr.close_path()
        cr.set_source_rgba(rgb[0], rgb[1], rgb[2], fill_alpha)
        cr.fill()

        # Crisp line stroke
        cr.new_path()
        cr.move_to(*pts[0])
        for px, py in pts[1:]:
            cr.line_to(px, py)
        cr.set_source_rgba(rgb[0], rgb[1], rgb[2], 0.95)
        cr.set_line_width(2.0)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.stroke()
