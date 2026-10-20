# Change Log V2.0

Upgrade berbasis `Business_AI_Analyst_Streamlit_Siap_Deploy_Gratis.zip` (baseline V1 yang tersimpan sebelum update).

## Dipertahankan
- Import Excel/CSV streaming untuk file Detailed Sales, auto header, multi-sheet, multi-file.
- Database sesi SQLite non-PII, anti import hash identik, indeks dan pagination.
- Menu Ringkasan/Cabang/Produk/Kategori & Brand/Data Explorer/AI Analyst/Panduan.
- Analisis terverifikasi SQL dan integrasi penjelasan Gemini opsional.
- Data demo sintetis dan deployment Streamlit Cloud.

## Ditambahkan
- UI V2 professional: hero, KPI cards, visual chart, filter brand/supplier, tema terang/gelap.
- Mode multi-file Tambahkan/Ganti dataset, backup kopi database sebelum append.
- Margin, laba kotor, produktivitas cabang, breakdown supplier.
- Advanced analytics: perbandingan 2 periode lengkap, kontributor selisih cabang, sinyal anomali (min 7 hari), audit kualitas.
- Analisis ABC semua SKU.
- Chat pertanyaan lanjut: ABC, kualitas data, anomali, comparison, ranking margin.
- Ekspor laporan PDF & Excel berisi agregat non-PII.
- Validasi jumlah/ukuran file, opsi password bersama melalui secrets, pembatasan session cache, XML Zip guard, sanitasi CSV/XLSX.
- Tes regresi + tes V2 pada GitHub Actions.

## Batas yang belum diklaim
- Tidak ada database permanen, login multi-user individual, audit trail enterprise, sinkronisasi real-time, dan deduplikasi antar-file *berbeda* dengan transaksi yang overlap.
- Upload diproses di server Streamlit Cloud; jangan upload data rahasia tanpa izin.
- Mode AI generatif tidak aktif tanpa key; mode pertanyaan analitik lokal tetap gratis.
