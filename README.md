# Business AI Analyst — MVP Gratis — Streamlit Cloud Edition 1.1

Aplikasi web untuk menganalisis Excel **Detailed Sales** (terutama format NICESO) memakai Python, SQLite, Streamlit dan Plotly. Dirancang untuk file besar dengan pembacaan Excel **streaming**, bukan memuat 200 ribu baris ke DataFrame sekaligus.

**Tidak ada data perusahaan asli di dalam source code ini.** File `.xlsx` harus diunggah sendiri oleh pengguna yang memiliki izin.

## Yang sudah berfungsi

- Upload **satu atau beberapa** file `.xlsx` / `.csv` dengan struktur Detailed Sales serupa (maksimum 90 MB total pada antarmuka gratis).
- Temukan header Excel otomatis, meski ada judul laporan pada baris-baris awal (misalnya baris 6).
- Data transaksi disalin ke database SQLite **sementara, per sesi pengguna**, tanpa kolom identitas pelanggan dan nama karyawan/kasir.
- Analisis omzet sebelum pajak, omzet termasuk pajak, gross profit, margin, cost, unit, diskon dan transaksi unik.
- Dashboard per jam (jika 1 hari), atau per tanggal (jika banyak hari).
- Cabang teratas, produk, kategori, brand, supplier, filter dan pencarian melalui pertanyaan bahasa Indonesia.
- Ekspor data agregat ke CSV (Excel-compatible) dan preview detail per halaman.
- Mode **Analyst lokal gratis** = parser pertanyaan + perhitungan SQL, tanpa LLM; opsi **Gemini generatif** bila pemilik menambahkan API key & pengguna mengizinkan.
- Mode **Data Demo** sintetis sehingga pemilik bisa mencoba aplikasi sebelum mengunggah file sebenarnya.
- Deteksi **file identik** berdasarkan SHA-256 untuk menghindari penghitungan ganda jika file yang sama ikut dipilih dua kali.

### Batas versi pertama

- **Belum ada** akun/login multi-role, basis data persisten, database lintas sesi, impor `.xls` lama, jadwal otomatis, atau integrasi WhatsApp/POS.
- Bukan sistem audit keuangan. Profit memakai kolom sumber **Gross Profit**, omzet memakai sumber **Sales**.
- Perbandingan periode belum otomatis memisahkan hari tak lengkap. File identik terdeteksi, tetapi **file berbeda yang berisi transaksi tumpang tindih belum otomatis dideduplikasi**.
- Cloud gratis memiliki batas CPU/RAM/storage. File sebesar ~38MB telah dites diproses dalam ~22 detik di lingkungan pengujian lokal yang kuat; performa di hosting gratis bisa lebih lambat atau gagal jika resource habis.
- Sesi bisa hilang sewaktu server hibernasi/restart. Jangan gunakan sebagai arsip permanen.

## A. Jalankan sendiri di Windows

1. Instal **Python 3.11/3.12** dari https://www.python.org/downloads/ . Pastikan centang `Add Python to PATH`.
2. Extract ZIP source ini ke folder `Business_AI_Analyst`.
3. Buka Command Prompt / PowerShell pada folder tersebut:

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   streamlit run app.py
   ```

4. Browser akan membuka `http://localhost:8501`.
5. Klik **Gunakan Data Demo** atau upload Excel melalui sidebar.

## B. GRATIS 1 — Publikasikan ke Streamlit Community Cloud (disarankan)

**Langkah 1 — Buat repository GitHub**

1. Buka https://github.com/ lalu login/buat akun gratis.
2. Klik **New repository**, nama misalnya `business-ai-analyst`, pilih **Public** untuk aplikasi yang akan dibagikan bebas.
3. Klik **uploading an existing file**, upload **isi folder hasil ekstrak** (bukan file ZIP dan bukan folder pembungkus). Pastikan `app.py`, `requirements.txt`, `src/`, `.streamlit/config.toml`, `examples/` ada.
4. **JANGAN upload laporan Excel asli** (terutama yang memiliki KTP/NPWP/Phone). `.gitignore` tersedia, tetapi upload lewat browser tetap perlu diperiksa manual.

**Langkah 2 — Deploy**

1. Buka https://share.streamlit.io/ dan masuk menggunakan GitHub. Panduan paling sederhana tersedia di `DEPLOY_GRATIS.md`.
2. Pilih **Create app** > **Yup, I have an app**.
3. Isi **Repository** `username/business-ai-analyst`, **Branch** `main`, **Main file path** `app.py`.
4. Klik **Deploy** dan tunggu dependensi terinstal.
5. Setelah berhasil kamu memperoleh URL `https://nama-app.streamlit.app` yang bisa dikirim ke orang lain.

**Langkah 3 — Aktifkan AI generatif (opsional)**

1. Buat API key dari https://aistudio.google.com/apikey jika tersedia dan memenuhi syarat pada akun/negara kamu.
2. Di dashboard Streamlit App Settings > Secrets, isi (contoh):

   ```toml
   GEMINI_API_KEY = "KUNCI_KAMU"
   ```

3. Di halaman **AI Analyst**, pengguna harus **mencentang** Interpretasi Gemini untuk mengirim pertanyaan dan **hanya ringkasan agregat** ke penyedia AI.
4. Tanpa kunci API, menu Analyst tetap bisa menjawab pertanyaan bisnis dasar dengan SQL, **bukan chatbot LLM generatif**.

