# MintSpot

[English](README.md) | Bahasa Indonesia

MintSpot adalah aplikasi desktop mandiri untuk Linux Mint (GTK4 + Libadwaita) yang menjaga laptop tetap terhubung ke jaringan Wi-Fi 2.4 GHz sambil memancarkan hotspot 5 GHz melalui Wi-Fi Direct (`P2P-GO`). Aplikasi ini dibuat untuk adaptor Wi-Fi dua kanal agar perangkat 5 GHz seperti iPhone dapat berbagi koneksi laptop tanpa pembungkus hotspot eksternal.

## Fitur utama

- Menjalankan mesin mandiri (`mintspot-engine`) yang berkomunikasi langsung dengan `wpa_supplicant` (D-Bus atau control socket), `dnsmasq`, dan tabel `nftables` terisolasi (`table inet mintspot`), lengkap dengan rollback otomatis saat gagal serta fallback ke NetworkManager (`nmcli`).
- Menyediakan saklar preset **Jembatan 5 GHz iPhone** yang mengunci `method=p2p`, `band=a`, dan pemilihan kanal non-DFS otomatis (`36`, `40`, `44`, `48`, `149`, dan seterusnya).
- Mengganti server DNS hotspot secara langsung antara Cloudflare (`1.1.1.1`), AdGuard DNS (`94.140.14.14` untuk pemblokiran iklan dan pelacak pihak ketiga di tingkat jaringan), dan Google DNS (`8.8.8.8`).
- Memantau perangkat terhubung lengkap dengan nama host, IP, alamat MAC, kekuatan sinyal (`dBm`), grafik trafik unduh/unggah secara langsung, ubah nama perangkat, batas kecepatan (`5`, `10`, atau `25 Mbps` lewat `nftables`), serta tombol jeda/lanjutkan internet.
- Menyertakan tes kecepatan uplink bawaan (ping, unduh, dan unggah melalui Cloudflare), deteksi server dev lokal (`ss -tlnH`) dengan kode QR Safari, serta lembar kode QR Wi-Fi siap pindai.
- Mendukung tema Terang dan Gelap, pergantian bahasa Inggris dan Bahasa Indonesia secara langsung (`EN` / `ID`), ikon system tray `StatusNotifierItem`, mati otomatis saat idle, pemulihan otomatis (watchdog), autostart systemd saat boot, dan hook pemulihan setelah suspend/wake.

## Persyaratan

- Linux Mint (atau distro berbasis Debian/Ubuntu lain) dengan GTK 4 dan Libadwaita
- Adaptor Wi-Fi yang mendukung kombinasi `managed` + `P2P-GO` pada dua kanal terpisah (`#channels <= 2`) untuk mode jembatan 5 GHz; adaptor kanal tunggal tetap dapat menggunakan mode fallback `nmcli`
- Paket sistem yang dibutuhkan:

```bash
sudo apt update
sudo apt install -y \
  python3 python3-gi python3-cairo python3-qrcode \
  gir1.2-gtk-4.0 gir1.2-adw-1 \
  dnsmasq-base iw nftables wpasupplicant policykit-1
```

## Instalasi dan cara menjalankan

Klon repositori ini lalu jalankan aplikasi desktopnya:

```bash
git clone https://github.com/gunturaa/mintspot.git
cd mintspot
chmod +x mintspot-app mintspot-engine
./mintspot-app
```

Anda dapat mengecek dukungan Wi-Fi Direct 5 GHz pada adaptor Wi-Fi sebelum memulai:

```bash
./mintspot-engine detect
```

### Pengaturan bahasa

Saat pertama kali dijalankan, MintSpot otomatis membaca bahasa sistem (locale `id*` langsung memakai Bahasa Indonesia; locale lain memakai English). Anda dapat berganti antara **English** dan **Bahasa Indonesia** kapan saja lewat tombol `EN` / `ID` di header bar atau lewat **Pengaturan > Sistem > Bahasa**. Pilihan bahasa disimpan di `~/.config/mintspot/ui.json` tanpa perlu izin root.

### Integrasi sistem opsional

1. **Pintasan menu aplikasi** (sesuaikan nilai `Exec=` di `mintspot.desktop` dengan lokasi folder klon Anda):

```bash
mkdir -p ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
cp assets/mintspot.svg ~/.local/share/icons/hicolor/scalable/apps/mintspot.svg
cp mintspot.desktop ~/.local/share/applications/mintspot.desktop
```

2. **Kebijakan Polkit khusus** (sesuaikan nilai `org.freedesktop.policykit.exec.path` di dalam `assets/id.gunturaa.mintspot.policy` jika lokasi folder bukan `~/Documents/mintspot`):

```bash
sudo cp assets/id.gunturaa.mintspot.policy /usr/share/polkit-1/actions/
```

