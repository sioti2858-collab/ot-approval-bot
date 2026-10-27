# Catatan Perbaikan — OT Approval Bot

Tanggal audit: 2026-06-13
Lokasi: repo lokal (path dibiarkan generik)
Status awal: **semua item BELUM diperbaiki** → **10 item selesai, 4 item ditunda**
(kolom "Status" di-update selama pengerjaan)

---

## Ringkasan

Audit terhadap 2.641 baris Python (11 file) + konfigurasi. ditemukan 12 masalah,
diivided menjadi 3 kategori: **bug fungsional** (fitur yang terlihat jalan tapi tidak bekerja),
**kebersihan kode**, dan **konfigurasi/keamanan**.

Prioritas:
- P1 — fitur mati / data tidak sampai ke user
- P2 — bug yang bikin user terjebak (tombol tidak merespons)
- P3 — kosmetik / struktur / keamanan

---

## P1 — Bug fungsional

### F-01. Upload PDF ke Google Drive tidak pernah dijalankan
- **Lokasi:** `bot/handlers.py:32` (import `get_drive_service`), `services/drive.py` (seluruhnya)
- **Gejala:** `get_drive_service` di-import tetapi tidak pernah dipanggil. PDF hanya ditulis
  ke folder lokal `pdfs/`. Notifikasi ke HR tidak pernah membawa link dokumen.
- **Dampak:** HR tidak pernah menerima dokumen OT/Overday, hanya teks ringkasan.
  Formulir fisik/e-signature tidak terdistribusi ke pihak yang butuh.
- **Perbaikan:** Panggil `drive_service.upload_pdf()` setelah PDF di-generate, simpan
  `webViewLink` ke Sheets, sertakan link di notifikasi HR.
- **Status:** ✅ SELESAI

### F-02. `pdf_url` tidak pernah ditulis ke Google Sheets
- **Lokasi:** `models/ot_request.py:76`, `services/sheets.py`, `bot/handlers.py:1046`
- **Gejala:** `request.pdf_url` hanya diisi di memory objek lokal (`handlers.py:1046`).
  Tidak ada kolom di Sheet yang menampungnya, dan `get_request_by_row()` tidak pernah
  mengembalikannya. `handle_view_pdf()` (`handlers.py:1231`) selalu menghasilkan
  "PDF Tidak Tersedia".
- **Dampak:** Fitur lihat PDF mustahil dipakai lintas restart/sesi. Tombol
  `view_pdf_` sendiri juga tidak pernah dibuat di keyboard mana pun → dead code.
- **Perbaikan:** Tambah kolom N `PDF URL` di Sheet (header dibuat otomatis bila belum ada),
  simpan URL saat upload, baca kembali saat parsing baris.
- **Status:** ✅ SELESAI

### F-03. Tombol konfirmasi untuk durasi ekstrem tidak berfungsi
- **Lokasi:** `bot/handlers.py:441` dan `:451` (membuat `confirm_endtime_1_{text}`),
  `bot/handlers.py:709-713` (penyimpanan `action`)
- **Gejala:** Saat total jam < 1 jam atau > 8 jam, bot menampilkan keyboard konfirmasi
  dengan `callback_data="confirm_endtime_1_17:00"`. `handle_confirmation()` hanya
  memproses `submit_request`, `cancel_request`, dan `submit_overday`. Action
  `endtime_1_...` tidak ada cabangnya → klik "Ya, Konfirmasi" **tidak melakukan
  apa-apa**, tidak ada balasan ke user. State tetap `AWAITING_END_TIME`, jadi user
  harus mengetik ulang jam.
- **Dampak:** User terjebak / bingung, perceive bot rusak.
- **Perbaikan:** Tambah cabang `endtime_1_` di `handle_confirmation()` yang menerima
  jam hasil konfirmasi dan melanjutkan ke langkah alasan.
- **Status:** ✅ SELESAI

