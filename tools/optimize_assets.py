"""
Optimalkan aset PNG (tanda tangan & logo) supaya muat di GitHub Actions.

GitHub membatasi nilai repository secret/variable maksimal 48 KB. PNG asli
disimpan sebagai base64 (besar file x 1,37), jadi file PNG harus di bawah
~34 KB supaya base64-nya muat.

Skrip ini:
  - tidak mengubah file asli di local_assets/
  - menulis hasil ke local_assets/optimized/
  - mencetak panjang base64 tiap file (TIDAK mencetak isinya)

Pemakaian:
  python tools/optimize_assets.py            # buat + tampilkan ukuran
  python tools/optimize_assets.py --copy     # salin ke clipboard-friendly .b64
"""
import argparse
import base64
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "local_assets"
OUT = ASSETS / "optimized"

# Batas nilai GitHub (bytes)
GITHUB_LIMIT = 48 * 1024


def optimize(src, dst):
    """Perkecil + optimalkan PNG sampai muat di bawah batas GitHub."""
    im = Image.open(src).convert("RGBA")

    # Logo & tanda tangan tidak butuh transparansi penuh -> RGB lebih kecil.
    # Latar putih yang tidak dipakai dijadikan putih, bukan alpha.
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        im = bg

    for width in (im.width, 320, 240, 180):
        if width > im.width:
            continue
        scaled = im if width == im.width else im.resize(
            (width, max(1, round(im.height * width / im.width))), Image.LANCZOS
        )
        for colors in (256, 128, 64, 32):
            q = scaled.convert("P", palette=Image.ADAPTIVE, colors=colors)
            q.save(dst, format="PNG", optimize=True)
            if dst.stat().st_size <= 34_000:
                return q.size, colors
    # Simpan versi terakhir apa adanya walau masih di atas batas
    return im.size, 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--copy", action="store_true", help="Tulis file .b64 di samping hasil")
    args = parser.parse_args()

    if not ASSETS.exists():
        print("! folder local_assets tidak ditemukan")
        return 1

    OUT.mkdir(exist_ok=True)
    files = sorted(ASSETS.glob("*.png"))
    if not files:
        print("! tidak ada PNG di local_assets/")
        return 1

    semua_ok = True
    print(f"{'file':<22}{'asli':>10}{'hasil':>10}{'base64':>10}  status")
    print("-" * 68)

    for src in files:
        dst = OUT / src.name
        size, colors = optimize(src, dst)
        raw = dst.read_bytes()
        b64_len = len(base64.b64encode(raw))
        ok = b64_len <= GITHUB_LIMIT
        semua_ok = semua_ok and ok

        status = "MUAT" if ok else "TERLALU BESAR"
        if colors:
            status += f" ({colors} warna)"
        print(f"{src.name:<22}{src.stat().st_size:>10}{len(raw):>10}{b64_len:>10}  {status}")

        if args.copy:
            (OUT / (src.stem + ".b64")).write_text(
                base64.b64encode(raw).decode("ascii"), encoding="utf-8"
            )

    print()
    print(f"Batas GitHub: {GITHUB_LIMIT} karakter per secret/variable")
    if semua_ok:
        print("Semua aset muat -> base64-nya bisa langsung ditempel ke GitHub variable.")
        print(f"Folder hasil: {OUT}")
    else:
        print("!! Ada aset yang masih terlalu besar -> belum bisa dipakai di GitHub.")
    return 0 if semua_ok else 1


if __name__ == "__main__":
    sys.exit(main())
