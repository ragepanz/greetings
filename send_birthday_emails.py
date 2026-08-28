"""
send_birthday_emails.py
------------------------
Alur:
  1. Baca data karyawan dari Google Sheets (lewat link CSV publish, tanpa perlu API key).
  2. Cocokkan tanggal & bulan lahir dengan tanggal hari ini (zona waktu Asia/Jakarta).
  3. Untuk tiap karyawan yang ulang tahun -> generate kartu ucapan (generate_card.py).
  4. Kirim email lewat Gmail SMTP, gambar di-embed langsung di body (bukan attachment).

Menjalankan manual (untuk tes):
    python send_birthday_emails.py --dry-run
    python send_birthday_emails.py --force-name "NOVITA SARI" --force-email you@example.com

Environment variables yang dibutuhkan (diisi lewat GitHub Actions Secrets):
    SHEET_CSV_URL     -> link "Publish to web" Google Sheets dalam format CSV
    GMAIL_ADDRESS     -> email pengirim, mis. your-email@gmail.com
    GMAIL_APP_PASSWORD-> App Password 16 digit dari akun Gmail tsb
    CC_EMAILS         -> (opsional) daftar email CC broadcast dipisah koma
"""

import argparse
import os
import smtplib
import socket
import sys
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # Baca .env file (kalau ada)

TZ_NAME = os.getenv("TIMEZONE", os.getenv("APP_TIMEZONE", "Asia/Jakarta"))
try:
    from zoneinfo import ZoneInfo
    JAKARTA_TZ = ZoneInfo(TZ_NAME)
except Exception:  # pragma: no cover
    JAKARTA_TZ = None

from generate_card import generate_card

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

REQUIRED_COLUMNS = ["NOPEG", "NAMA", "UNIT", "JABATAN", "TANGGAL LAHIR", "EMAIL"]


def today_jakarta() -> datetime:
    if JAKARTA_TZ:
        return datetime.now(JAKARTA_TZ)
    return datetime.now()


def extract_send_hour(df_raw: pd.DataFrame, default_hour: int = 7) -> int:
    """Membaca parameter JAM_KIRIM_WIB dari kolom PARAMETER dan VALUE jika ada."""
    cols_upper = {str(c).strip().upper(): c for c in df_raw.columns}
    if "PARAMETER" in cols_upper and "VALUE" in cols_upper:
        param_col = cols_upper["PARAMETER"]
        val_col = cols_upper["VALUE"]

        mask = df_raw[param_col].astype(str).str.strip().str.upper() == "JAM_KIRIM_WIB"
        matches = df_raw[mask]
        if not matches.empty:
            raw_val = str(matches.iloc[0][val_col]).strip()
            import re
            match = re.search(r"^(\d{1,2})", raw_val)
            if match:
                hour = int(match.group(1))
                if 0 <= hour <= 23:
                    return hour
    return default_hour


def load_employee_data(sheet_csv_url: str) -> tuple[pd.DataFrame, int]:
    """Ambil data dari Google Sheets (link publish CSV). Kolom wajib: NOPEG, NAMA, UNIT, JABATAN, TANGGAL LAHIR, EMAIL.
    Mengembalikan (df_karyawan, target_hour).
    """
    import io
    import urllib.request

    req = urllib.request.Request(
        sheet_csv_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        content = response.read()

    df_raw = pd.read_csv(io.BytesIO(content))
    df_raw.columns = [c.strip().upper() for c in df_raw.columns]

    target_hour = extract_send_hour(df_raw)

    missing = [c for c in REQUIRED_COLUMNS if c not in df_raw.columns]
    if missing:
        raise ValueError(
            f"Kolom berikut tidak ditemukan di Google Sheets: {missing}. "
            f"Kolom yang ada: {list(df_raw.columns)}"
        )

    df = df_raw.copy()
    df["TANGGAL LAHIR"] = pd.to_datetime(df["TANGGAL LAHIR"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["TANGGAL LAHIR", "NAMA", "EMAIL"])
    return df, target_hour


def find_todays_birthdays(df: pd.DataFrame, today: datetime) -> pd.DataFrame:
    mask = (df["TANGGAL LAHIR"].dt.day == today.day) & (df["TANGGAL LAHIR"].dt.month == today.month)
    return df[mask]


def build_email(name: str, to_email: str, cc_emails: list[str], from_email: str, card_path: str) -> MIMEMultipart:
    """Membangun 1 pesan email ucapan untuk 1 orang yang berulang tahun."""
    msg = MIMEMultipart("related")
    msg["Subject"] = f"Selamat Ulang Tahun, {name.title()}!"
    msg["From"] = f"Cabin Line Services<{from_email}>"
    msg["To"] = to_email
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)

    plain_text = f"Selamat Ulang Tahun, {name.title()}! Kartu ucapan terlampir."

    html = f"""\
    <html>
      <body style="font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #fcfbf9;">
        <div style="text-align: center; padding: 20px 0;">
          <img src="cid:birthday_card" alt="Selamat Ulang Tahun, {name.title()}!" style="max-width:600px; width:100%; height:auto; display:block; margin: 0 auto; border-radius:8px;" />
        </div>
      </body>
    </html>
    """

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(plain_text, "plain"))
    alt_part.attach(MIMEText(html, "html"))
    msg.attach(alt_part)

    with open(card_path, "rb") as f:
        img = MIMEImage(f.read(), _subtype="jpeg")
    img.add_header("Content-ID", "<birthday_card>")
    img.add_header("Content-Disposition", "inline", filename=os.path.basename(card_path))
    msg.attach(img)

    return msg


