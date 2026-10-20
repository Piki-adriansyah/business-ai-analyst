# PANDUAN UPLOAD WEBSITE GRATIS — STREAMLIT CLOUD

**Target:** membuat website Business AI Analyst yang bisa dipakai lewat HP/PC siapa saja melalui link. **Tidak perlu membeli domain atau VPS.** Hanya butuh akun GitHub dan akun Streamlit gratis.

## SEBELUM UPLOAD: cek keamanan

- **Jangan upload Excel asli `detailed_sales_....xlsx`** ke GitHub. File penjualan kamu mengandung kolom identitas pelanggan dan angka internal bisnis.
- ZIP ini sudah berisi **kode aplikasi dan data demo buatan**, tanpa dataset bisnis asli.
- GitHub repo public = semua orang bisa melihat source code; bukan berarti mereka otomatis bisa melihat Excel pribadi yang diupload lewat aplikasi.
- Untuk data perusahaan asli, minta persetujuan internal sebelum mengupload ke Streamlit Community Cloud karena file melewati server pihak ketiga.

## LANGKAH 1 — BUAT REPOSITORY DI GITHUB

1. Buka https://github.com dan login.
2. Klik **+** > **New repository**.
3. Isi nama repository **`business-ai-analyst`**.
4. Pilih **Public** (agar kode dapat diakses bebas dan aplikasinya mudah dibagikan).
5. Klik **Create repository**.
6. Ekstrak ZIP sampai terlihat file `app.py` dan `requirements.txt`.
7. Pada halaman repository, klik **uploading an existing file** / **Add file** > **Upload files**.
8. Drag **isi folder** aplikasi (bukan ZIP dan bukan folder induknya). Pastikan `app.py`, `src/`, `examples/`, `requirements.txt` di root repository. Sertakan juga folder `.streamlit/` (tersembunyi pada beberapa perangkat).
9. Klik **Commit changes**. Jangan mengupload file pribadi.

**Jika folder `.streamlit` tidak ikut karena tersembunyi**, pilih `View > Show > Hidden items` di File Explorer Windows atau buat file `.streamlit/config.toml` di GitHub dengan isi yang sudah ada dalam paket.

## LANGKAH 2 — DEPLOY KE STREAMLIT COMMUNITY CLOUD

1. Buka https://share.streamlit.io dan masuk menggunakan akun GitHub.
2. Klik **Create app** > **Yup, I have an app**.
3. Isi:
   - Repository: `USERNAME_GITHUB/business-ai-analyst`
   - Branch: `main`
   - Main file path: **`app.py`**
   - URL: pilih nama yang tersedia, misalnya `bisnis-ai-analyst-demo`
4. Klik **Deploy**.
5. Tunggu proses instalasi dependensi selesai. Setelah berhasil, situs akan memiliki alamat seperti `https://bisnis-ai-analyst-demo.streamlit.app`. **Ini contoh pola alamat; URL aktual mengikuti yang diberikan Streamlit.**
6. Pada **App settings > Sharing**, pastikan aplikasi **Public** bila memang ingin semua orang mengaksesnya.

## LANGKAH 3 — COBA DENGAN DATA DEMO

1. Buka URL publik aplikasimu (bisa dari HP lain).
2. Klik **Gunakan Data Demo**.
3. Lihat menu **Ringkasan**, **Cabang**, **Produk**, **Kategori & Brand**, dan **AI Analyst**.
4. Uji pertanyaan "Top 10 cabang berdasarkan omzet".
5. Semua orang bisa memakai data demo tanpa mengupload apa pun.

## LANGKAH 4 — BACA EXCEL ASLI (HANYA JIKA DIIJINKAN)

1. Pilih file Excel di uploader sidebar.
2. Klik **Proses Data**. Laporan sekitar 38 MB dengan 200 ribu baris membutuhkan beberapa puluh detik atau lebih; hasil bergantung RAM/CPU hosting gratis.
3. Data asli diproses sementara di server aplikasi dan tidak otomatis ditambahkan ke repository GitHub.
4. Klik **Hapus Data Sesi** ketika selesai.

**Perhatian:** aplikasi publik belum memiliki fitur login multi-role atau isolasi data untuk standar enterprise. Jika tidak boleh mengirim file internal ke hosting pihak ketiga, jalankan pada komputer perusahaan sendiri dan bagikan hanya di jaringan internal.

## OPSIONAL — GEMINI GENERATIF

Aplikasi **tidak memerlukan Gemini** untuk dashboard, perhitungan, atau tanya-jawab analitik dasar. Jika ingin penjelasan generatif:

1. Buat API key sesuai kebijakan https://ai.google.dev/gemini-api/docs/api-key .
2. Buka aplikasi di Streamlit > App settings > Secrets.
3. Tambahkan `GEMINI_API_KEY = "isi-api-key-anda"`.
4. Simpan. Pengguna bisa memilih opsi Gemini di menu AI Analyst.

**Jangan meletakkan API key ke repository**, dan jangan mengirim data perusahaan rahasia ke layanan AI tanpa dasar izin dan memahami kebijakan datanya. Kuota/fitur gratis dapat berubah.

## JIKA FREE HOSTING TIDAK KUAT

**Jalur alternatif: komputer sendiri + Cloudflare Quick Tunnel** untuk uji terbatas:

1. Buka `JALANKAN_WINDOWS.bat` pada komputer yang terus menyala.
2. Pasang `cloudflared` dari https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ .
3. Di CMD baru jalankan: `cloudflared tunnel --url http://localhost:8501`.
4. Bagikan URL `.trycloudflare.com` sementara yang muncul.

Quick Tunnel bersifat **sementara dan ditujukan untuk development/testing**; tidak cocok untuk produksi dengan data sensitif tanpa pengamanan ekstra.

## LINK DOKUMENTASI RESMI

- Deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Pengaturan berbagi: https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
- File layout: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization
- Keterbatasan gratis: https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
