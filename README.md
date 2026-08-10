# Sistem Ucapan Ulang Tahun Otomatis — Learning Center Unit, Dinas Cabin

Sistem ini berjalan sendiri setiap hari: baca data karyawan dari Google
Sheets, cek siapa yang ulang tahun hari ini, buatkan kartu ucapan dengan nama otomatis,
lalu kirim email lewat Gmail — semua gratis, tanpa server, tanpa birokrasi IT Pusat.

## Isi folder

```
greetings/
├── .github/workflows/birthday-email.yml   <- jadwal harian (GitHub Actions)
├── generate_card.py                       <- tempel nama ke kartu ucapan (Pillow)
├── send_birthday_emails.py                <- baca sheet, cek ulang tahun, kirim email
├── requirements.txt
├── fonts/LiberationSans-Bold.ttf          <- font untuk nama (mirip Arial, dibundel biar aman)
└── template/card_template.jpg             <- template kartu ucapan
```

## Langkah Setup (sekali saja)

### 1. Siapkan Google Sheets

1. Buat Google Sheet baru dengan kolom **persis** seperti ini (baris pertama = header):

   | NOPEG | NAMA | TANGGAL LAHIR | UNIT | JABATAN | EMAIL |
   |-------|------|---------------|------|---------|-------|

   - `TANGGAL LAHIR` harus berupa format tanggal (Format > Number > Date), bukan teks.
   - `EMAIL` adalah email kantor karyawan (yang akan menerima kartu).

2. Isi data karyawan. Kalau ada karyawan baru/resign, admin unit tinggal
   tambah/hapus baris — tidak perlu sentuh kode sama sekali.

3. Publish sheet ini sebagai CSV:
   - Buka sheet → **File > Share > Publish to web**
   - Pilih sheet yang sesuai → pilih format **Comma-separated values (.csv)**
   - Klik **Publish**, lalu copy link yang muncul (bentuknya seperti
     `https://docs.google.com/spreadsheets/d/e/xxxxx/pub?output=csv`)
   - Simpan link ini — nanti dipakai sebagai secret `SHEET_CSV_URL`.

### 2. Siapkan Gmail

1. Pastikan akun Gmail pengirim sudah aktifkan **2-Step Verification**.
2. Buka **myaccount.google.com > Security > 2-Step Verification > App passwords**.
3. Buat App Password baru (beri nama misalnya "Birthday Bot").
   Google akan kasih 16 digit kode — copy dan simpan.

### 3. Upload folder ini ke GitHub (repo private)

1. Buat repository baru di GitHub, **set sebagai Private**.
2. Upload semua isi folder ke repo tersebut.

### 4. Masukkan Secrets di GitHub

Di repo GitHub → **Settings > Secrets and variables > Actions > New repository secret**,
tambahkan 4 secret ini:

| Nama Secret          | Isi                                                              |
|-----------------------|------------------------------------------------------------------|
| `SHEET_CSV_URL`       | Link CSV dari langkah 1.3                                        |
| `GMAIL_ADDRESS`       | Email Gmail pengirim                                              |
| `GMAIL_APP_PASSWORD`  | 16 digit App Password dari langkah 2.3 (tanpa spasi)              |
| `CC_EMAILS`           | (opsional) email yang mau di-CC, pisahkan koma jika lebih dari satu|

### 5. Selesai — sistem otomatis berjalan tiap hari

GitHub Actions akan otomatis bangun setiap hari, cek Google Sheets, dan kirim
email ke siapa pun yang ulang tahun hari itu. Tidak perlu PC nyala 24 jam,
tidak perlu server, 100% gratis.

## Cara tes lokal

Set environment variables dulu (jalankan 1x setiap buka terminal baru):

```powershell
$env:GMAIL_ADDRESS="your-email@gmail.com"
$env:GMAIL_APP_PASSWORD="xxxxxxxxxxxxxxxx"
$env:SHEET_CSV_URL="https://docs.google.com/.../pub?output=csv"
```

### Kirim langsung ke 1 orang (testing tanpa CC)

```powershell
python send_birthday_emails.py --force-name "NAMA KARYAWAN" --force-email "email@tujuan.com" --no-cc --ignore-schedule
```

### Cek siapa yang ulang tahun hari ini (tanpa kirim email)

```powershell
python send_birthday_emails.py --dry-run
```

### Kirim ke semua yang ulang tahun hari ini

```powershell
python send_birthday_emails.py
```

### Tes otomatis kirim di jam tertentu (lokal)

```powershell
$target = Get-Date "07:00:00"
$wait = ($target - (Get-Date)).TotalSeconds
Write-Host "Menunggu $([math]::Round($wait)) detik..."
Start-Sleep -Seconds $wait
python send_birthday_emails.py
```

Ganti `"07:00:00"` ke jam yang diinginkan. PC harus tetap nyala sampai jam tersebut.

## Menyesuaikan posisi/ukuran nama di kartu

Kalau suatu saat template kartu diganti, buka `generate_card.py` dan ubah nilai
`NAME_CENTER_X`, `NAME_CENTER_Y`, `MAX_NAME_WIDTH` sesuai posisi teks "Dear" di
template yang baru.
