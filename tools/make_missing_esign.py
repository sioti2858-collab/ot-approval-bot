"""
Buat placeholder tanda tangan untuk PDF.

Kenapa ada file ini:
  Repo ini PUBLIK, jadi tanda tangan asli tidak boleh di-commit - itu
  mempublikasikan tanda tangan pribadi orang. Tanda tangan asli dikirim
  lewat environment variable (APPROVER_x_ESIGN_BASE64 / APPROVER_x_ESIGN).

  Dulu repo menyimpan "coretan" placeholder yang saling hampir identik di
  png/esign_approver_1/2/3.png. Kalau env variable-nya lupa diisi, PDF
  menampilkan coretan yang tidak jelas - dan dikira tanda tangan asli.

  Sekarang semua fallback memakai satu gambar yang jelas berlabel, jadi
  kalau konfigurasi e-sign belum lengkap, pembaca PDF langsung tahu
  ada yang belum diisi (bukan salah tanda tangan orang).

Jalankan: python tools/make_missing_esign.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET = PROJECT_ROOT / "png" / "esign_missing.png"

WIDTH, HEIGHT = 420, 180
BACKGROUND = (250, 250, 250)
BORDER = (190, 190, 190)
TEXT = (110, 110, 110)


def _font(size: int):
    """Ambil font TrueType dari Windows kalau ada, kalau tidak pakai default."""
    try:
        from PIL import ImageFont

        for name in ("arial.ttf", "segoeui.ttf", "calibri.ttf"):
            candidate = Path("C:/Windows/Fonts") / name
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
    except Exception:
        pass
    return None


def build() -> int:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow tidak terpasang - jalankan: pip install Pillow")
        return 1

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.rectangle([2, 2, WIDTH - 3, HEIGHT - 3], outline=BORDER, width=3)
    # garis diagonal supaya jelas ini bukan tanda tangan
    draw.line([12, 12, WIDTH - 13, HEIGHT - 13], fill=(225, 225, 225), width=2)
    draw.line([WIDTH - 13, 12, 12, HEIGHT - 13], fill=(225, 225, 225), width=2)

    lines = [
        "TANDA TANGAN BELUM DIKONFIGURASI",
        "isi APPROVER_x_ESIGN_BASE64 di GitHub Secrets",
    ]
    fonts = [_font(17), _font(12)]

    y = 58
    for text, font in zip(lines, fonts):
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            width = right - left
        except Exception:
            width = len(text) * 7
        draw.text(((WIDTH - width) / 2, y), text, fill=TEXT, font=font)
        y += 32

    image.save(TARGET, "PNG", optimize=True)
    size = TARGET.stat().st_size
    print(f"Placeholder dibuat: {TARGET.relative_to(PROJECT_ROOT)} ({size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(build())