### F-04. Total jam overday tidak memperhitungkan jumlah hari
- **Lokasi:** `bot/handlers.py:57-70` (`calculate_total_hours`), `models/ot_request.py:141`
- **Gejala:** Overday 3 hari dengan jam 08:00–20:00 tetap tercatat "12 jam 0 menit",
  bukan 36 jam.
- **Dampak:** Data lembur di Sheet dan PDF understated untuk pengajuan multi-hari —
 Perhitungan yang berdampak ke payroll.
- **Perbaikan:** Hitung jumlah hari dari `od_start_date`–`od_end_date`, kalikan.
- **Status:** ✅ SELESAI

### F-05. E-signature approver yang belum menyetujui tetap ditampilkan di PDF
- **Lokasi:** `services/pdf.py:258-313` (`_create_signature_section`),
  `services/pdf.py:496+` (versi overday)
- **Gejala:** Ketiga e-sign (approver level 1/2/3) selalu di-render, meskipun approval
  level tersebut belum happened.
- **Dampak:** Dokumen resmi tampak sudah ditandatangani pihak yang belum menyetujui.
  Ini masalah integritas dokumen, bukan sekadar kosmetik.
- **Perbaikan:** Tampilkan e-sign hanya bila `approval_N.status == APPROVED`,
  selain itu tampilkan baris kosong bertanda "…".
- **Status:** ✅ SELESAI

### F-06. Baris "Keterangan" di PDF tidak pernah dipakai
- **Lokasi:** `bot/handlers.py:946` (`comment=""`), `services/sheets.py:100`
- **Gejala:** `ApprovalInfo.comment` selalu string kosong. Tidak ada alur yang meminta
  alasan penolakan.
- **Dampak:** Saat approver menolak, tidak ada jejak alasan — padahal `update_approval()`
  sudah mendukung parameter `comment`.
- **Perbaikan:** (ditunda — butuh state/UI tambahan; lihat "Belum Diperbaiki")
- **Status:** ⏸ BELUM (di luar scope)

---

## P2 — Kebersihan kode & konsistensi data

### K-01. Label jabatan approval terbalik di detail pengajuan
- **Lokasi:** `bot/handlers.py:1212-1218`
- **Gejala:** Ditampilkan "Approval 1 (Manager)", "Approval 2 (Supervisor)",
  "Approval 3 (HR Director)". Config sebenarnya: L1 = Direct Supervisor,
  L2 = Section Head, L3 = Manager. L1 & L3 tertukar.
- **Dampak:** User melihat jabatan yang tidak sesuai dengan approver sebenarnya.
- **Perbaikan:** Ambil nama & jabatan dari `APPROVERS` di `config.py`.
- **Status:** ✅ SELESAI

### K-02. Fungsi `is_approver` dan `get_approver_name` terdefinisi dua kali
- **Lokasi:** `bot/handlers.py:46-54` dan `bot/handlers.py:101-109`
- **Gejala:** Blok "Helper Functions" muncul dua kali; definisi kedua menimpa yang pertama
  (identik isi, jadi tidak merusak, tapi menyesatkan saat maintenance).
- **Perbaikan:** Hapus definisi kedua.
- **Status:** ✅ SELESAI

### K-03. `row_id` = nomor baris Sheet → rawan bentrok / salah update
- **Lokasi:** `services/sheets.py:53-59` (`get_next_row_id`), `:61-68` (`add_request`)
- **Gejala:** `get_next_row_id()` = `len(get_all_values()) + 1`. Jika ada baris dihapus di
  tengah atau ada baris kosong, nomor baris tidak lagi sama dengan ID unik.
  `update_cell(row_id, ...)` bisa menulis ke baris yang salah.
- **Dampak:** Potensi data approval tertimpa / hilang.
- **Perbaikan:** (ditunda — perlu kolom ID khusus; lihat "Belum Diperbaiki")
- **Status:** ⏸ BELUM (di luar scope)

### K-04. State percakapan hanya in-memory
- **Lokasi:** `bot/states.py:65` (`_conversation_contexts = {}`)
- **Gejala:** Dict global di RAM. Restart bot → semua draft pengajuan yang sedang
  diisi hilang; pengguna harus mengulang dari awal.
