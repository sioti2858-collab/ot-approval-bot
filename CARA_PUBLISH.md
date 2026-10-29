# Status Publish

Repo ini **sudah tayang** di <https://github.com/sioti2858-collab/ot-approval-bot> (public).

Kalau Anda clone ulang dari nol, ikuti saja **[README.md](README.md)** bagian
"Mulai Cepat". File ini hanya catatan buat pemilik repo.

---

## Yang sudah dilakukan

| Item | Status |
|---|---|
| Repo | ✅ https://github.com/sioti2858-collab/ot-approval-bot (public) |
| Deskripsi & topics | ✅ terpasang |
| Branch | `main` |
| CI (GitHub Actions) | ✅ hijau — <https://github.com/sioti2858-collab/ot-approval-bot/actions> |
| Workflow bot | ✅ `.github/workflows/bot.yml` — scheduled tiap 5 menit, jalan 6 jam/run |
| Persistensi state | ✅ `services/state_store.py` — state form disimpan ke tab Google Sheets |
| Deploy cloud | ✅ Railway (`Dockerfile` + `railway.json`) **atau** GitHub Actions gratis (repo public) |
| Data pribadi | ✅ nol (scan 48 entri file di repo: aman) |

## GitHub API — perlu izin apa saja

Fine-grained PAT (`github_pat_...`) yang dipakai untuk publish:

| Izin | Level | Dipakai untuk |
|---|---|---|
| Administration | Read and write | membuat repo, set deskripsi & topics |
| Contents | Read and write | push commit |
| Workflows | Write | hanya boleh ada di file `.github/workflows/*.yml` |

> Kalau token hanya punya "Contents" saja, push akan ditolak dengan
> `refusing to allow a Personal Access Token to create or update workflow`.

---

## Perawatan harian

```bash
git status              # cek perubahan
git add . && git commit -m "pesan"
git push                # kirim ke GitHub (branch main)
```

## Kalau perlu publish ulang / buat repo baru

1. Bikin **fine-grained token**: <https://github.com/settings/tokens>
   → Repository permissions: Administration *(write)*, Contents *(write)*, Workflows *(write)*
   → Repository access: **All public repositories**
2. Simpan token di file teks, jangan langsung di chat/prompt
3. Push pakai header auth sementara supaya token tidak tersimpan di `.git/config`:

   ```bash
   TOKEN=$(head -1 push_token.txt | tr -d '\r\n')
   B64=$(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')
   GIT_TERMINAL_PROMPT=0 git -c http.extraHeader="Authorization: Basic $B64" push -u origin main
   rm -f push_token.txt
   ```

4. **Revoke tokennya** setelah selesai di <https://github.com/settings/tokens>

---

## Jangan pernah

- Commit `.env` atau `credentials.json` (keduanya sudah di `.gitignore`)
- `git push --all` / `git push --mirror` — hanya `main` yang aman
- Menaruh tanda tangan asli atau logo perusahaan di dalam `png/`
  (folder `png/` hanya berisi placeholder; file asli ada di `local_assets/`)
