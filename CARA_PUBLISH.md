# Cara Publish ke GitHub

Semua persiapan sudah beres. Yang tersisa cuma **2 langkah**.

---

## Langkah 1 — Bikin repo di github.com

1. Buka <https://github.com/new>
2. **Owner**: `sioti2858-collab`
3. **Repository name**: `ot-approval-bot`
4. **Pilih Public** (gratis, tanpa batas)
5. **Jangan centang** "Add a README file", "Add .gitignore", atau "Choose a license"
   (repo Anda sudah punya semuanya — centang ini nanti bikin konflik)
6. Klik **Create repository**

## Langkah 2 — Push dari komputer ini

Buka terminal di folder `D:\ot-approval-bot`, lalu jalankan:

```bash
git push -u origin main
```

Saat GitHub minta password:
- **Username**: `sioti2858-collab`
- **Password**: pakai **Personal Access Token**, bukan password biasa.
  Buat di <https://github.com/settings/tokens> → *Fine-grained tokens* →
  centang **Contents: Read and write** → Generate → salin tokennya.

> Kalau `git push` sudah berhasil dan mau push lagi di kemudian hari, cukup `git push` saja.

---

## Cek hasil

Buka <https://github.com/sioti2858-collab/ot-approval-bot>

Yang seharusnya Anda lihat:

| Bagian | Isi |
|---|---|
| Tab **Code** | 39 file, README tampil rapi |
| Tab **Actions** | workflow "CI" jalan hijau (hijau = semua uji lulus) |
| Tab **Issues** | 2 template (Laporan Bug & Permintaan Fitur) |
| Tombol **About** | bisa diisi deskripsi & tag: `telegram`, `bot`, `pdf`, `google-sheets` |

---

## Kalau mau memamerkan bot di README

Tambah badge di bagian atas `README.md`:

```markdown
![GitHub Actions](https://github.com/sioti2858-collab/ot-approval-bot/actions/workflows/ci.yml/badge.svg)
```

---

## Catatan penting

- **Jangan** pernah `git push --all` atau `git push --mirror`. Branch `main` saja
  yang aman untuk dikirim.
- **Jangan** commit `.env` atau `credentials.json`. Keduanya sudah di `.gitignore`.
- Kalau butuh password manager di komputer ini:
  <https://git-scm.com/book/en/v2/Git-Tools-Credential-Storage>
- Kalau repo ingin diubah jadi **privat** (untuk versi internal asli):
  GitHub → **Settings → General → Danger Zone → Change visibility**
