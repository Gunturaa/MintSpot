"""Bilingual (English / Bahasa Indonesia) UI localization for MintSpot."""

from __future__ import annotations

import json
import locale
import os
from pathlib import Path
from typing import Dict, List, Tuple

SUPPORTED_LANGUAGES: List[Tuple[str, str]] = [
    ("en", "English"),
    ("id", "Bahasa Indonesia"),
]

UI_PREFS_PATH = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "mintspot" / "ui.json"

_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # Navigation & Header
        "tab_hotspot": "Hotspot",
        "tab_devices": "Devices",
        "tab_settings": "Settings",
        "tooltip_refresh": "Refresh (Ctrl+R)",
        "tooltip_switch_light": "Switch to Light Mode",
        "tooltip_switch_dark": "Switch to Dark Mode",
        "tooltip_switch_lang": "Switch language to Bahasa Indonesia",
        "lang_badge": "EN",
        "footer_credit": "© 2026 MintSpot · 5 GHz Wi-Fi Direct Bridge",

        # Master Card
        "master_title": "Personal Hotspot",
        "status_off": "Off",
        "status_live": "{band} Live",
        "checking_hardware": "Checking Wi-Fi hardware...",
        "engine_missing": "mintspot-engine not found or not executable.",
        "broadcasting_on": "Broadcasting \"{ssid}\" on channel {channel}",
        "ready_to_bridge": "Ready to bridge {ssid}",
        "hotspot_turned_off": "Hotspot is turned off",

        # Signal Bridge Card
        "section_bridge": "5 GHz Bridge",
        "uplink_kicker": "UPLINK WI-FI",
        "not_connected": "Not connected",
        "no_wifi": "No Wi-Fi",
        "disconnected": "Disconnected",
        "connected": "Connected",
        "output_kicker": "HOTSPOT OUTPUT",
        "method_wifi_direct": "Wi-Fi Direct",
        "iphone_bridge_title": "iPhone 5 GHz Bridge",
        "iphone_bridge_desc": "Force 5 GHz via Wi-Fi Direct while staying on 2.4 GHz Wi-Fi",

        # Network Card
        "section_network": "Network",
        "network_name": "Network Name",
        "tooltip_copy_ssid": "Copy network name",
        "wifi_pw_qr": "Wi-Fi Password & QR",
        "scan_iphone_camera": "Scan with iPhone Camera to join",
        "show_qr": "Show QR",
        "band_channel": "Band & Channel",
        "band_configured": "{band} (configured)",
        "connected_devices": "Connected Devices",
        "tooltip_open_devices": "Open Devices tab",
        "interface": "Interface",
        "inactive": "Inactive",
        "unknown": "Unknown",
        "status_read_error": "Could not read MintSpot status.",

        # Speed Test Card
        "section_speedtest": "Speed Test",
        "uplink_speedtest": "Uplink Speed Test",
        "speedtest_idle": "Test real-time latency, download, and upload",
        "run_test": "Run Test",
        "testing": "Testing...",
        "metric_ping": "PING",
        "metric_download": "DOWNLOAD",
        "metric_upload": "UPLOAD",
        "speedtest_done": "Completed via Cloudflare edge",
        "speedtest_stage_ping": "Measuring ping...",
        "speedtest_stage_download": "Testing download...",
        "speedtest_stage_upload": "Testing upload...",
        "speedtest_failed": "Speed test failed: {error}",

        # Local Dev Preview Card
        "section_dev_preview": "Local Dev Preview",
        "no_dev_server": "No local dev server detected (e.g. npm run dev on :3000). Enter any port below.",
        "port_label": "Port",
        "port_placeholder": "e.g. 3000, 5173, 8080",
        "safari_qr": "Safari QR",
        "invalid_port": "Enter a valid port number (1-65535).",
        "turn_on_hotspot_dev": "Turn on Personal Hotspot first so your iPhone can reach this laptop.",
        "local_server_port": "Local Server :{port}",
        "dev_qr_subtitle": "Scan with iPhone Camera to open your local dev server in Safari over 5 GHz.",

        # Devices Page
        "section_throughput": "Live Throughput",
        "devices_header": "CONNECTED DEVICES ({count})",
        "devices_hotspot_off": "Turn on Personal Hotspot to see connected devices.",
        "devices_empty": "No devices connected yet. Open Wi-Fi on your iPhone or scan the QR code.",
        "device_default_name": "Connected Device",
        "pill_paused": "Paused",
        "pill_cap": "{mbps} Mbps cap",
        "pending_ip": "pending IP",
        "total_traffic": "Total {size}",
        "btn_rename": "Rename",
        "btn_pause": "Pause",
        "btn_resume": "Resume",
        "devices_footer": "Pause and speed limits are enforced directly in MintSpot's isolated nftables firewall (works in 5 GHz Wi-Fi Direct mode).",
        "graph_peak": "Peak {speed}",

        # Rename Dialog
        "rename_title": "Rename Device",
        "rename_hint": "Friendly name for {mac}",
        "rename_placeholder": "e.g. My iPhone",
        "save_name": "Save Name",

        # Settings Page
        "settings_name": "Name",
        "ssid_placeholder": "Hotspot SSID",
        "settings_password": "Password",
        "pw_placeholder": "Leave blank to keep current",
        "btn_generate": "Generate",
        "hidden_network": "Hidden Network",
        "section_radio_privacy": "Radio & Privacy",
        "settings_band": "Band",
        "settings_method": "Method",
        "settings_channel": "Channel",
        "settings_dns": "DNS Server",
        "settings_idle": "Auto-Off when Idle",
        "dns_footer": "AdGuard DNS blocks third-party ads and trackers on connected devices without installing a VPN.",
        "save_settings": "Save Settings",
        "section_system": "System",
        "settings_language": "Language",
        "autostart_boot": "Start Hotspot on Boot",
        "wifi_adapter": "Wi-Fi Adapter",
        "detecting": "Detecting...",
        "unknown_adapter": "Unknown adapter",
        "p2p_ready": "5 GHz P2P ready",
        "single_channel": "Single-channel",

        # Dropdown options
        "band_5ghz": "5 GHz (iPhone / Fast)",
        "band_24ghz": "2.4 GHz (Legacy)",
        "method_p2p": "Wi-Fi Direct (5 GHz Bridge)",
        "method_auto": "Automatic",
        "method_nmcli": "NetworkManager",
        "channel_auto": "Automatic (non-DFS preferred)",
        "channel_num": "Channel {ch}",
        "dns_cloudflare": "Cloudflare (1.1.1.1 · Fast)",
        "dns_adguard": "AdGuard DNS (Ad-Block for iPhone)",
        "dns_google": "Google DNS (8.8.8.8)",
        "idle_never": "Never",
        "idle_minutes": "After {mins} minutes",
        "limit_unlimited": "Unlimited",
        "limit_mbps": "{mbps} Mbps",

        # Toasts & Notifications
        "toast_ssid_copied": "Network name copied.",
        "toast_pw_copied": "Password copied.",
        "toast_url_copied": "Preview URL copied.",
        "toast_set_creds_first": "Set a network name and password in Settings first.",
        "toast_pw_generated": "Generated a new 12-character password. Click Save Settings to apply.",
        "toast_ssid_empty": "Network name cannot be empty.",
        "toast_pw_short": "WPA2 password must be at least 8 characters.",
        "toast_idle_off": "No devices for {mins}m. Turning hotspot off.",
        "toast_lang_switched": "Language switched to English.",
        "notify_watchdog_title": "MintSpot Watchdog",
        "notify_watchdog_body": "Hotspot dropped. Automatically restoring 5 GHz bridge...",
        "notify_new_device_title": "New Device Connected",
        "notify_new_device_body": "{name} joined MintSpot ({ip})",
        "connecting_ip": "connecting...",

        # Runtime bridge notes
        "bridge_note": "Bridging {uplink} ({uplink_band}) -> {ssid} ({out_band}, Ch {ch}){dns_note}.",
        "bridge_note_adguard": " · AdGuard Ad-Block DNS",
        "nmcli_note": "Running via NetworkManager hotspot.",

        # QR Sheets
        "qr_join_title": "Join Wi-Fi",
        "qr_join_hint": "Point your iPhone Camera at this code to join the 5 GHz hotspot.",
        "qr_missing_pkg": "Install python3-qrcode to render a scannable QR code.",
        "qr_network_label": "Network",
        "qr_password_label": "Password",
        "tooltip_copy_field": "Copy {label}",
        "tooltip_copy_url": "Copy URL",
        "url_qr_default_subtitle": "Point your iPhone Camera at this code to open in Safari.",

        # Backend messages
        "err_operation_failed": "Operation failed.",
        "err_no_polkit_agent": "No polkit authentication agent found. Run from a desktop session.",
        "err_auth_cancelled": "Authentication cancelled.",
        "err_not_authorized": "Not authorized.",
        "err_pkexec_missing": "pkexec not found. Install policykit-1.",
        "err_timeout": "Operation timed out.",
        "err_parse_creds": "Could not parse hotspot credentials.",
        "msg_done": "Done.",
        "msg_hotspot_on": "Personal Hotspot is now on.",
        "msg_hotspot_off": "Personal Hotspot turned off.",
        "msg_bridge_enabled": "iPhone 5 GHz Bridge enabled (Wi-Fi Direct, 5 GHz).",
        "msg_bridge_disabled": "Switched back to Automatic hotspot method.",
        "msg_settings_saved": "Hotspot settings saved.",
        "msg_autostart_on": "Autostart on boot enabled.",
        "msg_autostart_off": "Autostart on boot disabled.",
        "msg_device_paused": "Internet paused for device.",
        "msg_device_resumed": "Internet resumed for device.",
        "msg_limit_removed": "Speed limit removed.",
        "msg_limit_set": "Device limited to {mbps} Mbps.",
        "msg_renamed": "Device name updated.",

        # System Tray
        "tray_off_short": "MintSpot · Off",
        "tray_off_status": "MintSpot · Hotspot Off",
        "tray_off_tooltip": "Hotspot is off. Click to open.",
        "tray_click_open": "Click to open MintSpot",
        "tray_device_singular": "{count} device",
        "tray_device_plural": "{count} devices",
        "tray_live_status": "{ssid} · {band} Live ({devices})",
        "tray_live_tooltip": "Broadcasting {band} ({devices})",
        "tray_turn_off": "Turn Hotspot Off",
        "tray_turn_on": "Turn Hotspot On",
        "tray_open": "Open MintSpot",
        "tray_quit": "Quit MintSpot",
    },
    "id": {
        # Navigation & Header
        "tab_hotspot": "Hotspot",
        "tab_devices": "Perangkat",
        "tab_settings": "Pengaturan",
        "tooltip_refresh": "Muat Ulang (Ctrl+R)",
        "tooltip_switch_light": "Ganti ke Mode Terang",
        "tooltip_switch_dark": "Ganti ke Mode Gelap",
        "tooltip_switch_lang": "Ganti bahasa ke English",
        "lang_badge": "ID",
        "footer_credit": "© 2026 MintSpot · Jembatan Wi-Fi Direct 5 GHz",

        # Master Card
        "master_title": "Hotspot Pribadi",
        "status_off": "Mati",
        "status_live": "{band} Aktif",
        "checking_hardware": "Memeriksa perangkat keras Wi-Fi...",
        "engine_missing": "mintspot-engine tidak ditemukan atau tidak dapat dijalankan.",
        "broadcasting_on": "Memancarkan \"{ssid}\" di kanal {channel}",
        "ready_to_bridge": "Siap menjembatani {ssid}",
        "hotspot_turned_off": "Hotspot dimatikan",

        # Signal Bridge Card
        "section_bridge": "Jembatan 5 GHz",
        "uplink_kicker": "WI-FI UPLINK",
        "not_connected": "Tidak terhubung",
        "no_wifi": "Tidak ada Wi-Fi",
        "disconnected": "Terputus",
        "connected": "Terhubung",
        "output_kicker": "OUTPUT HOTSPOT",
        "method_wifi_direct": "Wi-Fi Direct",
        "iphone_bridge_title": "Jembatan 5 GHz iPhone",
        "iphone_bridge_desc": "Paksa 5 GHz lewat Wi-Fi Direct saat laptop tetap terhubung ke Wi-Fi 2.4 GHz",

        # Network Card
        "section_network": "Jaringan",
        "network_name": "Nama Jaringan",
        "tooltip_copy_ssid": "Salin nama jaringan",
        "wifi_pw_qr": "Kata Sandi & QR Wi-Fi",
        "scan_iphone_camera": "Pindai dengan Kamera iPhone untuk terhubung",
        "show_qr": "Tampilkan QR",
        "band_channel": "Pita & Kanal",
        "band_configured": "{band} (terkonfigurasi)",
        "connected_devices": "Perangkat Terhubung",
        "tooltip_open_devices": "Buka tab Perangkat",
        "interface": "Antarmuka",
        "inactive": "Tidak aktif",
        "unknown": "Tidak diketahui",
        "status_read_error": "Gagal membaca status MintSpot.",

        # Speed Test Card
        "section_speedtest": "Tes Kecepatan",
        "uplink_speedtest": "Tes Kecepatan Uplink",
        "speedtest_idle": "Uji latensi, unduhan, dan unggahan secara langsung",
        "run_test": "Mulai Tes",
        "testing": "Menguji...",
        "metric_ping": "PING",
        "metric_download": "UNDUH",
        "metric_upload": "UNGGAH",
        "speedtest_done": "Selesai melalui server Cloudflare",
        "speedtest_stage_ping": "Mengukur ping...",
        "speedtest_stage_download": "Menguji kecepatan unduh...",
        "speedtest_stage_upload": "Menguji kecepatan unggah...",
        "speedtest_failed": "Tes kecepatan gagal: {error}",

        # Local Dev Preview Card
        "section_dev_preview": "Pratinjau Dev Lokal",
        "no_dev_server": "Belum ada server dev lokal terdeteksi (mis. npm run dev di :3000). Masukkan port di bawah.",
        "port_label": "Port",
        "port_placeholder": "mis. 3000, 5173, 8080",
        "safari_qr": "QR Safari",
        "invalid_port": "Masukkan nomor port yang valid (1-65535).",
        "turn_on_hotspot_dev": "Nyalakan Hotspot Pribadi terlebih dahulu agar iPhone bisa menjangkau laptop ini.",
        "local_server_port": "Server Lokal :{port}",
        "dev_qr_subtitle": "Pindai dengan Kamera iPhone untuk membuka server dev lokal di Safari lewat 5 GHz.",

        # Devices Page
        "section_throughput": "Trafik Langsung",
        "devices_header": "PERANGKAT TERHUBUNG ({count})",
        "devices_hotspot_off": "Nyalakan Hotspot Pribadi untuk melihat perangkat yang terhubung.",
        "devices_empty": "Belum ada perangkat terhubung. Buka pengaturan Wi-Fi di iPhone atau pindai kode QR.",
        "device_default_name": "Perangkat Terhubung",
        "pill_paused": "Dijeda",
        "pill_cap": "Batas {mbps} Mbps",
        "pending_ip": "menunggu IP",
        "total_traffic": "Total {size}",
        "btn_rename": "Ubah Nama",
        "btn_pause": "Jeda",
        "btn_resume": "Lanjutkan",
        "devices_footer": "Jeda internet dan batas kecepatan diterapkan langsung di firewall nftables MintSpot (berjalan pada mode Wi-Fi Direct 5 GHz).",
        "graph_peak": "Puncak {speed}",

        # Rename Dialog
        "rename_title": "Ubah Nama Perangkat",
        "rename_hint": "Nama panggilan untuk {mac}",
        "rename_placeholder": "mis. iPhone Saya",
        "save_name": "Simpan Nama",

        # Settings Page
        "settings_name": "Nama",
        "ssid_placeholder": "SSID Hotspot",
        "settings_password": "Kata Sandi",
        "pw_placeholder": "Kosongkan untuk mempertahankan saat ini",
        "btn_generate": "Buat Acak",
        "hidden_network": "Jaringan Tersembunyi",
        "section_radio_privacy": "Radio & Privasi",
        "settings_band": "Pita Frekuensi",
        "settings_method": "Metode",
        "settings_channel": "Kanal",
        "settings_dns": "Server DNS",
        "settings_idle": "Mati Otomatis saat Idle",
        "dns_footer": "AdGuard DNS memblokir iklan dan pelacak pihak ketiga pada perangkat terhubung tanpa perlu memasang VPN.",
        "save_settings": "Simpan Pengaturan",
        "section_system": "Sistem",
        "settings_language": "Bahasa",
        "autostart_boot": "Jalankan Hotspot saat Boot",
        "wifi_adapter": "Adaptor Wi-Fi",
        "detecting": "Mendeteksi...",
        "unknown_adapter": "Adaptor tidak diketahui",
        "p2p_ready": "Mendukung P2P 5 GHz",
        "single_channel": "Kanal tunggal",

        # Dropdown options
        "band_5ghz": "5 GHz (iPhone / Cepat)",
        "band_24ghz": "2.4 GHz (Standar)",
        "method_p2p": "Wi-Fi Direct (Jembatan 5 GHz)",
        "method_auto": "Otomatis",
        "method_nmcli": "NetworkManager",
        "channel_auto": "Otomatis (utamakan non-DFS)",
        "channel_num": "Kanal {ch}",
        "dns_cloudflare": "Cloudflare (1.1.1.1 · Cepat)",
        "dns_adguard": "AdGuard DNS (Blokir Iklan iPhone)",
        "dns_google": "Google DNS (8.8.8.8)",
        "idle_never": "Tidak pernah",
        "idle_minutes": "Setelah {mins} menit",
        "limit_unlimited": "Tanpa batas",
        "limit_mbps": "{mbps} Mbps",

        # Toasts & Notifications
        "toast_ssid_copied": "Nama jaringan disalin.",
        "toast_pw_copied": "Kata sandi disalin.",
        "toast_url_copied": "URL pratinjau disalin.",
        "toast_set_creds_first": "Atur nama jaringan dan kata sandi di Pengaturan terlebih dahulu.",
        "toast_pw_generated": "Kata sandi acak 12 karakter dibuat. Klik Simpan Pengaturan untuk menerapkan.",
        "toast_ssid_empty": "Nama jaringan tidak boleh kosong.",
        "toast_pw_short": "Kata sandi WPA2 minimal 8 karakter.",
        "toast_idle_off": "Tidak ada perangkat selama {mins} menit. Mematikan hotspot.",
        "toast_lang_switched": "Bahasa diganti ke Bahasa Indonesia.",
        "notify_watchdog_title": "MintSpot Watchdog",
        "notify_watchdog_body": "Hotspot terputus. Memulihkan jembatan 5 GHz secara otomatis...",
        "notify_new_device_title": "Perangkat Baru Terhubung",
        "notify_new_device_body": "{name} bergabung ke MintSpot ({ip})",
        "connecting_ip": "menghubungkan...",

        # Runtime bridge notes
        "bridge_note": "Menjembatani {uplink} ({uplink_band}) -> {ssid} ({out_band}, Kanal {ch}){dns_note}.",
        "bridge_note_adguard": " · AdGuard DNS Pemblokir Iklan",
        "nmcli_note": "Berjalan melalui hotspot NetworkManager.",

        # QR Sheets
        "qr_join_title": "Gabung Wi-Fi",
        "qr_join_hint": "Arahkan Kamera iPhone ke kode ini untuk terhubung ke hotspot 5 GHz.",
        "qr_missing_pkg": "Pasang python3-qrcode untuk menampilkan kode QR.",
        "qr_network_label": "Jaringan",
        "qr_password_label": "Kata Sandi",
        "tooltip_copy_field": "Salin {label}",
        "tooltip_copy_url": "Salin URL",
        "url_qr_default_subtitle": "Arahkan Kamera iPhone ke kode ini untuk membuka di Safari.",

        # Backend messages
        "err_operation_failed": "Operasi gagal.",
        "err_no_polkit_agent": "Agen autentikasi polkit tidak ditemukan. Jalankan dari sesi desktop.",
        "err_auth_cancelled": "Autentikasi dibatalkan.",
        "err_not_authorized": "Tidak diizinkan.",
        "err_pkexec_missing": "pkexec tidak ditemukan. Pasang policykit-1.",
        "err_timeout": "Waktu operasi habis.",
        "err_parse_creds": "Gagal membaca kredensial hotspot.",
        "msg_done": "Selesai.",
        "msg_hotspot_on": "Hotspot Pribadi sekarang aktif.",
        "msg_hotspot_off": "Hotspot Pribadi dimatikan.",
        "msg_bridge_enabled": "Jembatan 5 GHz iPhone diaktifkan (Wi-Fi Direct, 5 GHz).",
        "msg_bridge_disabled": "Kembali ke metode hotspot Otomatis.",
        "msg_settings_saved": "Pengaturan hotspot disimpan.",
        "msg_autostart_on": "Jalankan otomatis saat boot diaktifkan.",
        "msg_autostart_off": "Jalankan otomatis saat boot dimatikan.",
        "msg_device_paused": "Akses internet perangkat dijeda.",
        "msg_device_resumed": "Akses internet perangkat dilanjutkan.",
        "msg_limit_removed": "Batas kecepatan dihapus.",
        "msg_limit_set": "Kecepatan perangkat dibatasi ke {mbps} Mbps.",
        "msg_renamed": "Nama perangkat diperbarui.",

        # System Tray
        "tray_off_short": "MintSpot · Mati",
        "tray_off_status": "MintSpot · Hotspot Mati",
        "tray_off_tooltip": "Hotspot mati. Klik untuk membuka.",
        "tray_click_open": "Klik untuk membuka MintSpot",
        "tray_device_singular": "{count} perangkat",
        "tray_device_plural": "{count} perangkat",
        "tray_live_status": "{ssid} · {band} Aktif ({devices})",
        "tray_live_tooltip": "Memancarkan {band} ({devices})",
        "tray_turn_off": "Matikan Hotspot",
        "tray_turn_on": "Nyalakan Hotspot",
        "tray_open": "Buka MintSpot",
        "tray_quit": "Keluar MintSpot",
    },
}


