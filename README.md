# Business AI Analyst V2 — Streamlit Community Cloud

**Versi updater dari Business AI Analyst V1.** Source untuk repository:
`https://github.com/Piki-adriansyah/business-ai-analyst`

Aplikasi gratis untuk menganalisis Excel/CSV `Detailed Sales`, berdasarkan perhitungan SQLite yang dapat diaudit. AI generatif hanya opsional; aplikasi analitik dasar **tidak membutuhkan API**.

## Apa yang baru pada V2?

| Modul | Deskripsi |
|---|---|
| Ringkasan | Dashboard KPI profesional, tren per jam/harian, kontribusi kategori, top cabang & produk, insight otomatis |
| Cabang | Omzet, laba kotor, qty, transaksi, margin dan selisih antarperiode |
| Produk | Peringkat, margin dan ABC/Pareto berbasis **semua SKU** |
| Kategori & Brand | Breakdown berdasarkan kategori, brand, dan supplier |
| Advanced Analytics | Perbandingan periodik dengan validasi kelengkapan, sinyal anomali, pemeriksaan kualitas, produktivitas |
| Data Explorer | Preview baris non-PII dengan pagination, ekspor CSV halaman |
| AI Analyst | Tanya-jawab bahasa Indonesia berdasarkan query terverifikasi + Gemini opsional dengan persetujuan |
| Laporan | Download **PDF dan Excel** berisi agregat KPI, rangking, kualitas data dan referensi sumber |
| Dataset | Riwayat impor, jumlah baris, duplikasi berdasarkan file SHA-256, tambah/ganti dataset |
| Panduan | Definisi dan batasan metrik serta keamanan data |

Menu V1 `Ringkasan`, `Cabang`, `Produk`, `Kategori & Brand`, `Data Explorer`, `AI Analyst`, dan `Panduan` tetap tersedia.

## Mulai cepat di Streamlit Community Cloud

Repo publik sudah ada; cukup **update source yang sama**, tidak perlu buat repository baru.

1. Sebelum perubahan, buat branch cadangan `backup-v1` dari `main`.
2. Ekstrak ZIP ini, kemudian salin **semua isi folder**, bukan file ZIP-nya, ke checkout lokal repo `business-ai-analyst`. Ganti file lama jika diminta.
3. Push ke branch uji `v2-test`. Jalankan tes dan deploy uji `v2-test` dengan `app.py`.
4. Bila berhasil, merge perubahan ke `main`. Streamlit Cloud mendeteksi perubahan dan mengupdate website sebelumnya secara otomatis.
5. Jika `requirements.txt` diubah, Streamlit menginstal dependency tambahan; proses pertama bisa lebih lama.

Baca **`UPDATER_V2_PANDUAN_GITHUB.md`** untuk langkah sangat rinci tanpa perlu VPS.

## Menjalankan di komputer Windows

Ekstrak ZIP, klik `JALANKAN_WINDOWS.bat`, atau jalankan:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Akses `http://localhost:8501`.

## Cara mengunggah banyak file

- Format `.xlsx` dan `.csv`, termasuk header tabel yang tidak berada di baris pertama.
- Maksimal 12 file; per file 65 MB, total 95 MB per proses. Dataset gabungan maksimal 850 ribu baris (untuk kapasitas hosting gratis).
- Pilih **Ganti dataset** bila ingin dataset baru, **Tambahkan** untuk file dari tanggal berikutnya.
- SHA-256 mencegah **file identik** terimport dua kali. **Transaksi beririsan dalam file berbeda belum otomatis dihapus**, karena beberapa baris dengan nomor transaksi sama memang sah; cek rekap sumber.
- Data demo harus diganti, bukan ditambahkan ke dataset real.
- Nilai numerik pada file sumber dibaca menurut format yang didukung; cek hasil dengan laporan resmi perusahaan.

## Definisi metrik

- **Omzet** = `SUM(Sales)` (sebelum pajak).
- **Omzet termasuk pajak** = `SUM(Sales (Inc Tax))`.
- **Laba kotor** = `SUM(Gross Profit)` sumber; bukan laba bersih.
- **Margin laba kotor** = `100 × SUM(Gross Profit) / SUM(Sales)`.
- **Transaksi** = jumlah unik gabungan `Store Code` dan `Sales Ref Code` (bila tersedia).
- **Growth** hanya jika data aktif dan periode pembanding sama-sama memiliki setiap tanggal dalam rentangnya; jika tidak lengkap, sistem menampilkan "tidak tersedia".
- **Anomali** menggunakan robust z-score (median/MAD) minimum 7 tanggal, berupa sinyal statistik, bukan bukti kesalahan.
- **ABC** ditentukan oleh kontribusi penjualan kumulatif semua SKU, dengan batas sekitar 80%/95%.
- **GP mismatch** hanya menunjukkan bahwa `Sales - Cost` tidak sama dengan `Gross Profit` menurut kolom laporan; ini **bukan** bukti perhitungan salah karena basis pajak, diskon, dan komponen Cost bisa berbeda.

## Privasi & keamanan — penting

**Versi ini bukan SaaS enterprise multi-akun.** Infrastruktur gratis punya batasan dan pengelola harus mematuhi izin penggunaan data.

1. Jangan commit Excel asli, file `.env`, atau `.streamlit/secrets.toml` ke GitHub publik.
2. Parser hanya menyalin kolom bisnis yang ada pada daftar putih. Kolom pelanggan, KTP, NPWP, telepon, dan pegawai tidak disalin ke database analitik.
3. **File upload diproses di server Streamlit**, bukan hanya di browser; per-sesi menggunakan SQLite temporer. Tidak ada klaim isolasi tingkat perusahaan, enkripsi end-to-end terkelola, atau penyimpanan permanen.
4. Mode publik (tanpa password) memperbolehkan setiap pengunjung menggunakan data demo dan mengunggah file mereka dengan persetujuan. Jika ingin membatasi akses, atur `APP_ACCESS_PASSWORD` pada Secrets. Ini password bersama, **bukan login individual dengan MFA**.
5. Laporan PDF/Excel hanya berisi hasil **agregat bisnis**, bukan tabel pelanggan. API generatif tidak menerima file mentah, hanya pertanyaan dan hasil agregat dengan opt-in pengguna.
6. Data hanya tersedia selama sesi dan bisa hilang akibat sleep/restart. Hapus data sesi setelah selesai. Jangan jadikan ini database produksi permanen.
7. Jika perusahaan mewajibkan kontrol akses audit atau residensi data, gunakan hosting privat dan sistem autentikasi yang sesuai.

## Config Secrets opsional

Di Streamlit > Manage app > Settings > Secrets, isi misalnya:

```toml
APP_ACCESS_PASSWORD = "ganti_password_panjang_yang_unik"
# Hanya bila memang ingin penjelasan AI generatif:
# GEMINI_API_KEY = "kunci-pribadi-di-streamlit-secrets"
```

**Jangan upload `secrets.toml` asli ke GitHub.** Kunci Gemini tidak diperlukan untuk chat deterministik.

## Testing

```bash
python -m unittest discover -s tests -v
```

Unit tests mencakup regresi V1, dimensi SQL, ABC, periode lengkap, anomali, Q&A, ekspor PDF/Excel, injeksi CSV, batas upload, dan pengamanan input. UI interaktif di server Streamlit perlu diuji setelah deployment.