3. **Aktifkan ulang otomatis setelah suspend/wake** (sesuaikan `ENGINE=` di `assets/mintspot-sleep` bila perlu):

```bash
sudo cp assets/mintspot-sleep /lib/systemd/system-sleep/mintspot
sudo chmod +x /lib/systemd/system-sleep/mintspot
```

## Referensi CLI (`mintspot-engine`)

Perintah yang mengubah jaringan memerlukan `sudo` atau `pkexec`.

| Perintah | Keterangan |
| --- | --- |
| `./mintspot-engine status` | Menampilkan status hotspot, konfigurasi, antarmuka, dan perangkat terhubung dalam format JSON |
| `./mintspot-engine detect` | Memeriksa chipset Wi-Fi, driver, dan dukungan multi-kanal `P2P-GO` |
| `sudo ./mintspot-engine start [--method p2p\|auto\|nmcli]` | Menyalakan hotspot |
| `sudo ./mintspot-engine stop` | Mematikan hotspot dan menghapus aturan `nftables` MintSpot |
| `sudo ./mintspot-engine config --set key=value` | Mengubah `ssid`, `band`, `method`, `channel`, `hidden`, `interface`, `dns_mode`, atau `idle_off_minutes` (tambahkan `--password-stdin` untuk mengganti kata sandi) |
| `sudo ./mintspot-engine block <mac>` / `unblock <mac>` | Menjeda atau melanjutkan akses internet perangkat |
| `sudo ./mintspot-engine limit <mac> <mbps>` | Membatasi kecepatan perangkat (`0` untuk menghapus batas) |
| `sudo ./mintspot-engine rename <mac> "<nama>"` | Menyimpan nama panggilan untuk perangkat |
| `sudo ./mintspot-engine enable` / `disable` | Mengaktifkan atau mematikan autostart `mintspot.service` saat boot |

## Pintasan papan ketik

| Pintasan | Fungsi |
| --- | --- |
| `Ctrl+1` | Membuka tab Hotspot |
| `Ctrl+2` | Membuka tab Perangkat |
| `Ctrl+3` | Membuka tab Pengaturan |
| `Ctrl+R` | Memuat ulang status dan daftar perangkat |
| `Ctrl+Q` | Keluar dari MintSpot |
| `Esc` | Menutup dialog QR atau dialog ubah nama |

## Struktur proyek

```text
mintspot/
├── mintspot-app                 # Pembungkus peluncur aplikasi desktop
├── mintspot-engine              # Pembungkus CLI mesin hotspot
├── mintspot.desktop             # Entri aplikasi Freedesktop
├── DESIGN.md                    # Panduan palet warna dan desain antarmuka
├── assets/                      # Ikon aplikasi, ikon tray, kebijakan Polkit, hook sleep
└── mintspot/
    ├── __main__.py              # Titik masuk aplikasi GTK4 / Libadwaita
    ├── window.py                # Jendela utama (tab Hotspot, Perangkat, Pengaturan)
    ├── i18n.py                  # Kamus terjemahan Inggris / Indonesia dan penyimpanan preferensi
    ├── backend.py               # Klien Polkit/pkexec untuk memanggil mintspot-engine
    ├── engine.py                # Mesin mandiri P2P-GO, dnsmasq, dan nftables
    ├── hardware.py              # Deteksi kapabilitas adaptor lewat iw dan sysfs
    ├── wpa_p2p.py               # Jembatan P2P wpa_supplicant lewat D-Bus dan control socket
    ├── tray.py                  # Ikon system tray StatusNotifierItem dan DBusMenu
    ├── graph.py                 # Grafik trafik langsung berbasis Cairo
    ├── qr_dialog.py             # Lembar kode QR kredensial Wi-Fi
    ├── dev_preview.py           # Detektor server dev lokal dan kode QR Safari
    ├── speedtest.py             # Tes kecepatan ping, unduh, dan unggah uplink
    ├── config.py                # Penyimpanan konfigurasi /etc/mintspot dan state /run/mintspot
    └── style.py                 # Stylesheet GTK4 tema Terang dan Gelap
```

## Catatan AdGuard DNS di Safari iPhone

Saat memakai mode **AdGuard DNS**, Safari di iOS dapat melewati DNS hotspot jika fitur **Limit IP Address Tracking (Batasi Pelacakan Alamat IP)** atau **iCloud Private Relay** aktif pada jaringan tersebut. Agar Safari memakai DNS MintSpot, buka **Pengaturan > Wi-Fi > ikon (i) pada nama hotspot Anda**, matikan **Batasi Pelacakan Alamat IP**, lalu pastikan **Konfigurasi DNS** disetel ke **Otomatis**. Perlu dicatat bahwa filter berbasis DNS memblokir domain iklan dan pelacak pihak ketiga, sedangkan iklan first-party atau skrip pop-under inline di halaman streaming tetap memerlukan ekstensi pemblokir konten di Safari.
