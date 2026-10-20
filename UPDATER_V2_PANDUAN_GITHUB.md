# UPDATE BUSINESS AI ANALYST V1 KE V2 - AMAN TANPA MENGGANTI LINK

Repository kamu: https://github.com/Piki-adriansyah/business-ai-analyst
Website existing: https://business-ai-analyst-piki.streamlit.app

## 0. Penting: jangan hapus website dan jangan upload Excel perusahaan

Updater **mengganti source code**, bukan mengganti domain atau repository. Excel asli tetap hanya boleh diupload melalui aplikasi bila sudah mendapat izin. Isi ZIP ini hanya source dan data demo sintetis.

## 1. Backup versi yang sekarang sebelum upgrade

1. Buka repository GitHub di atas.
2. Klik dropdown **main** di atas daftar file.
3. Ketik `backup-v1`, pilih **Create branch: backup-v1 from main**.
4. Switch kembali ke `main`.
5. Buat branch `v2-test` dari main untuk menguji updater.

Dengan cara ini, versi lama tidak ikut tertimpa ketika kamu menguji V2.

## 2. Cara mengupload V2 yang PALING AMAN (GitHub Desktop)

Github Desktop gratis: https://desktop.github.com/

1. Instal GitHub Desktop di Windows dan login akun GitHub `Piki-adriansyah`.
2. Pilih **File > Clone repository** lalu `Piki-adriansyah/business-ai-analyst`.
3. Pilih branch `v2-test` (branch sudah dibuat di langkah 1).
4. **Ekstrak** ZIP updater. Jangan upload file `.zip` langsung ke repository.
5. Dari folder hasil ekstrak, copy SEMUA isinya (termasuk `.streamlit` dan `.github`) ke folder repository lokal. Pilih **Replace/Replace files in destination**.
6. GitHub Desktop akan menampilkan daftar file berubah. Pastikan Excel asli tidak ada dalam daftar commit.
7. Isi commit message `Upgrade Business AI Analyst V2` lalu klik **Commit to v2-test**.
8. Klik **Push origin**.

Alternatif jika sudah menggunakan Git CLI (jangan jalankan di folder lain):

```powershell
git clone https://github.com/Piki-adriansyah/business-ai-analyst.git
cd business-ai-analyst
git checkout -b v2-test
# SALIN isi ZIP updater ke folder ini, ganti file lama.
git add -A
git commit -m "Upgrade Business AI Analyst V2"
git push -u origin v2-test
```

**Catatan GitHub web:** unggah source di branch `v2-test` menggunakan Add file > Upload files bila tersedia. Bila tabrakan nama file lama menghambat upload/overwrite, gunakan GitHub Desktop agar berkas lama terganti dengan benar. Jangan memilih Delete repository.

## 3. Cek CI di GitHub

Buka tab **Actions** pada repository > pilih `Uji Business AI Analyst V2`. Tunggu unit tests selesai (centang hijau).

Jika Actions belum berjalan, cek bahwa `.github/workflows/tes-otomatis.yml` sudah masuk GitHub; folder bertitik terkadang terlewat saat mengupload manual di Windows.

## 4. Deploy V2 TERPISAH untuk pengujian (rekomendasi)

1. Buka https://share.streamlit.io > Create app > Deploy a public app from GitHub.
2. Repository: `Piki-adriansyah/business-ai-analyst`.
3. Branch: `v2-test`.
4. Main file path: `app.py`.
5. Pilih subdomain test lain yang tersedia (misalnya `business-ai-analyst-piki-v2-test` jika tersedia).
6. Deploy, lalu coba tombol **Gunakan Data Demo** dan setiap menu.

Ini aplikasi test, tidak akan mengganti alamat produksi yang sekarang.

## 5. Cek fitur V2 sebelum merge

- Buka Ringkasan, cek 8 KPI, grafik penjualan, top cabang dan kategori.
- Buka Cabang, Produk, Kategori & Brand, Data Explorer, AI Analyst, Panduan (fitur V1).
- Buka Advanced Analytics, ABC Produk, Dataset Manager, dan Laporan (fitur baru).
- Di Laporan, klik **Buat laporan PDF & Excel**, unduh dan buka dua file.
- Coba upload 2 Excel dengan mode **Ganti dataset**, cek jumlah baris dan tanggal.
- Coba upload file baru dengan mode **Tambahkan**, cek dataset tidak hilang.
- Coba mengunggah file yang sama; sistem seharusnya melewati file identik.
- Klik Hapus Data Sesi, pastikan kembali ke landing page.

## 6. Mengganti versi online tanpa mengganti URL

Jika semuanya berhasil:

1. GitHub: dari branch `v2-test`, klik **Contribute > Open pull request**.
2. Base branch `main` dan compare branch `v2-test`.
3. Review perubahan lalu klik **Merge pull request**.
4. Kembali ke https://business-ai-analyst-piki.streamlit.app
5. Tunggu Streamlit menarik commit GitHub. Perubahan `requirements.txt` memicu instal ulang dependency (bisa beberapa menit).
6. Refresh browser (Ctrl+F5) apabila masih menampilkan tampilan lama.

Streamlit memantau GitHub dan menampilkan update setelah commit; tidak perlu buat domain lagi.

## 7. Jika ingin password di website

Buka https://share.streamlit.io > My apps > aplikasi kamu > Settings > Secrets. Tambahkan:

```toml
APP_ACCESS_PASSWORD = "masukkan_password_unik_panjang"
# opsional, fitur penjelasan AI generatif saja:
# GEMINI_API_KEY = "kunci_dari_penyedia_AI"
```

Kemudian reboot aplikasi bila diperlukan. Jangan menyimpan password/API key di source atau screenshot publik. Password ini dibagi bersama kepada pengguna yang diberi izin; belum memiliki akun pengguna individual.

## 8. Rollback jika ditemukan masalah

Branch `backup-v1` menyimpan source awal. Buat pull request dari branch itu ke main (atau gunakan revert commit V2), lalu tunggu app otomatis mengupdate. Jangan menghapus site Streamlit; URL tetap sama.

## Catatan penting

- Source V2 dibuat dari paket V1 asli yang tersedia dalam percakapan, dan diverifikasi sesuai struktur repository di screenshot. Koneksi langsung untuk membaca commit terbaru di GitHub belum tersedia, sehingga bila kamu mengubah kode setelah upload V1, review diff sebelum merge.
- Pemrosesan file 38 MB telah diuji **lokal**, tapi performa dan reliabilitas Cloud bergantung pada RAM/CPU/limit gratis dan jumlah pengunjung.
- File identik dihalangi; data dengan transaksi yang bertumpang tindih namun berasal dari file berbeda perlu diperiksa karena tidak otomatis disatukan per nomor transaksi.
