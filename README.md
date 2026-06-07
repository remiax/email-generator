# Email Generator (Microsoft domains)

Generator alamat email realistis untuk domain Microsoft:
**hotmail.com, outlook.com, live.com, msn.com**.

Dibuat dari gabungan banyak file daftar nama yang sudah dibersihkan & di-unik-kan.

## Isi

| File | Keterangan |
|---|---|
| `build_names.py` | Menggabungkan semua file sumber nama → 2 file bersih unik |
| `email_generator.py` | Generator email (format valid + realistis + mampu miliaran) |
| `data/first_names.txt` | 169.721 nama depan unik (hasil `build_names.py`) |
| `data/last_names.txt` | 174.533 nama belakang unik (hasil `build_names.py`) |
| `data/first_names_weighted.tsv` | nama depan + bobot popularitas |
| `data/last_names_weighted.tsv` | nama belakang + bobot (jumlah sensus) |

File sumber asli (`first_names.all.txt`, `firstnames.csv`, `last_names.all.txt`,
`last-names.txt`, `surnames.csv`) tetap disimpan sebagai bahan mentah.

## Cara pakai

### 1. Bangun daftar nama bersih (sekali saja)

```bash
python build_names.py
```

Proses pembersihan tiap nama: buang aksen (José → jose), huruf kecil semua,
hanya simpan huruf a–z, panjang 2–20, lalu di-unik-kan & diurutkan.

### 2. Hasilkan email

```bash
# 20 email ke layar
python email_generator.py 20

# 1 juta email ke file
python email_generator.py 1000000 -o emails.txt

# 5 miliar email ke file (streaming, hemat memori)
python email_generator.py 5000000000 -o miliar.txt

# pilih domain tertentu
python email_generator.py 100 --domains outlook.com,live.com

# hasil bisa diulang (seed) + dijamin unik (untuk jumlah wajar)
python email_generator.py 100000 --seed 42 --dedupe -o unik.txt

# mode seragam: lebih beragam (semua nama sama peluang), kurang "human"
python email_generator.py 50 --uniform

# uji validitas format
python email_generator.py --self-test
```

### Opsi penting

| Opsi | Default | Fungsi |
|---|---|---|
| `count` | 1000 | jumlah email |
| `-o, --output` | layar | file keluaran |
| `--domains` | 4 domain MS | daftar domain (pisah koma) |
| `--seed` | acak | seed agar hasil bisa diulang |
| `--min-len` / `--max-len` | 6 / 30 | panjang local-part (sebelum `@`) |
| `--uniform` | mati | sampling seragam (lebih beragam, kurang realistis) |
| `--dedupe` | mati | jamin unik (pakai memori) |
| `--self-test` | — | cek persentase format valid |

## Kenapa "bagus" / sedikit invalid

Local-part (bagian sebelum `@`) **selalu dibangun sesuai aturan akun Microsoft**:

- diawali huruf, diakhiri huruf/angka;
- hanya huruf, angka, titik `.`, garis bawah `_`, strip `-`;
- tanpa pemisah berurutan / di awal / di akhir;
- panjang 1–64 karakter.

`--self-test` pada 300.000 sampel = **100% format valid (0 invalid)**.

### Realistis / "human" (sampling berbobot frekuensi)

Secara default nama **tidak** diambil seragam, melainkan **berbobot frekuensi
nyata**, jadi nama umum mendominasi seperti pada populasi manusia:

- Nama belakang ditimbang dengan **jumlah sensus** (dari `surnames.csv`),
  mis. `smith`, `johnson`, `williams` jauh lebih sering muncul.
- Nama depan ditimbang dengan **popularitas lintas-negara** (dari
  `firstnames.csv`), mis. `maria`, `anna`, `john`, `alexander`.
- Pola username meniru kebiasaan asli (±52% memakai angka/tahun lahir):
  `mary.soto`, `alexander.miller`, `jean.nicosia1971`, `rita.linnell`,
  `semele.anderson1989`, `abenson`.
- Domain dibagi proporsi realistis: hotmail 42% / outlook 34% / live 16% /
  msn 8% (uji 2 juta: persis sesuai).

Pakai `--uniform` bila ingin keberagaman maksimum (semua nama berpeluang sama).

## Mampu miliaran

- Nama depan × belakang = **±29,6 miliar** kombinasi, dikali banyak pola &
  variasi angka → ruang praktis **triliunan** alamat unik.
- Mode streaming menulis langsung ke file (tidak menahan semua di memori).
- Kecepatan ±150.000 email/detik (mode realistis berbobot).
- Tingkat duplikat tanpa `--dedupe`:
  - mode realistis (default): **±4%** pada 2 juta (karena memusat ke nama umum);
  - mode `--uniform`: **±0,04%** (ruang jauh lebih lebar).
- Untuk benar-benar miliaran alamat **unik**: gunakan `--uniform` (ruang
  terlebar), atau `--dedupe` untuk jumlah wajar, atau terima ±beberapa persen
  duplikat pada mode realistis.

## Penting: "valid format" vs "kotak surat ada"

Generator ini menjamin **format** valid dan **realistis**, tetapi **tidak**
menjamin alamat benar-benar terdaftar/aktif. Untuk memastikan kotak surat ada,
diperlukan verifikasi terpisah (mis. pengecekan SMTP/API). Gunakan secara
bertanggung jawab dan sesuai hukum (anti-spam, privasi, dll).
