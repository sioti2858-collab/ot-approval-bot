<div align="center">

# OT Approval Bot

**Bot Telegram untuk pengajuan lembur (overtime) & overday dengan persetujuan berjenjang dan dokumen PDF otomatis.**

Python 3.10+ · Telegram Bot API · Google Workspace · MIT License

</div>

---

## Apa itu repo ini?

Bot Telegram untuk tim HR & Operasional yang ingin mengelola pengajuan lembur
**tanpa** spread sheet manual dan tanpa bolak-balik chat pribadi.

Karyawan isi form di Telegram → data masuk Google Sheets → pengajuan diteruskan ke
approver sesuai level → setelah disetujui semua level, **PDF dengan tanda tangan
otomatis** dikirim ke HR dan pemohon.

```
Karyawan          Bot Telegram           Approver L1 → L2 → L3          HR & Pemohon
   │ isi form ───▶ validasi ───▶ notifikasi + tombol Setuju/Tolak ───▶ PDF otomatis
   │               Google Sheets  │                                      │
   └──────────────────────────────┴──────────────────────────────────────┴── Telegram
```

---

## Fitur

| Fitur | Penjelasan |
|---|---|
| **Form pengajuan** | Lembur (overtime) dan overday, dengan validasi input di setiap langkah |
| **Persetujuan berjenjang** | Overtime 3 level, overday 2 level. Notifikasi + tombol inline ke tiap approver |
| **Dokumen PDF otomatis** | Formulir resmi dengan logo, rekap data, dan tanda tangan approver yang **hanya** tampil jika sudah menyetujui |
| **Google Sheets** | Semua pengajuan tersimpan otomatis dengan riwayat approval per level |
| **Google Drive** | Opsional: PDF di-upload ke Shared Drive dan link-nya disimpan di Sheet |
| **Anti kirim-ganda** | Tombol tidak bisa diproses dua kali (debounce + pengecekan status) |
| **Panduan otomatis** | Kalau user salah input, bot langsung memberi tahu format yang benar + contoh |
| **Self-approval aman** | Approver boleh menyetujui pengajuannya sendiri (jejaknya tetap tercatat), user biasa tidak |

---

## Mulai Cepat (5 menit)

### 1. Ambil kode

```bash
git clone https://github.com/<USERNAME-ANDA>/ot-approval-bot.git
cd ot-approval-bot
```

### 2. Siapkan Python

Butuh **Python 3.10 atau lebih baru**.

```bash
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux / macOS
pip install -r requirements.txt
```

### 3. Isi konfigurasi

```bash
copy .env.example .env      # Windows
# cp .env.example .env     # Linux / macOS
```

Buka `.env` lalu isi minimal 4 hal ini:

| Isi | Cara mendapatkannya |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Chat **@BotFather** di Telegram → `/newbot` → salin token |
| `GOOGLE_SHEET_ID` | Buat Google Sheet kosong → buka URL → ambil bagian `/d/<ID>/edit` |
| `APPROVER_1_USER_ID` … `HR_USER_ID` | Chat **@userinfobot** di Telegram → dia balas ID Anda |
| `COMPANY_NAME` | Nama perusahaan, dicetak di header PDF |

> **Catatan tanda tangan:** folder `png/` hanya berisi file *placeholder*. Ganti dengan
> tanda tangan asli Anda (simpan di folder `local_assets/`, sudah masuk `.gitignore`),
> lalu arahkan `APPROVER_1_ESIGN` dan seterusnya ke file tersebut.

### 4. Setup Google Service Account