def send_email(msg: MIMEMultipart, from_email: str, app_password: str, to_email: str, cc_emails: list[str]):
    all_recipients = [to_email] + cc_emails
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(from_email, app_password)
            server.sendmail(from_email, all_recipients, msg.as_string())
    except (socket.timeout, TimeoutError, smtplib.SMTPConnectError, OSError):
        # Fallback ke port 587 STARTTLS jika port 465 diblokir jaringan WiFi/kantor
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls()
            server.login(from_email, app_password)
            server.sendmail(from_email, all_recipients, msg.as_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Jangan kirim email, cuma tampilkan siapa yang ulang tahun")
    parser.add_argument("--ignore-schedule", action="store_true", help="Abaikan pengecekan jam, paksa jalankan pengiriman")
    parser.add_argument("--no-cc", action="store_true", help="Jangan sertakan email CC (hanya kirim ke To)")
    parser.add_argument("--force-name", help="Paksa generate & kirim untuk 1 nama tertentu (buat testing)")
    parser.add_argument("--force-nopeg", help="Nopeg untuk --force-name")
    parser.add_argument("--force-unit", help="Unit untuk --force-name")
    parser.add_argument("--force-jabatan", help="Jabatan untuk --force-name")
    parser.add_argument("--force-email", help="Email tujuan kalau pakai --force-name")
    parser.add_argument("--force-cc", help="Daftar email CC untuk testing (dipisah koma)")
    args = parser.parse_args()

    sheet_csv_url = os.environ.get("SHEET_CSV_URL")
    from_email = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if args.no_cc:
        cc_emails = []
    elif args.force_cc:
        cc_emails = [e.strip() for e in args.force_cc.split(",") if e.strip()]
    else:
        cc_emails = [e.strip() for e in os.environ.get("CC_EMAILS", "").split(",") if e.strip()]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = None
    target_hour = 7
    if sheet_csv_url:
        try:
            df, target_hour = load_employee_data(sheet_csv_url)
        except Exception as e:
            print(f"Peringatan: Gagal memuat data Google Sheet: {e}", file=sys.stderr)

    if args.force_name or args.force_email:
        # Multi-target setup
        names = [n.strip() for n in args.force_name.split(";")] if args.force_name else ["TEST USER"]
        emails = [e.strip() for e in args.force_email.split(";")] if args.force_email else [None] * len(names)

        all_sheet_emails = []
        if df is not None and "EMAIL" in df.columns:
            all_sheet_emails = [
                str(e).strip() for e in df["EMAIL"].dropna().unique()
                if str(e).strip() and "@" in str(e)
            ]

        for name, target_email in zip(names, emails):
            nopeg = args.force_nopeg or "123456"
            unit = args.force_unit or "JKTTNP-2"
            jabatan = args.force_jabatan or "STAFF"

            if df is not None:
                match = pd.DataFrame()
                if target_email:
                    target_email_lower = target_email.strip().lower()
                    match = df[df["EMAIL"].astype(str).str.strip().str.lower() == target_email_lower]
                
                if match.empty and name:
                    match = df[df["NAMA"].astype(str).str.strip().str.upper() == name.strip().upper()]

                if not match.empty:
                    row = match.iloc[0]
                    name = str(row.get("NAMA", name)).strip()
                    nopeg = str(row.get("NOPEG", nopeg)).strip()
                    unit = str(row.get("UNIT", unit)).strip()
                    jabatan = str(row.get("JABATAN", jabatan)).strip()
                    target_email = str(row.get("EMAIL", target_email)).strip()
                    print(f"Ditemukan di Sheet: {name} (NOPEG: {nopeg}, UNIT: {unit}, JABATAN: {jabatan}) -> {target_email}")
                else:
                    print(f"Peringatan: Data tidak ditemukan di Sheet untuk name='{name}' email='{target_email}', menggunakan detail fallback.")

            card_path = generate_card(
                name=name,
                output_path=os.path.join(OUTPUT_DIR, f"{name.replace(' ', '_')}_test.jpg"),
                nopeg=nopeg,
                unit=unit,
                jabatan=jabatan
            )
            print(f"Kartu dibuat: {card_path}")

            if args.dry_run:
                print(f"   [dry-run] Email tidak dikirim untuk {name}.")
                continue

            if not target_email:
                print(f"Butuh email untuk {name}.")
                continue

            # CC list: hilangkan email penerima utama agar dia tidak menerima CC emailnya sendiri
            if args.no_cc:
                cc_list = []
            elif cc_emails:
                cc_list = [c for c in cc_emails if c.lower() != target_email.lower()]
            else:
                cc_list = [c for c in all_sheet_emails if c.lower() != target_email.lower()]

            try:
                msg = build_email(name, target_email, cc_list, from_email, card_path)
                send_email(msg, from_email, app_password, target_email, cc_list)
                print(f"Email terkirim ke {target_email} (CC: {cc_list})")
            finally:
                if os.path.exists(card_path):
                    os.remove(card_path)
        return

    if df is None:
        if not sheet_csv_url:
            print("ERROR: environment variable SHEET_CSV_URL belum diset.", file=sys.stderr)
        else:
            print("ERROR: Gagal memuat data dari Google Sheets. Pastikan koneksi internet aktif dan link CSV dapat diakses.", file=sys.stderr)
        sys.exit(1)

    today = today_jakarta()
    current_hour = today.hour
    print(f"Menjalankan pengecekan ulang tahun tanggal: {today.strftime('%d %B %Y')} (Jam WIB saat ini: {current_hour:02d}:00)")
    print(f"Jadwal pengiriman dari Google Sheets: {target_hour:02d}:00 WIB")

    if not args.ignore_schedule and current_hour != target_hour:
        print(f"Saat ini ({current_hour:02d}:00 WIB) bukan jadwal pengiriman ({target_hour:02d}:00 WIB). Pengecekan selesai (skipped).")
        return

    birthdays = find_todays_birthdays(df, today)

    if birthdays.empty:
        print("Tidak ada yang berulang tahun hari ini.")
        return

    all_sheet_emails = []
    if df is not None and "EMAIL" in df.columns:
        all_sheet_emails = [
            str(e).strip() for e in df["EMAIL"].dropna().unique()
            if str(e).strip() and "@" in str(e)
        ]

    # Gunakan email CC yang didefinisikan di environment variable (broadcast), atau default semua email di Sheet
    if args.no_cc:
        base_cc = []
    elif cc_emails:
        base_cc = cc_emails
        print(f"   CC (custom/env): {base_cc}")
    else:
        base_cc = all_sheet_emails
        print(f"   CC (semua karyawan di Sheet): {len(base_cc)} email")

    for _, row in birthdays.iterrows():
        name = str(row["NAMA"]).strip()
        nopeg = str(row.get("NOPEG", "")).strip()
        unit = str(row.get("UNIT", "")).strip()
        jabatan = str(row.get("JABATAN", "")).strip()
        to_email = str(row["EMAIL"]).strip()
        print(f"-> Ulang tahun hari ini: {name} (NOPEG: {nopeg}, UNIT: {unit}, JABATAN: {jabatan}) ({to_email})")

        safe_filename = "".join(c for c in name if c.isalnum() or c in " _-").strip().replace(" ", "_")
        card_path = generate_card(
            name=name,
            output_path=os.path.join(OUTPUT_DIR, f"{safe_filename}.jpg"),
            nopeg=nopeg,
            unit=unit,
            jabatan=jabatan
        )

        # Hapus email penerima dari CC agar penerima tidak kena CC kartunya sendiri
        cc_for_this = [c for c in base_cc if c.lower() != to_email.lower()]

        if args.dry_run:
            print(f"   [dry-run] Kartu dibuat di {card_path}, email TIDAK dikirim.")
            print(f"   [dry-run] To: {to_email}, CC: {cc_for_this}")
            continue

        if not from_email or not app_password:
            print("ERROR: GMAIL_ADDRESS / GMAIL_APP_PASSWORD belum diset.", file=sys.stderr)
            sys.exit(1)

        try:
            msg = build_email(name, to_email, cc_for_this, from_email, card_path)
            send_email(msg, from_email, app_password, to_email, cc_for_this)
            print(f"   Email terkirim ke {to_email} (CC: {cc_for_this})")
        finally:
            if os.path.exists(card_path):
                os.remove(card_path)
                print(f"   Kartu dibersihkan: {card_path}")


if __name__ == "__main__":
    main()

