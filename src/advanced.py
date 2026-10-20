"""Advanced business analytics. All SQL is read-only and scoped to validated filters.

Never accept query expressions from model output or uploaded spreadsheet cells.
The UI uses *whitelisted* dimensions/metrics and bound parameter values.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median
import sqlite3
from typing import Any

from .engine import DIMENSIONS, METRICS, _db, filter_sql, overview


def enriched_aggregate(db_path: str, where: str, params: list, dimension: str,
                       sort_by: str = 'sales', limit: int = 100,
                       ascending: bool = False) -> list[dict]:
    if dimension not in DIMENSIONS or sort_by not in (*METRICS.keys(), 'margin'):
        raise ValueError('Dimensi atau metrik tidak tersedia')
    dim = DIMENSIONS[dimension]
    order = 'ASC' if ascending else 'DESC'
    sort_sql = 'margin' if sort_by == 'margin' else sort_by
    limit = min(max(int(limit), 1), 500)
    q = f'''SELECT {dim} label,
        {METRICS['sales']} sales, {METRICS['gross_profit']} gross_profit,
        {METRICS['cost']} cost, {METRICS['qty']} qty,
        {METRICS['transactions']} transactions,
        COUNT(*) lines,
        CASE WHEN SUM(sales)<>0 THEN 100.0*SUM(gross_profit)/SUM(sales) ELSE NULL END margin
        FROM sales_rows WHERE {where} GROUP BY {dim}
        ORDER BY {sort_sql} {order} LIMIT ?'''
    with _db(db_path) as conn:
        rows = [dict(r) for r in conn.execute(q, [*params, limit])]
    return rows


def product_abc(db_path: str, where: str, params: list,
                preview_limit: int = 200) -> dict[str,Any]:
    """True ABC over *all* SKUs (not just the displayed top 200)."""
    sql = f'''SELECT COALESCE(NULLIF(sku,''),NULLIF(item,''),'(tanpa kode)') sku,
              MAX(item) item, COALESCE(SUM(sales),0) sales,
              COALESCE(SUM(qty),0) qty, COALESCE(SUM(gross_profit),0) gross_profit
              FROM sales_rows WHERE {where}
              GROUP BY COALESCE(NULLIF(sku,''),NULLIF(item,''),'(tanpa kode)')
              ORDER BY sales DESC'''
    with _db(db_path) as conn:
        raw = [dict(row) for row in conn.execute(sql, params)]
    positive = sum(max(0.0, r['sales'] or 0) for r in raw)
    running = 0.0
    counts = {'A':0,'B':0,'C':0}
    for r in raw:
        before = running / positive * 100 if positive else 0
        running += max(0.0, r['sales'] or 0)
        r['cumulative_share'] = 100 * running / positive if positive else None
        # classify against contribution *before* item, so giant first SKU remains A
        r['abc'] = 'A' if before < 80 else ('B' if before < 95 else 'C')
        counts[r['abc']] += 1
        r['sales_share'] = 100 * (r['sales'] or 0)/positive if positive else None
    return {'items': raw[:min(max(preview_limit,1),500)],
            'total_skus':len(raw),'classes':counts,'total_positive_sales':positive,
            'has_nonpositive_sales':any((r['sales'] or 0)<=0 for r in raw)}


def quality_report(db_path: str, where: str, params: list) -> dict:
    sql = f'''SELECT COUNT(*) rows,
      SUM(CASE WHEN qty<=0 THEN 1 ELSE 0 END) nonpositive_qty,
      SUM(CASE WHEN sales<0 THEN 1 ELSE 0 END) negative_sales,
      SUM(CASE WHEN sales=0 THEN 1 ELSE 0 END) zero_sales,
      SUM(CASE WHEN gross_profit<0 THEN 1 ELSE 0 END) negative_gross_profit,
      SUM(CASE WHEN sku='' THEN 1 ELSE 0 END) missing_sku,
      SUM(CASE WHEN category='' THEN 1 ELSE 0 END) missing_category,
      SUM(CASE WHEN transaction_ref='' THEN 1 ELSE 0 END) missing_transaction,
      SUM(CASE WHEN cost<>0 AND ABS(sales-cost-gross_profit)>0.1
          THEN 1 ELSE 0 END) gp_mismatch,
      COUNT(DISTINCT completed_date) dates,
      COUNT(DISTINCT source_file) files
      FROM sales_rows WHERE {where}'''
    with _db(db_path) as conn:
        result = dict(conn.execute(sql,params).fetchone())
    return {k:(0 if v is None else v) for k,v in result.items()}


def previous_period(db_path: str, start: date, end: date, stores=None,
                    categories=None, statuses=None, brands=None, suppliers=None) -> dict:
    """Only calculate a growth percentage when BOTH comparison windows are fully covered.

    Incomplete daily coverage is intentionally marked non-comparable. This errs on
    the side of not claiming growth from partial uploads.
    """
    if end < start:
        raise ValueError('Rentang tanggal tidak valid')
    n_days = (end-start).days+1
    p_end = start-timedelta(days=1)
    p_start = p_end-timedelta(days=n_days-1)
    w1,a1=filter_sql(start.isoformat(),end.isoformat(),stores,categories,statuses,
                     brands=brands,suppliers=suppliers)
    w0,a0=filter_sql(p_start.isoformat(),p_end.isoformat(),stores,categories,statuses,
                     brands=brands,suppliers=suppliers)
    curr=overview(db_path,w1,a1)
    prev=overview(db_path,w0,a0)
    complete=curr['days']==n_days and prev['days']==n_days and prev['rows']>0
    delta = 100 * (curr['sales']/prev['sales']-1) if complete and prev['sales'] else None
    return {'current':curr,'previous':prev,'current_start':start.isoformat(),
            'current_end':end.isoformat(),'prior_start':p_start.isoformat(),
            'prior_end':p_end.isoformat(), 'span_days':n_days,
            'comparable':complete,'growth_pct':delta,
            'why_not': '' if complete else
              'Periode sekarang atau sebelumnya tidak memiliki data pada setiap tanggal. '
              'Pertumbuhan tidak dihitung agar tidak membandingkan periode yang tidak lengkap.'}


def branch_comparison(db_path: str, start: date, end: date, stores=None,
                      categories=None, statuses=None, brands=None, suppliers=None,
                      limit: int = 100) -> dict:
    result=previous_period(db_path,start,end,stores,categories,statuses,brands,suppliers)
    if not result['comparable']:
        return {'info':result,'rows':[]}
    args = (stores,categories,statuses)
    wn,pn=filter_sql(start.isoformat(),end.isoformat(),*args,brands=brands,suppliers=suppliers)
    wo,po=filter_sql(result['prior_start'],result['prior_end'],*args,brands=brands,suppliers=suppliers)
    now={r['label']:r for r in enriched_aggregate(db_path,wn,pn,'store',limit=500)}
    old={r['label']:r for r in enriched_aggregate(db_path,wo,po,'store',limit=500)}
    data=[]
    for name in set(now)|set(old):
        today=now.get(name,{}).get('sales',0)
        before=old.get(name,{}).get('sales',0)
        data.append({'cabang':name,'sekarang':today,'sebelumnya':before,
                     'selisih':today-before,
                     'growth_pct':100*(today/before-1) if before else None})
    return {'info':result,'rows':sorted(data,key=lambda r:abs(r['selisih']),reverse=True)[:limit]}


def anomaly_days(db_path: str, where: str, params: list) -> dict:
    """Daily anomaly *signals*, not assertions of causality. Require ≥7 dates."""
    with _db(db_path) as conn:
        rows=[dict(r) for r in conn.execute(
            f'SELECT completed_date period, SUM(sales) sales FROM sales_rows WHERE {where} '
            'GROUP BY completed_date ORDER BY completed_date',params)]
    if len(rows)<7:
        return {'enough_data':False,'series':rows,'signals':[],
                'note':'Butuh minimal 7 tanggal untuk mendeteksi anomali penjualan harian.'}
    values=[r['sales'] for r in rows]
    med=median(values)
    mad=median([abs(v-med) for v in values])
    signals=[]
    if mad<=0:
        note='Variasi data terlalu kecil untuk klasifikasi anomali berbasis MAD.'
    else:
        note='Sinyal statistik menggunakan robust z-score (median dan MAD), bukan bukti penyebab.'
        for r in rows:
            score=0.6745 * (r['sales']-med)/mad
            if abs(score)>=3.5:
                signals.append({**r,'robust_z':round(score,2),
                                'arah':'Lebih tinggi' if score>0 else 'Lebih rendah'})
    return {'enough_data':True,'series':rows,'signals':signals[:25],
            'median':med,'mad':mad,'note':note}


def insight_cards(db_path: str, where: str, params: list) -> list[dict]:
    """Deterministic, auditable insights; not causal explanations."""
    o=overview(db_path,where,params)
    if not o['rows']:
        return []
    cards=[]
    for dimension, title in [('store','Cabang paling berkontribusi'),
                             ('category','Kategori terbesar'),
                             ('item','Produk teratas')]:
        top=enriched_aggregate(db_path,where,params,dimension,limit=1)
        if not top:continue
        r=top[0];share=100*r['sales']/o['sales'] if o['sales'] else 0
        cards.append({'title':title,'value':r['label'],
                      'detail':f"Omzet Rp{r['sales']:,.0f} ({share:.1f}% dari omzet terfilter)."})
    cards.append({'title':'Kualitas margin','value':f"{o['margin']:.1f}%",
                  'detail':'Margin laba kotor berdasarkan Sales dan Gross Profit; bukan laba bersih.'})
    if o['transactions']:
        cards.append({'title':'Rata-rata nilai transaksi',
                      'value':f"Rp{o['basket']:,.0f}",
                      'detail':'Omzet dibagi jumlah transaksi unik yang memiliki kode transaksi.'})
    return cards