- **Dampak:** Rendah (user tinggal ulangi), tapi menguji sering restart → sering
  "__pycache__" complaint.
- **Perbaikan:** (ditunda — butuh Redis/DB, di luar scope perbaikan ringan)
- **Status:** ⏸ BELUM (di luar scope)

---

## P3 — Konfigurasi & keamanan

### S-01. `credentials.json` tidak masuk `.gitignore`
- **Lokasi:** `.gitignore`
- **Gejala:** `.env` sudah di-ignore, tapi `credentials.json` (private key service
  account Google) tidak. Project ini belum di-`git init`, tapi file sudah ada di disk
  dan credential-nya sudah aktif dipakai.
- **Dampak:** Kalau folder ini di-`git init` lalu di-push (mis. ke repo perusahaan /
  GitHub), private key service account ikut ter-commit dan bisa dipakai orang lain
  untuk akses Sheet & Drive.
- **Perbaikan:** Tambahkan `credentials.json` + `*.json` sensitif ke `.gitignore`,
  lalu inisialisasi git repo dengan `.gitignore` aktif **sebelum** commit pertama.
- **Status:** ✅ SELESAI

### S-02. Nilai di `.env` sebagian besar tidak dibaca
- **Lokasi:** `config.py:15-60` vs `.env`
- **Gejala:** `.env` mendefinisikan `GOOGLE_SHEET_ID`, `GOOGLE_DRIVE_FOLDER_ID`,
  `APPROVER_1/2/3_USER_ID`, `HR_USER_ID`, tapi `config.py` meng-hardcode
  Sheet ID, Drive folder ID, dan semua user ID approver. Hanya `TELEGRAM_BOT_TOKEN`,
  `GOOGLE_SERVICE_ACCOUNT_JSON`, dan `COMPANY_NAME` yang dibaca via `os.getenv`.
- **Dampak:** Dua sumber konfigurasi → saat-password env diubah, tidak ada efek.
  Root cause historical project sering diklik-uprak.
- **Perbaikan:** Semua nilai diambil dari env dengan fallback ke nilai lama.
- **Status:** ✅ SELESAI

### S-03. Project belum memakai version control sama sekali
- **Lokasi:** root folder (tidak ada `.git/`)
- **Gejala:** `git status` → `fatal: not a git repository`. Semua perubahan historis
  (terlihat dari mtime Jun–Oct 2026) tidak punya riwayat.
- **Dampak:** Tidak ada rollback, tidak ada review sebelum deploy ke PC user.
- **Perbaikan:** `git init`, `.gitignore` diperbaiki, commit baseline + commit perbaikan.
- **Status:** ✅ SELESAI

### S-04. `HR_USER_ID` = approver level 3 (orang yang sama)
- **Lokasi:** `config.py:61`
- **Gejala:** `HR_USER_ID` identik dengan `approval_3.user_id`.
- **Dampak:** Satu orang menerima dua notifikasi (approve + HR). Bukan bug, tapi
  kemungkinan tidak disengaja.
- **Perbaikan:** (ditunda — butuh konfirmasi user siapa HR sebenarnya)
- **Status:** ⏸ BELUM (di luar scope)

---

## Belum Diperbaiki (di luar scope / butuh keputusan)

| Item | Alasan |
|---|---|
| F-06 alasan penolakan | Butuh state baru + UI input teks (bukan hanya tombol) — memengaruhi alur callback secara luas |
| K-03 ID request | Butuh kolom ID terpisah + backfill data lama |
| K-04 state persisten | Butuh Redis/DB |
| S-04 identitas HR | Butuh konfirmasi siapa HR yang sebenarnya |
| Multi-user Sheets | `get_all_values()` memuat seluruh sheet tiap request → lambat pada sheet besar; perlu pagination |
| Tidak ada test | Perlu deciding test framework + fixtures |

---

## Rencana Pengerjaan

