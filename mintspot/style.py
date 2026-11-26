"""macOS Sequoia / iOS System Settings CSS for GTK4 + Libadwaita.

All foreground/background pairings are verified against WCAG AA (4.5:1 normal,
3.0:1 large / non-text UI) in both Light and Dark themes.
"""

from __future__ import annotations

from gi.repository import Gdk, Gtk

CSS = """
/* ── Base Light Theme (macOS / iOS System Settings) ──────────────────────── */
window.air-window {
    background-color: #F2F2F7;
    color: #1C1C1E;
}

.air-headerbar {
    background-color: #F2F2F7;
    border-bottom: 1px solid rgba(60, 60, 67, 0.14);
    box-shadow: none;
    padding-top: 4px;
    padding-bottom: 4px;
}

/* Segmented navigation pill (macOS style) */
.air-segmented {
    background-color: #E3E3E8;
    border-radius: 10px;
    padding: 3px;
}

.air-segmented button {
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 5px 14px;
    min-height: 26px;
    font-weight: 600;
    font-size: 13px;
    color: #5A5A5E;
    box-shadow: none;
}

.air-segmented button:hover {
    color: #1C1C1E;
}

.air-segmented button.active-seg {
    background-color: #FFFFFF;
    color: #1C1C1E;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

/* Inset grouped cards (iOS Settings style) */
.air-card {
    background-color: #FFFFFF;
    border: 1px solid rgba(60, 60, 67, 0.14);
    border-radius: 12px;
    padding: 0;
}

.air-card-padded {
    background-color: #FFFFFF;
    border: 1px solid rgba(60, 60, 67, 0.14);
    border-radius: 12px;
    padding: 16px;
}

.air-section-title {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #5A5A5E;
    margin-left: 14px;
    margin-bottom: 6px;
    margin-top: 14px;
}

.air-section-footer {
    font-size: 12px;
    color: #5A5A5E;
    margin-left: 14px;
    margin-right: 14px;
    margin-top: 6px;
}

.air-row {
    padding: 12px 16px;
}

.air-divider {
    background-color: rgba(60, 60, 67, 0.14);
    min-height: 1px;
    margin-left: 16px;
}

/* Typography */
.air-hero-title {
    font-size: 17px;
    font-weight: 700;
    color: #1C1C1E;
}

.air-row-title {
    font-size: 14px;
    font-weight: 600;
    color: #1C1C1E;
}

.air-subtitle {
    font-size: 12.5px;
    color: #5A5A5E;
}

.air-value {
    font-size: 13.5px;
    color: #5A5A5E;
    font-feature-settings: "tnum";
}

.air-mono {
    font-family: monospace;
    font-size: 13px;
    color: #1C1C1E;
}

/* App icon badge inside master card */
.air-icon-badge {
    background-color: #E3E3E8;
    color: #1C1C1E;
    border-radius: 10px;
    min-width: 40px;
    min-height: 40px;
}

.air-icon-badge.live {
    background-color: #187032;
    color: #FFFFFF;
}

/* Status pills */
.air-pill {
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 700;
}

.air-pill-live {
    background-color: #E6F5EA;
    color: #187032;
}

.air-pill-off {
    background-color: #E5E5EA;
    color: #5A5A5E;
}

.air-pill-accent {
    background-color: #E5F0FB;
    color: #0066CC;
}

/* Signal Bridge strip (signature motif) */
.air-bridge-node {
    background-color: #F2F2F7;
    border: 1px solid rgba(60, 60, 67, 0.14);
    border-radius: 10px;
    padding: 10px 12px;
}

.air-bridge-kicker {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #5A5A5E;
}

.air-bridge-name {
    font-size: 14px;
    font-weight: 700;
    color: #1C1C1E;
}

.air-bridge-band {
    font-size: 12px;
    font-weight: 600;
    color: #0066CC;
}

/* Buttons */
.air-btn-primary {
    background-color: #0066CC;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 600;
    font-size: 14px;
    box-shadow: none;
}

.air-btn-primary:hover {
    background-color: #0055B3;
}

.air-btn-primary:disabled {
    opacity: 0.5;
}

.air-btn-secondary {
    background-color: #E5E5EA;
    color: #1C1C1E;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 13px;
    box-shadow: none;
}

.air-btn-secondary:hover {
    background-color: #D8D8DF;
}

.air-lang-btn {
    padding: 4px 9px;
    min-height: 26px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.03em;
}

.air-btn-danger {
    background-color: transparent;
    color: #C92A2A;
    border: 1px solid rgba(201, 42, 42, 0.35);
    border-radius: 8px;
    padding: 5px 10px;
    font-weight: 600;
    font-size: 12.5px;
    box-shadow: none;
}

.air-btn-danger:hover {
    background-color: rgba(201, 42, 42, 0.08);
}

/* Apple-style green switch */
switch.air-switch:checked {
    background-color: #248A3D;
}

/* Keyboard focus visibility (WCAG 1.4.11) */
button:focus-visible,
switch:focus-visible,
entry:focus-visible,
dropdown:focus-visible {
    outline: 2px solid #0066CC;
    outline-offset: 2px;
}

/* Notice banner */
.air-notice {
    background-color: #FFFFFF;
    border: 1px solid rgba(60, 60, 67, 0.14);
    border-left: 3px solid #0066CC;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 12.5px;
    color: #1C1C1E;
}

/* QR frame */
.air-qr-frame {
    background-color: #FFFFFF;
    border: 1px solid rgba(60, 60, 67, 0.16);
    border-radius: 14px;
    padding: 14px;
}

/* Crisp opaque toast pill */
toast {
    background-color: #1C1C1E;
    color: #F5F5F7;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 999px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28);
}

window.air-window.air-dark toast {
    background-color: #3A3A3C;
    color: #F5F5F7;
    border: 1px solid rgba(255, 255, 255, 0.18);
}

/* Speed Test metric tiles */
.air-stat-tile {
    background-color: #F2F2F7;
    border: 1px solid rgba(60, 60, 67, 0.14);
    border-radius: 10px;
    padding: 10px 8px;
}

.air-stat-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #5A5A5E;
}

.air-stat-value {
    font-size: 16px;
    font-weight: 700;
    color: #1C1C1E;
    font-feature-settings: "tnum";
}

window.air-window.air-dark .air-stat-tile {
    background-color: #1C1C1E;
    border-color: rgba(255, 255, 255, 0.10);
}

window.air-window.air-dark .air-stat-label {
    color: #AEAEB2;
}

window.air-window.air-dark .air-stat-value {
    color: #F5F5F7;
}

/* Elegant bottom copyright bar */
.air-footer {
    border-top: 1px solid rgba(60, 60, 67, 0.12);
    padding: 8px 16px;
}

.air-footer-text {
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.02em;
    color: #5A5A5E;
}

window.air-window.air-dark .air-footer {
    border-top-color: rgba(255, 255, 255, 0.09);
}

window.air-window.air-dark .air-footer-text {
    color: #AEAEB2;
}

/* ── Dark Theme Override ─────────────────────────────────────────────────── */
window.air-window.air-dark {
    background-color: #1C1C1E;
    color: #F5F5F7;
}

window.air-window.air-dark .air-headerbar {
    background-color: #1C1C1E;
    border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}

window.air-window.air-dark .air-segmented {
    background-color: #2C2C2E;
}

window.air-window.air-dark .air-segmented button {
    color: #AEAEB2;
}

window.air-window.air-dark .air-segmented button:hover {
    color: #F5F5F7;
}

window.air-window.air-dark .air-segmented button.active-seg {
    background-color: #3A3A3C;
    color: #F5F5F7;
}

window.air-window.air-dark .air-card,
window.air-window.air-dark .air-card-padded {
    background-color: #2C2C2E;
    border: 1px solid rgba(255, 255, 255, 0.10);
}

window.air-window.air-dark .air-section-title,
window.air-window.air-dark .air-section-footer,
window.air-window.air-dark .air-subtitle,
window.air-window.air-dark .air-value,
window.air-window.air-dark .air-bridge-kicker {
    color: #AEAEB2;
}

window.air-window.air-dark .air-hero-title,
window.air-window.air-dark .air-row-title,
window.air-window.air-dark .air-mono,
window.air-window.air-dark .air-bridge-name {
    color: #F5F5F7;
}

window.air-window.air-dark .air-divider {
    background-color: rgba(255, 255, 255, 0.10);
}

window.air-window.air-dark .air-icon-badge {
    background-color: #3A3A3C;
    color: #F5F5F7;
}

window.air-window.air-dark .air-icon-badge.live {
    background-color: #1F7A38;
    color: #FFFFFF;
}

window.air-window.air-dark .air-pill-live {
    background-color: #1A3322;
    color: #6EE787;
}

window.air-window.air-dark .air-pill-off {
    background-color: #3A3A3C;
    color: #AEAEB2;
}

window.air-window.air-dark .air-pill-accent {
    background-color: #1A2D42;
    color: #64B5FF;
}

window.air-window.air-dark .air-bridge-node {
    background-color: #1C1C1E;
    border: 1px solid rgba(255, 255, 255, 0.10);
}

window.air-window.air-dark .air-bridge-band {
    color: #64B5FF;
}

window.air-window.air-dark .air-btn-secondary {
    background-color: #3A3A3C;
    color: #F5F5F7;
}

window.air-window.air-dark .air-btn-secondary:hover {
    background-color: #48484A;
}

window.air-window.air-dark .air-btn-danger {
    color: #FF7B72;
    border-color: rgba(255, 123, 114, 0.40);
}

window.air-window.air-dark .air-notice {
    background-color: #2C2C2E;
    border-color: rgba(255, 255, 255, 0.10);
    border-left-color: #64B5FF;
    color: #F5F5F7;
}

window.air-window.air-dark button:focus-visible,
window.air-window.air-dark switch:focus-visible,
window.air-window.air-dark entry:focus-visible,
window.air-window.air-dark dropdown:focus-visible {
    outline: 2px solid #64B5FF;
    outline-offset: 2px;
}
"""


def install_css() -> Gtk.CssProvider:
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS)
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
    return provider