def _detect_system_language() -> str:
    env_lang = os.environ.get("MINTSPOT_LANG") or os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    if not env_lang:
        try:
            env_lang = locale.getlocale()[0] or ""
        except ValueError:
            env_lang = ""
    if env_lang.lower().startswith("id"):
        return "id"
    return "en"


def load_language() -> str:
    if UI_PREFS_PATH.is_file():
        try:
            data = json.loads(UI_PREFS_PATH.read_text(encoding="utf-8"))
            lang = str(data.get("language") or "").lower()
            if lang in _TRANSLATIONS:
                return lang
        except (OSError, ValueError):
            pass
    return _detect_system_language()


def save_language(lang: str) -> str:
    code = lang.lower() if lang.lower() in _TRANSLATIONS else "en"
    try:
        UI_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: Dict[str, object] = {}
        if UI_PREFS_PATH.is_file():
            try:
                raw = json.loads(UI_PREFS_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    existing.update(raw)
            except (OSError, ValueError):
                pass
        existing["language"] = code
        tmp = UI_PREFS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(UI_PREFS_PATH))
    except OSError:
        pass
    return code


_current_language: str = load_language()


def get_language() -> str:
    return _current_language


def set_language(lang: str, persist: bool = True) -> str:
    global _current_language
    code = lang.lower() if lang.lower() in _TRANSLATIONS else "en"
    _current_language = code
    if persist:
        save_language(code)
    return _current_language


def tr(key: str, **kwargs: object) -> str:
    table = _TRANSLATIONS.get(_current_language, _TRANSLATIONS["en"])
    text = table.get(key) or _TRANSLATIONS["en"].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