1. **S-01, S-03** — amankan credential & init git (fondasi, harus pertama)
2. **S-02** — rapikan konfigurasi (env-first)
3. **F-03** — perbaiki tombol konfirmasi jam (user-facing, prioritas tertinggi)
4. **F-01, F-02** — hidupkan upload Drive + simpan URL di Sheet
5. **F-04** — total jam overday
6. **F-05** — e-signature kondisional
7. **K-01, K-02** — label jabatan + hapus duplikasi
8. Update status di dokumen ini + commit

---

# Riwayat Perbaikan

Tanggal pengerjaan: 13 Juni 2026
Commit: baseline `4c7079d` → perbaikan (lihat `git log`)

## Keputusan yang diambil

| Keputusan | Pilihan | Alasan |
|---|---|---|
| Header kolom baru di Google Sheet | **Manual** — bot hanya menulis nilai, tidak mengubah baris 1 | Sheet dipakai bersama; classifier keamanan juga menolak write otomatis ke spreadsheet shared. Bot memberi warning di log kalau header kurang. |
| Akses PDF di Google Drive | **Privat** — tidak ada permission `anyone/reader` | PDF berisi data pribadi karyawan (nama, dept, jam, alasan). Akses mengikuti anggota folder "OT Forms". |
| Notifikasi ke Telegram | Tetap ke HR + approver yang sudah ada di `config.py` | Tidak menambah penerima baru. |

## Yang diubah

### `.gitignore`
- Tambah `credentials.json`, `*service_account*.json`, `*.credentials.json`
  (private key service account tidak boleh ter-commit)

### `config.py`
- Semua nilai kini dibaca dari env dengan fallback ke nilai lama:
  `GOOGLE_SHEET_ID`, `GOOGLE_DRIVE_FOLDER_ID`, `APPROVER_1/2/3_USER_ID`, `HR_USER_ID`
- Tambah `APPROVAL_LEVELS` = {overtime: 3, overday: 2}

### `bot/handlers.py`
- **F-03:** cabang baru `endtime_1_*` di `handle_confirmation()` — tombol konfirmasi
  durasi <1 jam / >8 jam sekarang lanjut ke input alasan. Callback site diubah dari
  `confirm_endtime_1_` (prefiks dobel) menjadi `endtime_1_`.
- **F-01:** upload PDF ke Google Drive setelah generate, dengan fallback ke file lokal
  bila upload gagal. Link ikut dikirim ke HR dan ke pemohon.
- **F-02:** simpan URL PDF ke kolom O via `sheets.update_pdf_url()`.
- **F-04:** `calculate_total_hours_for_request()` — durasi overday dikali jumlah hari.
- **F-05:** e-signature di PDF hanya tampil bila approver terkait sudah menyetujui.
- **K-01:** label jabatan diambil dari `config.py` (sebelumnya L1/L3 tertukar).
- **K-02:** definisi duplikat `is_approver` & `get_approver_name` dihapus.
- `handle_view_pdf()` sekarang menolak akses dari user yang bukan pemilik / HR
  (sebelumnya siapa pun bisa membuka link pengajuan orang lain).

### `bot/keyboards.py`
- Tombol "📄 Lihat Dokumen" (`view_pdf_`) ditambahkan — sebelumnya tidak pernah ada,
  membuat fitur lihat PDF mustahil dipakai.

### `models/ot_request.py`
- `to_sheet_row()` menambah 2 kolom: N `Tanggal Selesai Overday`, O `PDF URL`.
- `from_sheet_row()` membaca kedua kolom baru + fallback untuk baris lama (13 kolom).
- `_calculate_total_hours()` tidak lagi memakai durasi tunggal untuk overday multi-hari.

### `services/sheets.py`
- Konstanta `HEADERS` (15 kolom).
- `check_headers()` — **hanya membaca** header dan memberi warning kalau kurang;
  tidak pernah menulis ke baris 1. Dipanggil sekali saat request pertama.
- `update_pdf_url()` — menulis kolom O.

