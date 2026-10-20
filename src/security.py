"""Application security helpers, including safe exports and optional access gate."""
from __future__ import annotations
import hmac
import re
from pathlib import Path

MAX_FILES = 12
MAX_FILE_BYTES = 65 * 1024 * 1024
MAX_TOTAL_BYTES = 95 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.xlsx','.csv'}
DANGEROUS_FORMULA = re.compile(r'^\s*[=+\-@\t\r]')


def check_access(provided: str, configured: str) -> bool:
    return bool(configured and provided and hmac.compare_digest(provided.encode(),configured.encode()))


def safe_export_text(value) -> str:
    """Protect spreadsheet openers even if CSV/XLSX library options change."""
    if value is None:
        return ''
    text=str(value)
    return "'" + text if DANGEROUS_FORMULA.match(text) else text


def validate_uploads(files) -> tuple[bool,str]:
    if not files:
        return False,'Pilih minimal satu file.'
    if len(files)>MAX_FILES:
        return False,f'Maksimal {MAX_FILES} file per proses.'
    total=0
    for f in files:
        name=Path(f.name.replace('\\','/')).name
        if not name or Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
            return False,'Gunakan file Excel .xlsx atau CSV .csv saja.'
        size=int(getattr(f,'size',-1))
        if size<1:
            return False,f'File {name} kosong atau ukurannya tidak terbaca.'
        if size>MAX_FILE_BYTES:
            return False,f'File {name} melebihi batas 65 MB per file.'
        total+=size
    if total>MAX_TOTAL_BYTES:
        return False,'Total file melebihi 95 MB. Unggah secara bertahap dengan mode Tambahkan.'
    return True,''
