# NETWATCH — Terminal Pemantau Jaringan Kantor

Dashboard bergaya "secure terminal" untuk memantau perangkat di jaringan kantor:
cukup masukkan **IP address** perangkat untuk melihat pemakaian bandwidth, situs yang
dibuka, koneksi aktif, dan protokol yang dipakai, secara live.

![Dashboard](docs/dashboard.png)

## Apa yang bisa dilihat

| Data | Sumber | Keterangan |
|---|---|---|
| Upload / download per perangkat, grafik 120 detik | Semua paket IP | Akurat |
| **Situs yang dibuka (domain)** | TLS SNI, DNS query, HTTP Host | Contoh: `www.youtube.com`, `mail.google.com` |
| URL lengkap | HTTP biasa (`http://`) saja | Situs HTTPS hanya terlihat domainnya; isi halaman & path terenkripsi |
| Koneksi (IP:port tujuan, layanan, volume) | Header TCP/UDP | Dipetakan ke domain lewat jawaban DNS |
| Protokol (HTTPS, QUIC, DNS, SSH, RDP, VPN…) | Port | |
| MAC address, hostname | Ethernet, DHCP, reverse DNS | |
| Log intercept real-time | Semua di atas | |

Fitur lain: daftar semua aset di jaringan, export CSV riwayat situs per perangkat,
login operator (sesi tidak disimpan, kunci 5 menit setelah 5x gagal).

## Syarat penting: posisi komputer pemantau

Aplikasi ini **hanya bisa melihat lalu lintas yang benar-benar melewati kartu jaringan
komputer tempat ia berjalan**. Di jaringan switch biasa, PC biasa hanya melihat trafiknya
sendiri. Pilih salah satu:

1. **Port mirroring / SPAN** (disarankan) — di managed switch, mirror port uplink ke router
   ke port tempat komputer NETWATCH dicolok.
2. **Jalankan di gateway** — mini PC Linux yang menjadi router/gateway kantor.
3. **Router yang bisa mirror trafik** — misalnya MikroTik *Packet Sniffer → streaming* /
   *mangle action=sniff-tzsp* ke komputer NETWATCH, atau OpenWrt dengan port mirror.

> Bila browser memakai **DNS-over-HTTPS** atau **VPN**, domain via DNS tidak terlihat
> (SNI biasanya masih terlihat, kecuali VPN). Matikan DoH via kebijakan browser/GPO
> dan blokir VPN pribadi bila ingin data lengkap.

## Aplikasi Windows (NETWATCH.exe) — paling bersih

Satu file `NETWATCH.exe` dengan ikon sendiri, **tanpa jendela console dan tanpa logo Python**,
tidak perlu install Python. Otomatis meminta izin Administrator saat dibuka.