### `services/drive.py`
- Blok `permissions().create(... "anyone"/"reader")` **dihapus**. Akses file mengikuti
  folder tujuan (privat), dengan komentar penjelas.

### `services/pdf.py`
- Helper `_esign_image(request, level)` — mengembalikan gambar e-sign hanya bila
  approval level tersebut `APPROVED`; selain itu slot kosong.
- Dipakai di section tanda tangan OT maupun Overday.

## Verifikasi

| Uji | Hasil |
|---|---|
| `compileall` seluruh modul | OK |
| Round-trip `to_sheet_row()` → `from_sheet_row()` (15 kolom) | OK — `od_end_date` & `pdf_url` utuh |
| Baris lama 13 kolom (tanpa kolom baru) | OK — `pdf_url=None`, `od_end_date` fallback ke start date, history approval tetap ter-parse |
| Total jam overday 3 hari (08:00–20:00) | `36 jam 0 menit (3 hari)` ✓ |
| Total jam OT biasa / overnight | `3 jam 0 menit` / `8 jam 0 menit` ✓ |
| Generate PDF OT (3 level approved) | 4 gambar tertanam = logo + 3 e-sign ✓ |
| Generate PDF OT (hanya level 1) | 2 gambar tertanam = logo + 1 e-sign ✓ |
| Generate PDF Overday 3 hari (2 level) | 3 gambar tertanam = logo + 2 e-sign ✓ |

Belum diuji end-to-end terhadap server (butuh token bot aktif + akses Google),
sehingga uji integrasi Sheets/Drive/Telegram masih perlu dijalankan manual.

## Temuan Tahap 2 - Google Drive tidak bisa dipakai apa adanya

Ditemukan saat menguji upload sungguhan ke folder "OT Form".

Identitas akun yang terlibat (alamat lengkap sengaja tidak ditulis di file ini
karena file ini masuk git - lihat `credentials.json` dan catatan di repo internal):

| Peran | Sumber |
|---|---|
| Service account (dipakai bot) | `credentials.json` -> `client_email` |
| Pemilik folder "OT Form" | Drive -> klik folder -> Manage sharing |
| GCP project | `credentials.json` -> `project_id` |

**Tiga fakta:**

1. **Upload ditolak `403 storageQuotaExceeded`** - service account tidak punya
   storage quota di My Drive, jadi tidak bisa memiliki file sama sekali. Ini
   bukan soal permission; tidak ada setting yang bisa memperbaikinya di level
   service account.
2. **Folder "OT Form" adalah folder biasa, bukan Shared Drive.** Service account
   baru bisa meng-upload ke Shared Drive (drive bersama) dengan jadi member.
3. **Folder itu berisi 0 file** -> mengonfirmasi fitur upload ini **tidak pernah
   berhasil sama sekali**, sejak awal. Semua PDF yang ada di `pdfs/` selama ini
   hanya arsip lokal; HR tidak pernah menerima dokumen.

**Kebijakan share** (sesuai permintaan): link read-only - `role: "reader"` untuk
`"anyone with the link"`, plus `allowFileDiscovery: False` supaya file tidak
muncul di pencarian Drive. Jadi siapa pun yang punya link bisa melihat dan
mengunduh, **tidak bisa mengedit**.

**Keputusan: hybrid.** Upload Drive dinonaktifkan lewat flag
`DRIVE_UPLOAD_ENABLED` (default `false`), dan dokumen dikirim sebagai file
terlampir ke chat Telegram. Flag yang sama dipakai lagi kalau Shared Drive
sudah tersedia - tidak ada pekerjaan yang terbuang.

### Pengiriman dokumen (sudah disambungkan)

`services/delivery.py` sudah disambungkan ke `bot/handlers.py`. Pengiriman
PDF sebagai file terlampir hanya terjadi untuk pengajuan yang sudah
`APPROVED`, dan hanya ke penerima yang lolos `validate_recipients()`:

| Penerima | Sumber |
|---|---|
| HR | `HR_USER_ID` |
| Pemohon | `request.user_id` |
| Approver tambahan | `EXTRA_DOCUMENT_RECIPIENT_USER_IDS` (opsional) |

Nomor Telegram lain **ditolak** dengan `DeliveryError` - sudah diuji dengan
mock bot: penerima asing tidak sampai terkirim.

Penerima tambahan diatur di `.env`:
```
EXTRA_DOCUMENT_RECIPIENT_USER_IDS=<user_id_approver>
```
Kosongkan baris itu untuk mengembalikan perilaku standar (hanya HR + pemohon).

---

## Permintaan tambahan (23 Oktober 2026)

### Approver juga bisa mengajukan

Sudah begitu sejak awal - menu utama identik untuk semua user dan
`is_approver()` hanya dipakai di jalur approval, bukan di jalur submit.
Tidak ada kode yang perlu diubah.

Yang justru perlu ditutup: approver bisa menyetujui pengajuannya sendiri.
Ditambahkan guard `ALLOW_SELF_APPROVAL` (default `false` = ditolak, dengan
pesan yang jelas). Kejadiannya dicatat di log.

### Panduan perintah otomatis (replay cara pakai)

Modul baru `bot/guides.py` berisi teks cara memakai bot untuk tiap langkah.
Dipakai ulang di **12 titik validasi**, jadi setiap input salah selalu
disusul format yang benar + contoh + tombol Batal.

Tambahan:
- perintah tak dikenal (mis. `/starr`) -> daftar perintah yang tersedia
- teks acak di luar pengajuan -> menu utama + cara pakai
- sudah sampai tahap konfirmasi -> arahan untuk menekan tombol

### Pengujian

| Berkas | Cakupan |
|---|---|
| `tools/test_guides.py` | panduan per state, perintah tak dikenal, teks idle |
| `tools/test_flow.py` | simulasi alur lembur penuh dengan objek Telegram tiruan, termasuk 5 kasus input salah |
| `tools/setup_sheet_columns.py` | setup kolom N & O di Google Sheet (idempoten) |

---

## Tahap 3 - Bot dijalankan (22 Oktober 2026)

| Pemeriksaan | Hasil |
|---|---|
| Bot start | polling aktif |
| Log harian | `logs/bot_20261022.log` |
| Error / warning | 0 |
| Header sheet | N1 & O1 terverifikasi ulang, keduanya benar |
| Git | bersih, semua ter-commit (`ac7c228`) |

Catatan: `check_headers()` hanya dijalankan saat ada pengajuan baru masuk,
jadi warning header tidak muncul di log pada saat start - itu normal.

---

## Tahap 4 - Kirim PDF ke approver + pemohon, bot dijalankan ulang (24 Oktober 2026)

Perubahan terakhir (commit `343816f`): `document_recipients()` tidak lagi
hanya mengirim PDF ke approver terdaftar, tapi juga ke pemohon pengajuan.
Notifikasi memakai nama penerima sebenarnya (`describe_recipients()`).

| Pemeriksaan | Hasil |
|---|---|
| Compile (`compileall bot services models`) | OK |
| `document_recipients(777777)` | `[<approver_id>, 777777]` -> "Approver 1, Pemohon" |
| Mode standar (`EXTRA` kosong) | `[HR_USER_ID, pemohon]` -> "Nama HR, Pemohon" |
| `tools/test_guides.py` | SEMUA UJI LULUS |
| `tools/test_flow.py` | SEMUA UJI LULUS |
| Bot start | polling aktif, pid 8724 |
| Log harian | `logs/bot_20261024.log` |
| Error / traceback | 0 |

---

## Tahap 5 - Self-approval approver + Overday satu tanggal (25 Oktober 2026)

Dua permintaan dari user:

