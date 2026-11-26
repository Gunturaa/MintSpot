# MintSpot

English | [Bahasa Indonesia](README.id.md)

MintSpot is a standalone Linux Mint desktop utility (GTK4 + Libadwaita) that keeps your laptop connected to a 2.4 GHz Wi-Fi network while broadcasting a 5 GHz hotspot over Wi-Fi Direct (`P2P-GO`). It is built for dual-channel Wi-Fi adapters so 5 GHz devices such as iPhones can share your laptop's internet without external hotspot wrappers.

## What it does

- Runs a standalone engine (`mintspot-engine`) that talks directly to `wpa_supplicant` (D-Bus or control socket), `dnsmasq`, and an isolated `nftables` table (`table inet mintspot`), with automatic rollback on failure and fallback to NetworkManager (`nmcli`).
- Includes a one-switch **iPhone 5 GHz Bridge** preset that locks `method=p2p`, `band=a`, and automatic non-DFS channel selection (`36`, `40`, `44`, `48`, `149`, and above).
- Switches hotspot DNS upstream live between Cloudflare (`1.1.1.1`), AdGuard DNS (`94.140.14.14` for network-level third-party ad and tracker blocking), and Google DNS (`8.8.8.8`).
- Shows connected devices with hostname, IP, MAC address, signal strength (`dBm`), a live download/upload throughput graph, per-device renaming, speed caps (`5`, `10`, or `25 Mbps` via `nftables`), and pause/resume controls.
- Provides a built-in uplink speed test (ping, download, and upload via Cloudflare), local dev server detection (`ss -tlnH`) with scannable Safari QR codes, and a Wi-Fi QR share sheet.
- Ships with Light and Dark themes, live English and Indonesian UI switching (`EN` / `ID`), a `StatusNotifierItem` system tray icon, idle auto-off, a watchdog auto-heal loop, optional systemd boot autostart, and a sleep/wake resume hook.

## Requirements

- Linux Mint (or another Debian/Ubuntu-based distribution) with GTK 4 and Libadwaita
- A Wi-Fi adapter that supports concurrent `managed` + `P2P-GO` on separate channels (`#channels <= 2`) for 5 GHz bridge mode; single-channel adapters can still run through the `nmcli` fallback
- System packages:

```bash
sudo apt update
sudo apt install -y \
  python3 python3-gi python3-cairo python3-qrcode \
  gir1.2-gtk-4.0 gir1.2-adw-1 \
  dnsmasq-base iw nftables wpasupplicant policykit-1
```

## Installation and usage

Clone the repository and launch the desktop app:

```bash
git clone https://github.com/gunturaa/mintspot.git
cd mintspot
chmod +x mintspot-app mintspot-engine
./mintspot-app
```

You can also check whether your Wi-Fi adapter supports 5 GHz Wi-Fi Direct before starting:

```bash
./mintspot-engine detect
```

### Language preference

MintSpot detects your system locale on first launch (`id*` starts in Bahasa Indonesia; all other locales start in English). You can switch between **English** and **Bahasa Indonesia** at any time using the `EN` / `ID` button in the header bar or under **Settings > System > Language**. The choice is stored in `~/.config/mintspot/ui.json` without asking for root privileges.

### Optional system integrations

1. **Desktop launcher** (update `Exec=` in `mintspot.desktop` to match your clone path):

```bash
mkdir -p ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
cp assets/mintspot.svg ~/.local/share/icons/hicolor/scalable/apps/mintspot.svg
cp mintspot.desktop ~/.local/share/applications/mintspot.desktop
```

2. **Branded Polkit policy** (update the `org.freedesktop.policykit.exec.path` value inside `assets/id.gunturaa.mintspot.policy` if you cloned outside `~/Documents/mintspot`):

```bash
sudo cp assets/id.gunturaa.mintspot.policy /usr/share/polkit-1/actions/
```

3. **Auto-resume after suspend/wake** (update `ENGINE=` in `assets/mintspot-sleep` if needed):

```bash
sudo cp assets/mintspot-sleep /lib/systemd/system-sleep/mintspot
sudo chmod +x /lib/systemd/system-sleep/mintspot
```

## CLI reference (`mintspot-engine`)

Privileged commands require `sudo` or `pkexec`.

| Command | Description |
| --- | --- |
| `./mintspot-engine status` | Print hotspot state, config, interfaces, and connected clients as JSON |
| `./mintspot-engine detect` | Probe Wi-Fi chipset, driver, and `P2P-GO` multi-channel support |
| `sudo ./mintspot-engine start [--method p2p\|auto\|nmcli]` | Start the hotspot |
| `sudo ./mintspot-engine stop` | Stop the hotspot and remove MintSpot `nftables` rules |
| `sudo ./mintspot-engine config --set key=value` | Update `ssid`, `band`, `method`, `channel`, `hidden`, `interface`, `dns_mode`, or `idle_off_minutes` (add `--password-stdin` to change password) |
| `sudo ./mintspot-engine block <mac>` / `unblock <mac>` | Pause or resume internet access for a client |
| `sudo ./mintspot-engine limit <mac> <mbps>` | Cap a client's speed (`0` removes the cap) |
| `sudo ./mintspot-engine rename <mac> "<name>"` | Save a friendly name for a client |
| `sudo ./mintspot-engine enable` / `disable` | Enable or disable `mintspot.service` autostart on boot |

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+1` | Open the Hotspot tab |
| `Ctrl+2` | Open the Devices tab |
| `Ctrl+3` | Open the Settings tab |
| `Ctrl+R` | Refresh status and connected devices |
| `Ctrl+Q` | Quit MintSpot |
| `Esc` | Close active QR or rename dialogs |

## Project structure

```text
mintspot/
├── mintspot-app                 # Desktop launcher wrapper
├── mintspot-engine              # Privileged engine CLI wrapper
├── mintspot.desktop             # Freedesktop application entry
├── DESIGN.md                    # Visual palette and UI guidelines
├── assets/                      # App icons, tray icons, Polkit policy, sleep hook
└── mintspot/
    ├── __main__.py              # GTK4 / Libadwaita application entry point
    ├── window.py                # Main window (Hotspot, Devices, Settings tabs)
    ├── i18n.py                  # English / Indonesian translations and persistence
    ├── backend.py               # Polkit/pkexec client wrapper for mintspot-engine
    ├── engine.py                # Standalone P2P-GO, dnsmasq, and nftables engine
    ├── hardware.py              # iw and sysfs adapter capability discovery
    ├── wpa_p2p.py               # wpa_supplicant D-Bus and control-socket P2P bridge
    ├── tray.py                  # StatusNotifierItem system tray and DBusMenu
    ├── graph.py                 # Cairo live throughput graph
    ├── qr_dialog.py             # Wi-Fi credentials QR share sheet
    ├── dev_preview.py           # Local dev server detector and Safari QR sheet
    ├── speedtest.py             # Uplink ping, download, and upload speed test
    ├── config.py                # /etc/mintspot and /run/mintspot state storage
    └── style.py                 # Light and Dark GTK4 stylesheet
```

## Notes on AdGuard DNS with iPhone Safari

When using **AdGuard DNS** mode, iOS Safari may bypass hotspot DNS if **Limit IP Address Tracking** or **iCloud Private Relay** is active for the network. To make Safari use MintSpot's DNS on your iPhone, open **Settings > Wi-Fi > (i) next to your hotspot SSID**, turn off **Limit IP Address Tracking**, and confirm **Configure DNS** is set to **Automatic**. Note that DNS-based filtering blocks third-party ad and tracker domains, while first-party ads or inline pop-under scripts inside streaming pages still require a Safari content blocker.
