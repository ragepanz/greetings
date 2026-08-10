"""
generate_card.py
----------------
Menempelkan data karyawan (NOPEG, NAMA, UNIT, JABATAN) yang berulang tahun ke template kartu ucapan,
tepat di bawah tulisan "Dear".

Dipanggil dari send_birthday_emails.py, tapi juga bisa dites manual:

    python generate_card.py "NOVITA SARI" "533519" "CABIN" "ENGINEER"

Hasilnya disimpan di ./output/<nama>.jpg
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "template", "card_template.png")
FONT_PATH = os.path.join(BASE_DIR, "fonts", "LiberationSans-Bold.ttf")

# Warna navy diambil langsung dari warna tulisan "Dear" pada template asli
NAVY = (16, 32, 74)

# Posisi area teks pada template baru: di bawah "Dear" dan di atas garis hati.
TEMPLATE_WIDTH = 605
TEMPLATE_HEIGHT = 807
TEXT_CENTER_X = 0.5
MAX_TEXT_WIDTH_RATIO = 0.72
TEXT_Y_RATIOS = (0.398, 0.423)


def _fit_font(draw, text, max_width, max_size, min_size):
    """Cari ukuran font terbesar yang muat dalam max_width, turun bertahap kalau teks panjang."""
    size = max_size
    while size >= min_size:
        font = ImageFont.truetype(FONT_PATH, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            return font
        size -= 1
    return ImageFont.truetype(FONT_PATH, min_size)


def generate_card(name: str, output_path: str, nopeg: str = None, unit: str = None, jabatan: str = None) -> str:
    """Buat 1 file kartu ucapan untuk `name`, `unit`, dan `nopeg`, simpan ke `output_path`. Return path-nya."""
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    nopeg_clean = str(nopeg).strip() if nopeg and str(nopeg).strip() and str(nopeg).strip().lower() != "nan" else ""
    if nopeg_clean.endswith(".0"):
        nopeg_clean = nopeg_clean[:-2]

    name_clean = name.strip().upper() if name else ""
    unit_clean = str(unit).strip().upper() if unit and str(unit).strip() and str(unit).strip().lower() != "nan" else ""

    width, height = img.size
    scale = width / TEMPLATE_WIDTH
    max_text_width = int(width * MAX_TEXT_WIDTH_RATIO)
    y_positions = [int(height * ratio) for ratio in TEXT_Y_RATIOS]

    sub_parts = []
    if unit_clean:
        sub_parts.append(unit_clean)
    if nopeg_clean:
        sub_parts.append(nopeg_clean)
    sub_str = " | ".join(sub_parts)

    lines = []
    if name_clean:
        lines.append((name_clean, _fit_font(draw, name_clean, max_text_width, int(20 * scale), int(12 * scale))))
    if sub_str:
        lines.append((sub_str, _fit_font(draw, sub_str, max_text_width, int(13 * scale), int(9 * scale))))

    for (text, font), y_pos in zip(lines, y_positions):
        draw.text((int(width * TEXT_CENTER_X), y_pos), text, font=font, fill=NAVY, anchor="mm")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, quality=92)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Pemakaian: python generate_card.py "NAMA KARYAWAN" [NOPEG] [UNIT]')
        sys.exit(1)

    name = sys.argv[1]
    nopeg = sys.argv[2] if len(sys.argv) > 2 else None
    unit = sys.argv[3] if len(sys.argv) > 3 else None

    safe_filename = "".join(c for c in name if c.isalnum() or c in " _-").strip().replace(" ", "_")
    out = os.path.join(BASE_DIR, "output", f"{safe_filename}.jpg")
    path = generate_card(name, out, nopeg=nopeg, unit=unit)
    print(f"Kartu tersimpan di: {path}")