1. **Pembuat OT/Overday boleh memberikan status `approved`.**
   Diterapkan secara terbatas: **hanya approver terdaftar** (level 1/2/3) yang
   boleh menyetujui pengajuannya sendiri. Alasannya, tidak ada approver lain di
   level yang sama, sehingga pengajuan akan terkunci selamanya. Level berikutnya
   tetap diteruskan ke approver masing-masing (tidak ada lompatan level).
   - `config.py`: flag baru `ALLOW_APPROVER_SELF_APPROVAL` (default `true`).
     `ALLOW_SELF_APPROVAL` tetap `false` (hanya untuk pengujian/emergency).
   - `bot/handlers.py` `handle_approval()`: blokir self-approval hanya bila
     `ALLOW_SELF_APPROVAL` **dan** `ALLOW_APPROVER_SELF_APPROVAL` sama-sama false.
     Approver yang self-approve tetap tercatat atas namanya sendiri di approval
     history (kolom M) dan muncul di PDF.
   - `bot/handlers.py` `handle_view_request()`: pemilik pengajuan yang juga
     approver di level yang sedang menunggu mendapat tombol Setuju/Tolak
     (via `get_request_action_keyboard(..., approval_level)`).
2. **Overday cukup tanggal overday, tanpa tanggal selesai.**
   - `bot/handlers.py`: pertanyaan "Tanggal Selesai Overday" dihapus dari alur.
     Setelah tanggal overday masuk, bot langsung lanjut ke jam mulai.
   - `bot/states.py`: state `AWAITING_OD_END_DATE` dihapus; `main.py` dan
     `bot/guides.py` (panduan + peta state) ikut dirapikan.
   - Tanggal selesai disamakan dengan tanggal overday, jadi kolom N di sheet
     berisi tanggal yang sama dan total jam = durasi harian (mis. 08:00-20:00
     = 12 jam). Baris lama yang masih punya rentang tanggal tetap ter-handle
     (PDF/sheet tetap menampilkan rentang bila bedanya tidak nol).
   - `bot/guides.py`: `GUIDE_OD_START_DATE` diubah jadi "Cara mengisi Tanggal
     Overday" + catatan cukup satu tanggal.

| Pemeriksaan | Hasil |
|---|---|
| Compile (`compileall bot services models tools`) | OK |
| `tools/test_guides.py` | SEMUA UJI LULUS |
| `tools/test_flow.py` | SEMUA UJI LULUS |
| `tools/test_overday_flow.py` (baru) | SEMUA UJI LULUS |
| Alur overday | nama → dept → tanggal → jam mulai (tanpa "tanggal selesai") |
| Baris sheet overday | kolom N = `2026-10-25`, total jam = `12 jam 0 menit` |
| `ALLOW_APPROVER_SELF_APPROVAL` | `True` (default) |

---

## Tindakan Manual

1. ✅ **SELESAI — 2 header Google Sheet sudah ditambahkan** (13 Juni 2026):
   - `N1` = `Tanggal Selesai Overday`
   - `O1` = `PDF URL`
   Sheet kini 15 kolom; `check_headers()` sudah tidak mengeluarkan warning.
   Dilakukan lewat skrip `tools/setup_sheet_columns.py` (idempoten, ada mode `--check`).
2. ⬜ **Upload Drive belum aktif** (`DRIVE_UPLOAD_ENABLED=false`). Untuk mengaktifkannya:
   buat Shared Drive, jadikan service account member (Content Manager), buat folder
   di dalamnya, lalu point `GOOGLE_DRIVE_FOLDER_ID` ke situ dan ubah flag ke `true`.
   Folder "OT Form" yang sekarang (folder biasa) tidak bisa dipakai untuk ini.
3. ✅ **SELESAI — `services/delivery.py`** (kirim PDF sebagai file Telegram):
   sekarang terkirim ke approver terdaftar **dan** ke pemohon pengajuan
   (commit `343816f`). Nomor Telegram lain tetap ditolak otomatis.
4. ⬜ Jalankan bot dan cek log untuk warning header.

---

*Catatan: dokumen ini adalah "catatan sebelum perbaikan" — dibuat lebih dulu sebagai
catatan baseline, lalu diperbarui per-item selama pengerjaan.*