1. Buka [Google Cloud Console](https://console.cloud.google.com/) → buat project baru
2. Aktifkan **Google Sheets API** dan **Google Drive API**
3. **IAM & Admin → Service Accounts** → buat service account → buat **JSON key**
4. Simpan hasilnya sebagai `credentials.json` di root project
5. **Share** Google Sheet dan folder Drive ke email service account
   (emailnya ada di file JSON, field `client_email`)

### 5. Jalankan

```bash
python main.py
```

Kalau muncul `BOT STARTED SUCCESSFULLY!` — selesai. Buka bot di Telegram, kirim `/start`.

<details>
<summary><b>Cara cepat di Windows (tanpa terminal)</b></summary>

Klik dua kali `start_bot.bat`. Untuk monitoring log: `monitor_bot.bat`.
Lihat statistik: `stats_bot.bat`.

</details>

---

## Konfigurasi

Semua konfigurasi ada di `.env` (lihat `.env.example` untuk daftar lengkap).

| Variabel | Default | Fungsi |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | – | Token bot dari @BotFather (**wajib**) |
| `GOOGLE_SHEET_ID` | – | ID Sheet tujuan (**wajib**) |
| `GOOGLE_DRIVE_FOLDER_ID` | – | ID folder Drive (opsional) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | `credentials.json` | Lokasi file kredensial |
| `COMPANY_NAME` | `PT. Nama Perusahaan` | Header PDF |
| `LOGO_PATH` | `png/logo.png` | Logo di header PDF |
| `APPROVER_1..3_USER_ID` | – | ID Telegram approver per level |
| `APPROVER_1..3_NAME` / `_TITLE` | `Approver 1` dst. | Nama & jabatan di PDF |
| `APPROVER_1..3_ESIGN` | `png/esign_approver_N.png` | File tanda tangan (PNG) |
| `HR_USER_ID` | – | Penerima notifikasi & dokumen |
| `MAX_FUTURE_DAYS` | `30` | Maksimal tanggal ke depan |
| `MAX_PAST_DAYS` | `14` | Batas pengajuan lampiran |
| `BUTTON_DEBOUNCE_SECONDS` | `5` | Jeda anti double-tap |
| `DRIVE_UPLOAD_ENABLED` | `false` | Upload PDF ke Drive |
| `DRIVE_SHARE_MODE` | `link` | `link` atau `restricted` |
| `EXTRA_DOCUMENT_RECIPIENT_USER_IDS` | kosong | Penerima tambahan dokumen |
| `ALLOW_APPROVER_SELF_APPROVAL` | `true` | Approver boleh approve pengajuannya sendiri |
| `ALLOW_SELF_APPROVAL` | `false` | Semua orang boleh approve sendiri (hanya uji coba) |

---

## Struktur Proyek

```
ot-approval-bot/
├── main.py               # Entry point bot (long polling)
├── monitor.py            # Monitor log & statistik
├── config.py             # Semua konfigurasi (dibaca dari .env)
├── .env.example          # Template konfigurasi
├── bot/
│   ├── handlers.py       # Logika utama: menu, callback, input user
│   ├── keyboards.py      # Definisi tombol inline
│   ├── guides.py         # Teks panduan otomatis
│   └── states.py         # State machine percakapan
├── models/
│   └── ot_request.py     # Model data pengajuan
├── services/
│   ├── sheets.py         # Integrasi Google Sheets
│   ├── drive.py          # Integrasi Google Drive
│   ├── pdf.py            # Pembuatan PDF
│   └── delivery.py       # Pengiriman dokumen (pembatas privasi)
├── png/                  # Logo & tanda tangan (isi repo = placeholder)
├── pdfs/                 # Output PDF (di-gitignore)
├── logs/                 # Log harian (di-gitignore)
└── tools/                # Skrip uji & setup sheet
```

---

## Format Google Sheets

| Kolom | Isi |
|---|---|
| A | No. (ID) |
| B | Tanggal submit |
| C | User ID (Telegram) |
| D | Tipe (`overtime` / `overday`) |
| E | Nama |
| F | Dept/Section |
| G | Tanggal OT / Overday |
| H | Jam mulai |
| I | Jam selesai |
| J | Total jam |
| K | Alasan |
| L | Status |
| M | Riwayat approval |
| N | Tanggal selesai overday |
| O | URL PDF |

> Header kolom N dan O **tidak** dibuat otomatis (sheet dipakai bersama tim lain).
> Tambahkan manual di baris 1: `N1` = `Tanggal Selesai Overday`, `O1` = `PDF URL`.
> Alternatif: jalankan `python tools/setup_sheet_columns.py`.

**Alur status:** `draft` → `submitted` → `pending_approval_1` → `pending_approval_2` →
`pending_approval_3` → `approved` / `rejected`

---

## Menjalankan Uji

Semua uji berjalan lokal tanpa koneksi Telegram:

```bash
python tools/test_guides.py       # panduan perintah
python tools/test_idempotency.py  # anti double-tap & batas tanggal
python tools/test_overday_flow.py # alur overday
python tools/test_flow.py         # alur overtime + pesan error
```

---

## Menjalankan 24/7 (Gratis)

| Opsi | Gratis? | Catatan |
|---|---|---|
| **PC/laptop sendiri** | ✅ | Paling stabil. Pakai `start_bot.bat` + Windows Task Scheduler agar auto-start |
| **Railway** | ✅ | Free tier, tinggal isi environment variables |
| **Render** | ✅ | Free tier, tapi service bisa tidur → bot harus tetap aktif |
| **Oracle Cloud Always Free** | ✅ | VM 1 core / 1 GB, paling stabil di cloud gratis |
| **Google Cloud Run** | ✅ | Free tier ada, tapi butuh konfigurasi tambahan untuk bot |

> **Rekomendasi:** untuk satu tim kecil, jalankan di PC yang nyala 24 jam
> (atau Raspberry Pi). Gratis, mudah, dan tidak ada yang perlu dinyalakan ulang.
> Kalau mau cloud, **Railway** paling gampang.

### Environment variables di hosting

Di dashboard Railway/Render, isi **persis sama** dengan isi `.env` Anda
(`TELEGRAM_BOT_TOKEN`, `GOOGLE_SHEET_ID`, `APPROVER_*`, `HR_USER_ID`, dll).
Jangan commit `.env` ke git.

---

## Troubleshooting

| Gejala | Penyebab & Solusi |
|---|---|
| `Unauthorized` saat start | `TELEGRAM_BOT_TOKEN` salah / ada spasi |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| `403 storageQuotaExceeded` saat upload Drive | Service account tidak punya quota di My Drive → butuh Shared Drive, atau biarkan `DRIVE_UPLOAD_ENABLED=false` |
| `DefaultCredentialsError` | `credentials.json` tidak ada / rusak / path salah |
| Kolom PDF URL kosong di Sheet | Header kolom N/O belum ada → `python tools/setup_sheet_columns.py` |
| Bot tidak merespon | Proses `python main.py` sudah jalan? Cek `logs/bot_YYYYMMDD.log` |
| PDF tidak ada tanda tangan | `APPROVER_N_ESIGN` belum diisi atau file PNG tidak ditemukan |

---

## Privasi & Keamanan

Repo ini sengaja **tidak** memuat data pribadi:

- `.env` dan `credentials.json` sudah masuk `.gitignore` — **jangan** pernah di-commit
- Tanda tangan asli & logo perusahaan **tidak** disertakan; `png/` hanya berisi placeholder
- Nama approver, ID Telegram, dan ID Google Sheet/Drive dibaca dari `.env`, bukan hardcoded
- Pengiriman PDF dibatasi oleh `services/delivery.py`: hanya HR, pemohon, dan approver
  yang terdaftar yang bisa menerima dokumen

Kalau pernah terlanjur commit rahasia, **riwayat git juga menyimpan rahasia itu**.
Hapus dengan `git filter-repo`, atau mulai repo baru dengan riwayat bersih.

---

## Kontribusi

Silakan buka issue atau pull request. Sebelum mengirim:

```bash
python tools/test_guides.py && python tools/test_idempotency.py
```

Jangan commit `.env`, `credentials.json`, maupun tanda tangan asli.

---

## Lisensi

[MIT](LICENSE) — bebas dipakai, dimodifikasi, dan dipakai komersial.