1. Install [Npcap](https://npcap.com) (centang *WinPcap API-compatible mode*).
2. Install NETWATCH — buka PowerShell, jalankan sekali:
   ```powershell
   irm https://raw.githubusercontent.com/assyaref/NETWATCH/main/install.ps1 | iex
   ```
   NETWATCH.exe dipasang di `C:\Program Files\NETWATCH`, plus shortcut Desktop & Start Menu.
3. Buka terminal baru, lalu:
   - **`netwatch`** → membuka aplikasi
   - **`netwatch-update`** → memperbarui ke versi terbaru (otomatis menutup NETWATCH yang
     sedang berjalan, mengunduh, mengganti). Versi aktif terlihat di baris atas dashboard.

Setiap push ke `main` otomatis membangun dan merilis versi baru (`v1.0.N`) di **Releases**.

Build sendiri dari source: double-click `build_windows.bat` → hasil di `dist\NETWATCH.exe`.

## Instalasi dari source (Windows)

1. Install **Python 3.13** (`winget install -e --id Python.Python.3.13`) dan [Npcap](https://npcap.com)
   (centang *WinPcap API-compatible mode*).
2. Sekali saja, di folder ini (memasang perintah `netwatch`):
   ```powershell
   py -3.13 -m pip install -e ".[window]"
   ```
3. Ketik **`netwatch`** di CMD/PowerShell mana pun → izinkan Administrator (UAC) → jendela
   NETWATCH terbuka. Alternatif: double-click `NETWATCH.bat`.

Jika muncul `'netwatch' is not recognized`, folder Scripts Python belum ada di PATH. Jalankan
sekali di PowerShell, lalu buka terminal baru:
```powershell
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";" + (py -3.13 -c "import sysconfig; print(sysconfig.get_path('scripts'))"), "User")
```
Karena dipasang dengan `-e`, cukup `git pull` untuk update (tanpa install ulang).

Linux/macOS: `pip install -e .` lalu `sudo netwatch`.

## Semua diatur dari aplikasi

![Settings](docs/settings.png)

- **Login default: `admin` / `admin123`.** Selama password default masih dipakai, dashboard
  menampilkan peringatan dengan tombol **CHANGE PASSPHRASE**. Gantilah setelah login pertama.
- Ikon **⚙ (Settings)** di kanan atas:
  - **Mode**: LIVE CAPTURE atau DEMO / SIMULATION
  - **Network interface**: pilih dari daftar adapter (Wi-Fi, Ethernet, …) beserta IP-nya
  - **Office subnets**: tambah/hapus, atau **AUTO-DETECT** dari interface terpilih
  - **APPLY & RESTART CAPTURE**: langsung berlaku, tanpa restart aplikasi
  - Ganti Agent ID / passphrase, dan hapus semua data yang terkumpul
- Jika capture gagal (bukan Administrator, Npcap belum terpasang, interface salah), muncul
  peringatan merah dengan tombol **OPEN SETTINGS**.

Pengaturan disimpan di `%USERPROFILE%\.netwatch\config.json` (passphrase disimpan sebagai
hash PBKDF2). Lupa passphrase? Hapus file itu; login kembali ke `admin` / `admin123`.

**Jendela aplikasi**: NETWATCH membuka jendela native (pywebview/WebView2). Bila pywebview
tidak tersedia, otomatis memakai jendela Edge app mode (tanpa tab & address bar).
Menutup jendela = menghentikan NETWATCH.

### Opsi command line (opsional)

| Opsi | Fungsi |
|---|---|
| `--demo` | Mulai dalam mode demo (sementara, tidak disimpan) |
| `--iface NAME` / `--subnet CIDR` | Timpa pengaturan untuk sesi ini |
| `--no-window` | Jalankan server saja, buka `http://127.0.0.1:8787` sendiri |
| `--host` / `--port` | Alamat dashboard (default `127.0.0.1:8787`) |
| `--no-elevate` | Windows: jangan minta hak Administrator |

## Catatan hukum & etika

Memantau trafik karyawan menyentuh data pribadi. Di Indonesia, UU No. 27/2022 tentang
Pelindungan Data Pribadi berlaku. Pastikan ada **kebijakan tertulis penggunaan
jaringan kantor** yang diketahui karyawan, pantau hanya perangkat/jaringan milik
perusahaan, batasi akses dashboard ke admin yang berwenang, dan jangan simpan data lebih
lama dari yang diperlukan (NETWATCH menyimpan data di memori saja; hilang saat restart).

## Struktur

```
netwatch/
  netwatch/server.py    # HTTP server, API JSON, login
  netwatch/config.py    # pengaturan tersimpan + deteksi interface
  netwatch/engine.py    # start/stop capture sesuai pengaturan
  netwatch/capture.py   # sniffing (scapy): DNS, TLS SNI, HTTP, DHCP
  netwatch/store.py     # statistik per perangkat (in-memory)
  netwatch/demo.py      # generator trafik simulasi
  netwatch/window.py    # jendela desktop (pywebview / Edge app mode)
  NETWATCH.bat          # launcher Windows dari source
  build_windows.bat     # build NETWATCH.exe (PyInstaller)
  assets/               # ikon aplikasi
  netwatch/static/      # UI (HTML/CSS/JS tanpa framework)
```