**Peringatan AI:** Kuota dan ketersediaan tier gratis Gemini dapat berubah. Pada paket gratis Gemini API, data yang dikirim dapat dipakai penyedia untuk meningkatkan produknya. **Jangan aktifkan Gemini gratis untuk data rahasia perusahaan jika tidak diizinkan.**

**Peringatan hosting:** Streamlit Community Cloud cocok untuk demo dan komunitas, bukan sistem ber-SLA; app bisa sleep dan limit resource bisa menyebabkan upload besar gagal. Bila file terlalu besar untuk cloud, jalankan pada komputer pribadi menggunakan alternatif C.

## C. GRATIS 2 — Jalankan di PC + Cloudflare Tunnel

Kalau kamu ingin orang lain mengakses aplikasi sambil **proses Excel berat dijalankan di PC milikmu**, gunakan komputer Windows sebagai server:

1. Jalankan aplikasi lokal dengan `streamlit run app.py` (port 8501).
2. Install `cloudflared`: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ .
3. Di terminal lain jalankan:

   ```powershell
   cloudflared tunnel --url http://localhost:8501
   ```

4. Salin URL `https://xxxx.trycloudflare.com` yang muncul, kirim ke pengguna.
5. Untuk tes terbatas, versi cloudflared terbaru mendukung `--allowed-mail alamat@email.com` supaya akses hanya untuk email tertentu.

Kekurangannya: **PC dan terminal harus tetap menyala**, URL sementara, Quick Tunnel untuk **testing/development**, bukan produksi.

## D. Alternatif lainnya

| Pilihan | Gratis? | Bisa menjalankan source Streamlit ini? | Catatan |
|---|---|---|---|
| Streamlit Community Cloud | Ya (dengan limit) | Ya, langsung | Direkomendasikan untuk demo publik |
| PC sendiri + Cloudflare Quick Tunnel | Ya (testing) | Ya, langsung | Server PC selalu hidup; URL sementara |
| GitHub Pages | Ya untuk site statis | **Tidak**, perlu tulis ulang ke HTML/JS | Tidak menjalankan Python server-side |
| Hugging Face Spaces | Kebijakan tergantung jenis Space/akun | Bisa dengan layanan compute yang didukung | Periksa status biaya sebelum deploy; static Spaces bukan host Python |

## Keamanan

- Meng-upload Excel ke **web app publik berarti file diproses di server penyedia**, bukan hanya di browser lokal.
- Detail identitas pelanggan seperti `Customer`, `Customer ID`, `KTP`, `NPWP`, `Address`, `Phone`, `Membership`, serta **nama kasir**, **tidak masuk database analitik**. Tetapi byte file sementara tetap lewat server untuk diproses.
- DB SQLite sesi berada di penyimpanan **sementara server**. Klik **Hapus Data Sesi** untuk menghapus; proses hosting juga dapat menghapusnya saat reboot. Tidak ada janji isolasi enterprise atau pemusnahan memori absolut.
- Data antar pengguna tidak sengaja digabung, karena setiap sesi membuat file database sendiri di direktori temp, dengan nama acak. Sistem ini belum memiliki autentikasi/isolasi organisasi yang diaudit untuk penggunaan produksi.
- Perhatikan kebijakan internal perusahaan, perlindungan data pribadi, dan izin sebelum memakai hosting publik gratis.

## Format minimal Excel

Wajib tersedia: **Completed Date**, **Store**, **Item**, **Qty**, **Sales**.

Yang lebih lengkap lebih baik: **Store Code**, **Completed Time**, **Sales Ref Code**, **SKU**, **Katagory Utama**, **Brand Name**, **Cost**, **Gross Profit**, **Sales (Inc Tax)**, **Status**.

Judul laporan sebelum header (contoh pada 5 baris pertama) bisa ditangani otomatis. Nama kolom sebagian dapat mengikuti alias Indonesia seperti `Tanggal`, `Cabang`, `Nama Produk`, `Omzet`, dan `Jumlah Terjual`.

## Definisi indikator

- **Omzet** = SUM(`Sales`) → **sebelum pajak**.
- **Omzet termasuk pajak** = SUM(`Sales (Inc Tax)`).
- **Laba kotor** = SUM(`Gross Profit`) yang ada di Excel.
- **Margin kotor (%)** = Laba kotor / Omzet sebelum pajak × 100%.
- **Unit** = SUM(`Qty`).
- **Transaksi unik** = COUNT(DISTINCT (`Store Code`, `Sales Ref Code`)), bukan jumlah baris barang.
- **Diskon agregat** = SUM(`Unit Discount` × `Qty`) berdasarkan definisi kolom dalam laporan.

## File utama

- `app.py` — antarmuka Streamlit & navigasi.
- `src/engine.py` — parser XLSX/CSV streaming, pembersihan, query SQLite.
- `src/assistant.py` — asisten analitik lokal & Gemini (opsional).
- `examples/demo_sales.csv` — data simulasi, **bukan data milik perusahaan**.
- `tests/test_engine.py` — pengujian perhitungan, pertanyaan, privasi, dan file identik.
- `DEPLOY_GRATIS.md` — panduan GitHub + Streamlit Cloud dalam bahasa Indonesia.
- `.github/workflows/tes-otomatis.yml` — tes otomatis gratis saat source diunggah ke GitHub.

## Menjalankan tes

```bash
python -m unittest discover -s tests -v
```

## Sumber layanan publik (cek ulang jika kebijakan berubah)

- Streamlit Cloud: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Streamlit resource/hibernation: https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- Gemini pricing & privacy: https://ai.google.dev/gemini-api/docs/pricing
- Cloudflare Quick Tunnel: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
- GitHub Pages static-only: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
