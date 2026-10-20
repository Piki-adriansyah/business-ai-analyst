"""Guarded analytical Q&A: deterministic calculations, optional generative explanation.

Never send original files or customer data to any LLM.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any
from datetime import date
from .advanced import anomaly_days, product_abc, quality_report, enriched_aggregate, previous_period, branch_comparison

from .engine import aggregate, dataset_info, distinct_values, filter_sql, overview, trend

LABELS = {
    'store':'cabang', 'item':'produk', 'category':'kategori', 'brand':'merek',
    'supplier':'supplier', 'subcategory':'subkategori', 'hour':'jam',
    'completed_date':'tanggal', 'sku':'SKU'
}
METRIC_LABELS={'sales':'omzet sebelum pajak','sales_inc_tax':'omzet termasuk pajak',
               'gross_profit':'laba kotor','qty':'unit terjual','transactions':'transaksi',
               'cost':'biaya pokok','discount':'total diskon satuan × qty'}


def idr(x: float) -> str:
    return 'Rp' + f'{x:,.0f}'.replace(',','.')


def num(x: float) -> str:
    return f'{x:,.0f}'.replace(',','.')


def metric_format(metric: str, x: float) -> str:
    return num(x) if metric in {'qty','transactions'} else idr(x)


def _scope(question: str, db_path: str, where: str, params: list) -> tuple[str,list,str]:
    """Constrain query to explicitly named store only if a unique match exists."""
    q=question.lower()
    names=distinct_values(db_path,'store')
    m=re.search(r'\b(?:ns|niceso|toko|cabang)\s*(\d{1,3})\b',q)
    if m:
        code='NS' + m.group(1).zfill(2)
        matches=[store for store in names if re.search(r'\bNICESO\s*0*'+re.escape(m.group(1))+r'\s*,',store,re.I)]
        if len(matches)==1:
            return where + ' AND store=?',[*params,matches[0]],matches[0]
    # City/store name tails such as "Kahfi", "Cikampek", etc.
    tokens=re.findall(r'\b[a-z]{5,}\b',q)
    if tokens:
        for token in sorted(set(tokens),key=len,reverse=True):
            candidates=[]
            for store in names:
                suffix=store.split(',',1)[-1].lower()
                if re.search(r'\b'+re.escape(token)+r'\b',suffix):
                    candidates.append(store)
            if len(candidates)==1:
                return where+' AND store=?',[*params,candidates[0]],candidates[0]
    return where,params,''


def answer_question(question: str, db_path: str, where: str, params: list,
                    period_context: dict|None=None) -> dict[str,Any]:
    q=' '.join(question.lower().split())
    if not q:
        return {'answer':'Tulis pertanyaan terlebih dahulu.','table':[],'context':{}}
    if any(word in q for word in ['ktp','npwp','nomor hp','telepon pelanggan','customer id','alamat pelanggan']):
        return {'answer':'Data pribadi pelanggan tidak disimpan oleh aplikasi ini. Kamu bisa menganalisis data transaksi, cabang, produk, kategori, dan laba kotor.','table':[],'context':{}}

    scoped_where,scoped_params,matched_store=_scope(question,db_path,where,params)
    o=overview(db_path,scoped_where,scoped_params)
    info=dataset_info(db_path)
    context={'range':f"{info['min_date']} – {info['max_date']}",
             'lines':o['rows'],'days':o['days'],'store_filter':matched_store,
             'omzet':o['sales'],'gross_profit':o['gross_profit'],'qty':o['qty'],
             'transactions':o['transactions'],'margin':o['margin']}
    if not o['rows']:
        return {'answer':'Tidak ada transaksi yang cocok dengan filter atau cabang yang disebutkan.','table':[],'context':context}

    # V2: specialized deterministic analyses over whitelisted SQL only.
    if any(k in q for k in ('abc','pareto','80/20','80 20')):
        abc=product_abc(db_path,scoped_where,scoped_params,preview_limit=12)
        classes=abc['classes']
        table=[{'SKU':r['sku'],'Produk':r['item'],'Kelas':r['abc'],
                'Omzet':r['sales'],'Kontribusi (%)':round(r['sales_share'] or 0,2)}
               for r in abc['items']]
        return {'answer':f"**Analisis ABC seluruh {abc['total_skus']:,} SKU**\n\n"
                  f"- Kelas A: **{classes['A']:,} SKU** (kontribusi kumulatif awal sekitar 80%)\n"
                  f"- Kelas B: **{classes['B']:,} SKU** (kontribusi berikutnya hingga ~95%)\n"
                  f"- Kelas C: **{classes['C']:,} SKU** (sisanya).\n\n"
                  "Penentuan kelas memakai seluruh SKU dengan omzet positif dan mengacu pada data terfilter. "
                  "Produk beromzet nol/negatif perlu diperiksa terpisah.",
                'table':table,'context':{**context,'abc_counts':classes}}

    if any(k in q for k in ('anomali','tidak normal','outlier','lonjakan')):
        ana=anomaly_days(db_path,scoped_where,scoped_params)
        if not ana['enough_data']:
            return {'answer':ana['note'],'table':[],'context':context}
        top=ana['signals']
        if not top:
            msg='Tidak ditemukan sinyal anomali kuat pada omzet harian dalam periode terfilter.'
        else:
            msg=f'Ditemukan **{len(top)} tanggal** dengan deviasi tinggi dari median penjualan.'
        return {'answer':msg+'\n\n'+ana['note'],
                'table':[{'Tanggal':r['period'],'Omzet':r['sales'],
                          'Skor robust z':r['robust_z'],'Arah':r['arah']} for r in top],
                'context':{**context,'anomaly_count':len(top)}}

    if any(k in q for k in ('kualitas data','data kosong','validasi','data bermasalah')):
        qc=quality_report(db_path,scoped_where,scoped_params)
        return {'answer':f"**Pemeriksaan kualitas pada {qc['rows']:,} baris**\n\n"
                f"- SKU kosong: {qc['missing_sku']:,}\n"
                f"- Kategori kosong: {qc['missing_category']:,}\n"
                f"- Qty <= 0: {qc['nonpositive_qty']:,}\n"
                f"- Sales negatif: {qc['negative_sales']:,}\n"
                f"- Laba kotor negatif: {qc['negative_gross_profit']:,}.\n\n"
                'Ini indikator untuk ditinjau, bukan bukti kecurangan atau kesalahan sumber.',
                'table':[],'context':{**context,'quality':qc}}

    if ('margin' in q or 'persentase laba' in q) and any(k in q for k in ('cabang','toko','kategori','produk')):
        dim = 'store' if any(k in q for k in ('cabang','toko')) else ('category' if 'kategori' in q else 'item')
        rows=[r for r in enriched_aggregate(db_path,scoped_where,scoped_params,dim,'margin',20)
              if r['margin'] is not None and r['sales']>0]
        if rows:
            return {'answer':f'Peringkat margin laba kotor tertinggi berdasarkan {LABELS[dim]} pada data terfilter. '
                              'Margin dari omzet kecil perlu dibandingkan dengan nilai dan volume transaksi.',
                    'table':[{'Nama':r['label'],'Margin (%)':round(r['margin'],2),
                              'Omzet':r['sales'],'Laba Kotor':r['gross_profit']} for r in rows],
                    'context':{**context,'margin_ranking':rows[:8]}}

    # Comparison between precisely named branches (not guessed locations).
    if any(k in q for k in ('bandingkan','versus',' vs ','perbandingan')) and any(k in q for k in ('cabang','toko')):
        names=distinct_values(db_path,'store')
        matched=[n for n in names if len(n)>2 and n.casefold() in q.casefold()]
        if len(matched)==2:
            rows=[]
            for n in matched:
                ww=where+' AND store=?'; pp=[*params,n]
                data=overview(db_path,ww,pp)
                rows.append({'Cabang':n,'Omzet':data['sales'],'Laba Kotor':data['gross_profit'],
                            'Margin (%)':round(data['margin'],2),'Transaksi':data['transactions']})
            return {'answer':'Perbandingan dua cabang berikut mengikuti filter aktif. '
                    'Perbedaan angka belum membuktikan penyebab performa.',
                    'table':rows,'context':{**context,'branch_comparison':rows}}

    if any(kw in q for kw in ['margin','persentase laba']):
        return {'answer':f"Margin laba kotor pada data terfilter adalah **{o['margin']:.2f}%**, dari omzet sebelum pajak {idr(o['sales'])} dan laba kotor {idr(o['gross_profit'])}.\n\n**Catatan:** ini margin laba kotor, bukan laba bersih.",
                'table':[],'context':context}

    if any(kw in q for kw in ['pertumbuhan','growth','dibanding','perbandingan',
                              'kenapa turun','mengapa turun','naik atau turun']):
        if period_context:
            start_date=period_context.get('start')
            end_date=period_context.get('end')
            if start_date and end_date:
                comp=previous_period(db_path,start_date,end_date,
                       stores=period_context.get('stores'),
                       categories=period_context.get('categories'),
                       statuses=period_context.get('statuses'),
                       brands=period_context.get('brands'),
                       suppliers=period_context.get('suppliers'))
                if comp['comparable'] and comp['growth_pct'] is not None:
                    delta=comp['growth_pct']
                    suffix='naik' if delta>=0 else 'turun'
                    result={'answer':f"Omzet pada **{comp['current_start']} s.d. {comp['current_end']}**: "
                            f"**{idr(comp['current']['sales'])}**. Periode pembanding "
                            f"**{comp['prior_start']} s.d. {comp['prior_end']}**: "
                            f"**{idr(comp['previous']['sales'])}**. "
                            f"Perubahan omzet **{suffix} {abs(delta):.2f}%**.\n\n"
                            'Ini perubahan deskriptif, bukan bukti mengapa omzet berubah.',
                            'table':[],'context':{**context,'previous':comp['previous']['sales'],
                                                  'growth_pct':delta}}
                    if any(x in q for x in ('kenapa','mengapa','penyebab','faktor')):
                        c=branch_comparison(db_path,start_date,end_date,
                             stores=period_context.get('stores'),categories=period_context.get('categories'),
                             statuses=period_context.get('statuses'),brands=period_context.get('brands'),
                             suppliers=period_context.get('suppliers'),limit=8)
                        result['table']=[{'Cabang':r['cabang'],'Omzet sekarang':r['sekarang'],
                                          'Omzet sebelumnya':r['sebelumnya'],
                                          'Selisih':r['selisih']} for r in c['rows']]
                        result['answer'] += '\n\nTabel menunjukkan cabang dengan perubahan absolut terbesar, '
                        result['answer'] += 'bukan kepastian penyebab perubahan.'
                    return result
                if not comp['comparable']:
                    return {'answer':'**Belum bisa menghitung growth yang sebanding.** '
                            +comp['why_not']+'\n\nUpload data pada periode sebelumnya secara lengkap.',
                            'table':[],'context':context}
        if o['days']<2:
            return {'answer':f"**Belum bisa menghitung pertumbuhan antarhari** karena data yang terfilter "
                    f"hanya mencakup {o['days']} hari. Upload file tanggal sebelumnya sebagai pembanding.",
                    'table':[],'context':context}
        series=trend(db_path,scoped_where,scoped_params)
        first,last=series[0],series[-1]
        growth=None if first['sales']==0 else (last['sales']/first['sales']-1)*100
        growth_text='tidak bisa dihitung: awal bernilai nol' if growth is None else f'{growth:+.2f}%'
        return {'answer':f"Perbandingan tanggal pertama ({first['period']}, {idr(first['sales'])}) "
                f"dan terakhir ({last['period']}, {idr(last['sales'])}): **{growth_text}**. "
                'Ini BUKAN growth antarperiode dengan panjang sama; pilih rentang yang memiliki periode '
                'sebelumnya untuk analisis pertumbuhan yang valid.',
                'table':[{'Tanggal':r['period'],'Omzet':r['sales']} for r in series[-14:]],
                'context':context}

    # Metric selection
    metric='sales'
    if 'laba' in q or 'profit' in q: metric='gross_profit'
    elif any(w in q for w in ['unit','jumlah terjual','kuantitas','qty','berapa barang']): metric='qty'
    elif any(w in q for w in ['pajak','inc tax']): metric='sales_inc_tax'
    elif 'diskon' in q: metric='discount'
    elif any(w in q for w in ['hpp','biaya pokok','cost']): metric='cost'
    elif any(w in q for w in ['transaksi','struk','nota']): metric='transactions'

    dimension = None
    if any(w in q for w in ['jam','pukul','waktu ramai']): dimension='hour'
    elif any(w in q for w in ['supplier','pemasok']):dimension='supplier'
    elif any(w in q for w in ['kategori','category']): dimension='category'
    elif any(w in q for w in ['merek','brand']): dimension='brand'
    elif any(w in q for w in ['produk','barang','sku','item','terlaris']): dimension='item'
    elif any(w in q for w in ['cabang','toko','store','tertinggi','terendah','peringkat']): dimension='store'
    elif any(w in q for w in ['tanggal','harian','per hari']): dimension='completed_date'

    nmatch=re.search(r'\b(?:top|atas|teratas|terbaik)\s*(\d{1,2})\b',q)
    top=min(25,max(1,int(nmatch.group(1)))) if nmatch else 10
    ascending=any(w in q for w in ['terendah','terkecil','paling rendah'])
    if dimension:
        rows=aggregate(db_path,scoped_where,scoped_params,dimension,metric,top,ascending)
        if not rows:
            return {'answer':'Tidak tersedia data untuk pengelompokan tersebut.','table':[],'context':context}
        scope=' untuk '+matched_store if matched_store else ''
        title=f"**{top} {LABELS[dimension]} {'terendah' if ascending else 'tertinggi'} berdasarkan {METRIC_LABELS[metric]}{scope}**"
        lines=[f"{i}. {r['label']}: **{metric_format(metric,r['value'])}**" for i,r in enumerate(rows,1)]
        context['ranking']=[{'name':r['label'],'value':r['value']} for r in rows]
        return {'answer':title+'\n\n'+'\n'.join(lines),
                'table':[{LABELS[dimension].title():r['label'],METRIC_LABELS[metric].title():r['value']} for r in rows],
                'context':context}

    if 'ringkas' in q or 'insight' in q or 'analisis' in q or 'kesimpulan' in q:
        cats=aggregate(db_path,scoped_where,scoped_params,'category','sales',3)
        context['top_categories']=[{'name':r['label'],'sales':r['value']} for r in cats]
        top_category=(f"Kategori omzet tertinggi adalah **{cats[0]['label']}** ({idr(cats[0]['value'])})." if cats else '')
        return {'answer':f"**Ringkasan data terfilter**\n\n- Omzet sebelum pajak: **{idr(o['sales'])}**\n- Laba kotor: **{idr(o['gross_profit'])}** ({o['margin']:.2f}% margin)\n- Unit terjual: **{num(o['qty'])}**\n- Transaksi unik: **{num(o['transactions'])}**\n- Cabang aktif: **{o['branches']}**\n\n{top_category}\n\nData ini menunjukkan hasil penjualan, bukan penyebab naik-turunnya performa.",
                'table':[],'context':context}

    value={'sales':o['sales'],'sales_inc_tax':o['sales_inc_tax'],'gross_profit':o['gross_profit'],
           'qty':o['qty'],'transactions':o['transactions'],'cost':o['cost'],'discount':o['discount']}[metric]
    suffix=f" untuk **{matched_store}**" if matched_store else ''
    return {'answer':f"Total **{METRIC_LABELS[metric]}**{suffix} pada periode terfilter: **{metric_format(metric,value)}**.\n\nDihitung dari **{num(o['rows'])}** baris detail penjualan.",
            'table':[],'context':context}


def explain_with_gemini(question: str, result: dict, key: str,
                        model: str='gemini-2.5-flash') -> str:
    """Send ONLY already-aggregated business results, with explicit user opt-in."""
    if not key or not key.strip():
        raise ValueError('GEMINI_API_KEY belum dikonfigurasi oleh pengelola aplikasi.')
    safe_context=json.dumps(result.get('context',{}),ensure_ascii=False,default=str)[:12000]
    prompt=(
        'Kamu asisten Business Data Analyst. Gunakan HANYA angka dari ringkasan agregat yang diberikan. '
        'Jawab dalam bahasa Indonesia singkat dan praktis. Jangan membuat data, menyimpulkan sebab-akibat, '
        'atau menyebut data pelanggan. Jika satu hari, jangan klaim ada pertumbuhan harian/bulanan. '
        'Tidak perlu menghitung ulang jika jawaban deterministik sudah ada. '
        f'\nPERTANYAAN: {question[:1000]}\nHASIL TERVALIDASI:\n{result.get("answer","")[:6000]}'
        f'\nDATA AGREGAT:\n{safe_context}\nBerikan penjelasan berdasarkan bukti, keterbatasan, dan tindakan analisis berikutnya.'
    )
    payload={'contents':[{'role':'user','parts':[{'text':prompt}]}],
             'generationConfig':{'temperature':0.1,'maxOutputTokens':700}}
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    req=urllib.request.Request(url,data=json.dumps(payload).encode('utf-8'),method='POST',
        headers={'Content-Type':'application/json','x-goog-api-key':key.strip()})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp:
            body=json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code==429:
            raise RuntimeError('Kuota AI telah tercapai; silakan gunakan mode analitik lokal.') from exc
        if exc.code in (401,403):
            raise RuntimeError('Kunci Gemini tidak valid atau izin belum aktif.') from exc
        raise RuntimeError(f'Penyedia AI mengembalikan error HTTP {exc.code}.') from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError('Tidak bisa terhubung ke layanan AI. Coba lagi nanti.') from exc
    candidates=body.get('candidates') or []
    if not candidates:
        raise RuntimeError('AI tidak memberikan jawaban. Gunakan hasil analisis lokal.')
    parts=candidates[0].get('content',{}).get('parts',[])
    output='\n'.join(p.get('text','') for p in parts if p.get('text'))
    return output.strip() or 'AI tidak memberikan jawaban.'
