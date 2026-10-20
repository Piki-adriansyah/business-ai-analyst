"""Business AI Analyst: streamed XLSX/CSV importer and read-only SQLite analytics.

Uploads are processed within the Streamlit user's temporary session workspace.
Only business fields are copied: customer identifiers, names, IDs and phone are ignored.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import sqlite3
import tempfile
import time
import zipfile
from collections import Counter
from contextlib import closing, contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import BinaryIO, Callable, Iterator
from xml.etree import ElementTree as ET

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
CELL = '{'+NS+'}c'
ROW = '{'+NS+'}row'
VALUE = '{'+NS+'}v'
INLINE = '{'+NS+'}is'
TEXT = '{'+NS+'}t'

# List ONLY non-personal data fields permitted to leave the Excel file.
FIELDS = {
    'completed_date': ('completed date', 'tanggal', 'tanggal penjualan', 'sales date'),
    'completed_time': ('completed time', 'jam transaksi', 'jam'),
    'store_code': ('store code', 'kode toko', 'kode cabang'),
    'store': ('store', 'cabang', 'nama toko', 'nama cabang'),
    'transaction_ref': ('sales ref code', 'no transaksi', 'kode transaksi', 'transaction id'),
    'sku': ('sku', 'barcode', 'kode barang'),
    'item': ('item', 'nama produk', 'nama barang', 'produk'),
    'category': ('katagory utama', 'kategori utama', 'category', 'kategori'),
    'type_name': ('type name', 'jenis produk'),
    'brand': ('brand name', 'product brand', 'merek'),
    'supplier': ('supplier', 'pemasok'),
    'subcategory': ('spesifik product', 'subkategori'),
    'qty': ('qty', 'quantity', 'jumlah terjual', 'jumlah'),
    'unit_discount': ('unit discount', 'diskon satuan'),
    'unit_price': ('unit final price', 'harga satuan'),
    'sales': ('sales', 'net sales', 'omzet', 'omset', 'total sales', 'total omzet', 'total omset'),
    'sales_inc_tax': ('sales (inc tax)', 'sales inc tax', 'omzet termasuk pajak'),
    'cost': ('cost', 'hpp', 'total cost'),
    'gross_profit': ('gross profit', 'laba kotor'),
    'status': ('status', 'status transaksi'),
    'discount_name': ('discount name', 'nama diskon'),
}
REQUIRED = {'completed_date', 'store', 'item', 'qty', 'sales'}
METRICS = {
    'sales': 'COALESCE(SUM(sales),0)',
    'sales_inc_tax': 'COALESCE(SUM(sales_inc_tax),0)',
    'cost': 'COALESCE(SUM(cost),0)',
    'gross_profit': 'COALESCE(SUM(gross_profit),0)',
    'qty': 'COALESCE(SUM(qty),0)',
    'discount': 'COALESCE(SUM(unit_discount * qty),0)',
    'transactions': "COUNT(DISTINCT CASE WHEN transaction_ref <> '' THEN COALESCE(NULLIF(store_code,''),store) || ':' || transaction_ref END)",
}
DIMENSIONS = {
    'store': "COALESCE(NULLIF(store,''), '(Tanpa cabang)')",
    'item': "COALESCE(NULLIF(item,''), '(Tanpa produk)')",
    'sku': "COALESCE(NULLIF(sku,''), '(Tanpa SKU)')",
    'category': "COALESCE(NULLIF(category,''), '(Tanpa kategori)')",
    'brand': "COALESCE(NULLIF(brand,''), '(Tanpa merek)')",
    'supplier': "COALESCE(NULLIF(supplier,''), '(Tanpa supplier)')",
    'subcategory': "COALESCE(NULLIF(subcategory,''), '(Tanpa subkategori)')",
    'completed_date': 'completed_date',
    'hour': "SUBSTR(completed_time,1,2) || ':00'",
    'status': "COALESCE(NULLIF(status,''), '(Tanpa status)')",
}
FIELD_SQL = [(f, 'REAL' if f in {'qty','unit_discount','unit_price','sales','sales_inc_tax','cost','gross_profit'} else 'TEXT') for f in FIELDS]


def normalize_name(s: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', str(s or '').lower())).strip()


NAME_MAP = {normalize_name(name): field for field, names in FIELDS.items() for name in names}


def detect_mapping(row: dict[int, str]) -> dict[int, str]:
    mapping = {}
    for i, value in row.items():
        field = NAME_MAP.get(normalize_name(value))
        if field and field not in mapping.values():
            mapping[i] = field
    return mapping if REQUIRED.issubset(set(mapping.values())) else {}


def col_number(ref: str) -> int:
    n = 0
    for c in ref:
        if c.isalpha():
            n = n * 26 + (ord(c.upper()) - 64)
        else:
            break
    return n - 1


def get_cell_value(cell, shared: list[str]) -> str:
    typ = cell.get('t')
    if typ == 'inlineStr':
        inline = cell.find(INLINE)
        if inline is None:
            return ''
        return ''.join(el.text or '' for el in inline.iter(TEXT))[:3000]
    val = cell.find(VALUE)
    if val is None or val.text is None:
        return ''
    if typ == 's':
        try:
            return shared[int(val.text)]
        except (IndexError, ValueError):
            return ''
    return val.text[:3000]


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    path = 'xl/sharedStrings.xml'
    if path not in z.namelist():
        return []
    if z.getinfo(path).file_size > 125_000_000:
        raise ValueError('Daftar shared strings Excel terlalu besar untuk paket hosting gratis. Coba ekspor sebagai CSV.')
    items = []
    with z.open(path) as handle:
        context = ET.iterparse(handle, events=('start','end'))
        _, root = next(context)
        for event, el in context:
            if event == 'end' and el.tag == '{'+NS+'}si':
                items.append(''.join(t.text or '' for t in el.iter(TEXT))[:3000])
                el.clear()
                if len(items) % 1000 == 0:
                    root.clear()  # limit XML tree memory
    return items


def _iter_xlsx(file: BinaryIO, progress: Callable[[int], None] | None = None) -> Iterator[tuple[int,dict[str,str]]]:
    try:
        z = zipfile.ZipFile(file)
    except zipfile.BadZipFile as exc:
        raise ValueError('File XLSX tidak valid / rusak.') from exc
    with z:
        if len(z.infolist()) > 600 or sum(p.file_size for p in z.infolist()) > 1_500_000_000:
            raise ValueError('XLSX terlalu besar setelah diekstrak; batasi ukuran data.')
        shared = _shared_strings(z)
        sheets = sorted((name for name in z.namelist()
                        if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name)),
                        key=lambda n: int(re.search(r'sheet(\d+)\.xml',n).group(1)))
        if not sheets:
            raise ValueError('Sheet Excel tidak ditemukan.')
        total_size = sum(z.getinfo(x).file_size for x in sheets)
        byte_done = 0
        valid = False
        for sheet_name in sheets:
            map_fields: dict[int,str] = {}
            local_rows = 0
            with z.open(sheet_name) as handle:
                context = ET.iterparse(handle, events=('start','end'))
                _, root = next(context)
                for event, row in context:
                    if event != 'end' or row.tag != ROW:
                        continue
                    local_rows += 1
                    if not map_fields:
                        if local_rows <= 40:
                            raw = {col_number(c.get('r','')):get_cell_value(c,shared) for c in row if c.tag==CELL}
                            map_fields = detect_mapping(raw)
                            if map_fields:
                                valid = True
                        row.clear()
                        if local_rows % 500 == 0:
                            root.clear()
                        continue
                    mapped = {}
                    for c in row:
                        if c.tag == CELL:
                            idx = col_number(c.get('r',''))
                            fld = map_fields.get(idx)
                            if fld:
                                mapped[fld] = get_cell_value(c,shared)
                    if mapped:
                        yield local_rows, mapped
                    row.clear()
                    if local_rows % 500 == 0:
                        root.clear()  # bounded memory for 200k+ XLSX rows
                    if progress and local_rows % 10000 == 0:
                        progress(min(int((byte_done / max(total_size,1))*95 + 90 * local_rows / max(local_rows+10000,1)),95))
            byte_done += z.getinfo(sheet_name).file_size
        if not valid:
            raise ValueError('Kolom Detailed Sales tidak dikenali. Minimal perlu Tanggal, Cabang, Produk, Qty dan Sales.')


def _iter_csv(file: BinaryIO) -> Iterator[tuple[int, dict[str,str]]]:
    file.seek(0)
    content = io.TextIOWrapper(file,encoding='utf-8-sig',errors='replace',newline='')
    try:
        reader = csv.reader(content)
        mapping = {}
        for line_number, row in enumerate(reader,1):
            if not mapping:
                if line_number <= 40:
                    mapping=detect_mapping({idx: text for idx,text in enumerate(row)})
                continue
            yield line_number, {key:row[idx] for idx,key in mapping.items() if idx<len(row)}
        if not mapping:
            raise ValueError('Header CSV tidak dikenali. Periksa nama kolom.')
    finally:
        content.detach()


def number(raw) -> float:
    if raw is None or str(raw).strip() in {'','-'}:
        return 0.
    s = str(raw).strip().replace('Rp','').replace(' ','')
    if ',' in s and '.' in s:
        s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
    elif ',' in s:
        # 1,500,000 (thousands) vs 1,5 (decimal)
        s=s.replace(',','') if re.fullmatch(r'-?\d{1,3}(,\d{3})+',s) else s.replace(',','.')
    try:
        return float(s)
    except ValueError:
        return 0.


def valid_required_number(raw) -> bool:
    """Do not silently convert malformed mandatory Qty/Sales values into zero."""
    s=str(raw or '').strip().replace('Rp','').replace(' ','')
    if not re.fullmatch(r'[+-]?\d[\d.,]*(?:[eE][+-]?\d+)?',s):
        return False
    if ',' in s and '.' in s:
        s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
    elif ',' in s:
        s=s.replace(',','') if re.fullmatch(r'-?\d{1,3}(,\d{3})+',s) else s.replace(',','.')
    try:
        return math.isfinite(float(s))
    except ValueError:
        return False


def normalize_date(raw: str) -> str:
    s = str(raw or '').strip()
    if not s:
        return ''
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',s):
        try:
            return date.fromisoformat(s).isoformat()
        except ValueError:
            return ''
    for fmt in ('%d/%m/%Y','%d-%m-%Y','%Y/%m/%d','%d-%b-%Y','%m/%d/%Y'):
        try:
            return datetime.strptime(s,fmt).date().isoformat()
        except ValueError:
            pass
    if re.fullmatch(r'\d+(?:\.\d+)?',s):
        try:
            from datetime import timedelta
            return (date(1899,12,30) + timedelta(days=int(float(s)))).isoformat()
        except (ValueError, OverflowError):
            return ''
    return ''


def _row_values(source: dict[str,str]) -> list:
    record=[]
    for name, typ in FIELD_SQL:
        value = source.get(name,'')
        if name == 'completed_date':
            value = normalize_date(value)
        elif typ == 'REAL':
            value = number(value)
        else:
            value = str(value or '').strip()[:500]
        record.append(value)
    return record


def create_database() -> str:
    f = tempfile.NamedTemporaryFile(prefix='bai_session_',suffix='.sqlite3',delete=False)
    f.close()
    with closing(sqlite3.connect(f.name)) as con, con:
        con.execute('PRAGMA journal_mode=DELETE')
        con.execute('PRAGMA synchronous=OFF')
        cols=', '.join(f'{name} {typ}' for name,typ in FIELD_SQL)
        con.execute(f'CREATE TABLE sales_rows (source_file TEXT NOT NULL, source_row INTEGER NOT NULL, {cols})')
        con.execute('CREATE TABLE imports (filename TEXT NOT NULL, file_hash CHAR(64) NOT NULL UNIQUE, rows_inserted INTEGER NOT NULL, rows_bad_date INTEGER NOT NULL, rows_bad_numbers INTEGER NOT NULL DEFAULT 0, imported_at TEXT NOT NULL)')
    return f.name


def ingest_file(db_path: str, uploaded_file: BinaryIO, filename: str,
                progress: Callable[[int], None] | None = None) -> dict:
    if not filename.lower().endswith(('.xlsx','.csv')):
        raise ValueError('Format file belum didukung. Gunakan .xlsx atau .csv.')
    iterator = _iter_xlsx if filename.lower().endswith('.xlsx') else _iter_csv
    filename = Path(filename).name[:180]
    uploaded_file.seek(0)
    checksum=hashlib.sha256()
    while chunk := uploaded_file.read(1024*1024):
        checksum.update(chunk)
    file_hash=checksum.hexdigest()
    uploaded_file.seek(0)
    names = ['source_file','source_row']+[f for f,_ in FIELD_SQL]
    placeholders=','.join('?' for _ in names)
    insert=f"INSERT INTO sales_rows ({','.join(names)}) VALUES ({placeholders})"
    count, bad, invalid_numbers = 0, 0, 0
    with closing(sqlite3.connect(db_path)) as con, con:
        if con.execute('SELECT 1 FROM imports WHERE file_hash=?',(file_hash,)).fetchone():
            raise ValueError(f'File {filename} sudah diimpor di dataset ini. File identik tidak boleh dihitung dua kali.')
        con.execute('BEGIN')
        batch=[]
        try:
            for row_number, row in iterator(uploaded_file) if iterator is _iter_csv else iterator(uploaded_file,progress):
                if count + len(batch) >= 700_000:
                    raise ValueError('Batas 700.000 baris per file tercapai. Pecah file atau gunakan server yang lebih besar.')
                if not valid_required_number(row.get('qty')) or not valid_required_number(row.get('sales')):
                    invalid_numbers+=1
                    continue
                values=_row_values(row)
                if not values[0]:
                    bad+=1
                    continue
                batch.append((filename,row_number,*values))
                if len(batch)>=1500:
                    con.executemany(insert,batch)
                    count+=len(batch)
                    batch.clear()
                    if progress and count%15000<1500:
                        progress(min(95,5 + int((count/250000)*90)))
            if batch:
                con.executemany(insert,batch)
                count+=len(batch)
            if count==0:
                raise ValueError('Tidak ada baris valid setelah parsing file.')
            con.execute('INSERT INTO imports VALUES(?,?,?,?,?,?)',(filename,file_hash,count,bad,invalid_numbers,datetime.now().isoformat(timespec='seconds')))
        except Exception:
            con.rollback()
            raise
    return {'filename':filename,'rows':count,'invalid_dates':bad,'invalid_numbers':invalid_numbers,'hash_short':file_hash[:12]}


def finalize_database(db_path: str) -> None:
    with closing(sqlite3.connect(db_path)) as con, con:
        con.executescript('''
        CREATE INDEX IF NOT EXISTS idx_date_store ON sales_rows (completed_date,store);
        CREATE INDEX IF NOT EXISTS idx_cat_date ON sales_rows (category,completed_date);
        CREATE INDEX IF NOT EXISTS idx_item ON sales_rows (item);
        CREATE INDEX IF NOT EXISTS idx_status_date ON sales_rows (status,completed_date);
        ANALYZE;
        ''')


@contextmanager
def _db(db_path: str):
    con=sqlite3.connect(db_path,timeout=15)
    con.row_factory=sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def dataset_info(db_path: str) -> dict:
    with _db(db_path) as con:
        r=con.execute('''SELECT COUNT(*) rows,MIN(completed_date) min_date,MAX(completed_date) max_date,
                 COUNT(DISTINCT store) branches,COUNT(DISTINCT sku) products,
                 COUNT(DISTINCT category) categories,COUNT(DISTINCT brand) brands FROM sales_rows''').fetchone()
        statuses=[x['status'] for x in con.execute("SELECT DISTINCT status FROM sales_rows ORDER BY status")]
        files=[dict(x) for x in con.execute('SELECT * FROM imports ORDER BY imported_at')]
    return {**dict(r),'statuses':statuses,'imports':files}


def filter_sql(start: str, end: str, stores: list[str]|None=None,
               categories: list[str]|None=None, statuses: list[str]|None=None,
               brands: list[str]|None=None, suppliers: list[str]|None=None) -> tuple[str,list]:
    sql=['completed_date >= ?','completed_date <= ?']
    params=[start,end]
    for col,vals in (('store',stores),('category',categories),('status',statuses),
                     ('brand',brands),('supplier',suppliers)):
        if vals:
            sql.append(f"{col} IN ({','.join(['?']*len(vals))})")
            params.extend(vals)
    return ' AND '.join(sql),params


def distinct_values(db_path: str, field: str) -> list[str]:
    if field not in {'store','category','status','brand','supplier'}:
        raise ValueError('Field filter tidak diizinkan')
    with _db(db_path) as con:
        return [r[0] for r in con.execute(f"SELECT DISTINCT {field} FROM sales_rows WHERE {field}<>'' ORDER BY {field}")]


def overview(db_path: str, where: str, params: list) -> dict:
    with _db(db_path) as con:
        row=con.execute(f'''SELECT COUNT(*) rows,COUNT(DISTINCT store) branches,COUNT(DISTINCT sku) products,
            {METRICS['sales']} sales,{METRICS['sales_inc_tax']} sales_inc_tax,
            {METRICS['cost']} cost,{METRICS['gross_profit']} gross_profit,{METRICS['qty']} qty,
            {METRICS['discount']} discount,{METRICS['transactions']} transactions,
            COUNT(DISTINCT completed_date) days
            FROM sales_rows WHERE {where}''',params).fetchone()
    result=dict(row)
    result['margin'] = 100*result['gross_profit']/result['sales'] if result['sales'] else 0
    result['basket'] = result['sales']/result['transactions'] if result['transactions'] else 0
    return result


def aggregate(db_path: str, where: str, params: list, dimension: str,
              metric: str='sales', limit: int=20, ascending: bool=False) -> list[dict]:
    if dimension not in DIMENSIONS or metric not in METRICS:
        raise ValueError('Metrik atau dimensi tidak diizinkan')
    dim = DIMENSIONS[dimension]
    formula=METRICS[metric]
    order='ASC' if ascending else 'DESC'
    limit=max(1,min(int(limit),500))
    with _db(db_path) as con:
        result=con.execute(f'''SELECT {dim} AS label, {formula} AS value,
            COUNT(*) AS lines FROM sales_rows WHERE {where}
            GROUP BY {dim} ORDER BY value {order} LIMIT ?''',[*params,limit]).fetchall()
    return [dict(r) for r in result]


def trend(db_path: str, where: str, params: list, hour: bool=False) -> list[dict]:
    dim=DIMENSIONS['hour' if hour else 'completed_date']
    with _db(db_path) as con:
        rows=con.execute(f'''SELECT {dim} AS period,
            {METRICS['sales']} AS sales,{METRICS['gross_profit']} AS gross_profit,
            {METRICS['transactions']} AS transactions,
            {METRICS['qty']} AS qty
            FROM sales_rows WHERE {where} GROUP BY {dim} ORDER BY period''',params).fetchall()
    return [dict(r) for r in rows]


def paged_data(db_path: str, where: str, params: list, page: int=1, page_size: int=50) -> tuple[int,list[dict]]:
    # Excludes all identifying customer fields by design.
    page=max(1,int(page));page_size=max(1,min(100,int(page_size)))
    cols='completed_date,completed_time,store,sku,item,category,brand,qty,sales,sales_inc_tax,cost,gross_profit,status'
    with _db(db_path) as con:
        total=con.execute(f'SELECT COUNT(*) FROM sales_rows WHERE {where}',params).fetchone()[0]
        rows=con.execute(f'SELECT {cols} FROM sales_rows WHERE {where} ORDER BY completed_date DESC,source_row DESC LIMIT ? OFFSET ?',
                         [*params,page_size,(page-1)*page_size]).fetchall()
    return total,[dict(r) for r in rows]


def imported_summary(db_path: str) -> str:
    info=dataset_info(db_path)
    return f"{info['rows']:,} baris • {info['branches']:,} cabang • {info['min_date']} s.d. {info['max_date']}"
