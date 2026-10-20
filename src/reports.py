"""Privacy-preserving aggregated Excel and PDF reports; never export raw customers.

Works entirely in memory; safe on Streamlit Community Cloud.
"""
from __future__ import annotations
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from typing import Mapping, Sequence

from .security import safe_export_text

REPORT_SHEETS = [
    ('Cabang','cabang'), ('Produk','produk'), ('Kategori','kategori'),
    ('Brand','brand'), ('Supplier','supplier'), ('Tren','tren')
]


def _idr(v):
    return 'Rp' + f'{float(v or 0):,.0f}'.replace(',','.')


def _headers(records):
    # Exclude anything unexpected, most importantly transaction/customer fields
    allowed=('label','sku','item','sales','gross_profit','cost','qty','transactions',
             'margin','lines','sales_share','cumulative_share','abc',
             'period','sekarang','sebelumnya','selisih','growth_pct',
             'cabang','sources')
    return [k for k in allowed if any(k in d for d in records)]


def make_excel(summary: Mapping, grouped: Mapping[str,Sequence[dict]],
               quality: Mapping, sources: Sequence[dict], period_text: str) -> bytes:
    import xlsxwriter
    buf=BytesIO()
    wb=xlsxwriter.Workbook(buf, {'in_memory':True,'strings_to_formulas':False,
                                 'strings_to_urls':False})
    wb.set_properties({'title':'Business AI Analyst V2 - Laporan Bisnis',
                       'subject':'Agregat penjualan non-PII','comments':'Tidak memuat kolom pelanggan'})
    navy='#14243D';blue='#215ED8';grey='#64748B'
    header=wb.add_format({'bold':True,'font_color':'#FFFFFF','bg_color':navy,
                          'border':0,'valign':'vcenter'})
    title=wb.add_format({'bold':True,'font_size':20,'font_color':navy})
    sub=wb.add_format({'font_color':grey,'font_size':10})
    label=wb.add_format({'bold':True,'font_color':'#32465E'})
    money=wb.add_format({'num_format':'"Rp" #,##0;[Red]("Rp" #,##0)','font_color':navy})
    numeric=wb.add_format({'num_format':'#,##0;[Red](#,##0)'})
    percent=wb.add_format({'num_format':'0.00"%"'})
    normal=wb.add_format({'text_wrap':False,'font_color':navy})
    ws=wb.add_worksheet('Ringkasan')
    ws.hide_gridlines(2)
    ws.set_tab_color(blue)
    ws.set_column('A:A',28)
    ws.set_column('B:B',26)
    ws.set_column('C:H',15)
    ws.set_row(0,33)
    ws.write('A1','BUSINESS AI ANALYST V2',title)
    ws.write('A2','RINGKASAN ANALISIS BISNIS',sub)
    ws.write('A4','Periode',label);ws.write('B4',period_text,normal)
    ws.write('A5','Dibuat (UTC)',label);ws.write('B5',datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),normal)
    defn=[('Total omzet (sebelum pajak)','sales',money),
          ('Omzet termasuk pajak','sales_inc_tax',money),
          ('Laba kotor','gross_profit',money),('HPP','cost',money),
          ('Margin laba kotor (%)','margin',percent),('Unit terjual','qty',numeric),
          ('Transaksi unik','transactions',numeric),('Cabang','branches',numeric),
          ('SKU unik','products',numeric),('Baris terfilter','rows',numeric)]
    for i,(label_name,key,fmt) in enumerate(defn,6):
        ws.write(i,0,label_name,label)
        ws.write_number(i,1,float(summary.get(key,0) or 0),fmt)
    ws.write('A19','DEFINISI & BATASAN',header)
    notes=['Omzet = jumlah Sales (sebelum pajak), bukan Sales (Inc Tax).',
           'Laba kotor adalah angka Gross Profit pada sumber; bukan laba bersih.',
           'Transaksi unik: gabungan kode cabang dan nomor transaksi.',
           'Jika per tanggal/kolom sumber tidak lengkap, growth tidak diklaim.',
           'Data pelanggan, KTP, NPWP, nomor telepon, dan nama kasir tidak diekspor.',
           'Grafik dan angka mengikuti filter aktif saat laporan dibuat.']
    for i,s in enumerate(notes,19):
        ws.merge_range(i,0,i,6,s,sub)
    for sheet_name,group_key in REPORT_SHEETS:
        records=list(grouped.get(group_key,[]))
        sh=wb.add_worksheet(sheet_name)
        sh.hide_gridlines(2)
        sh.freeze_panes(1,0)
        sh.set_tab_color('#CBD5E1')
        cols=_headers(records)
        if not cols:
            sh.write('A1','Tidak tersedia data untuk filter ini.',normal)
            continue
        for j,col in enumerate(cols):
            sh.write(0,j,col.replace('_',' ').title(),header)
            sh.set_column(j,j,35 if col in {'label','item','cabang'} else 19)
        sh.set_row(0,24)
        for i,record in enumerate(records,1):
            for j,key in enumerate(cols):
                value=record.get(key)
                if isinstance(value,(int,float)) and not isinstance(value,bool):
                    fmt=percent if key in {'margin','sales_share','cumulative_share','growth_pct'} else (money if key in {'sales','gross_profit','cost','selisih','sekarang','sebelumnya'} else numeric)
                    sh.write_number(i,j,float(value),fmt)
                else:
                    sh.write_string(i,j,safe_export_text(value),normal)
        sh.autofilter(0,0,len(records),len(cols)-1)
        # Keep the download small; data bars make ranking visually useful.
        if 'sales' in cols and records:
            j=cols.index('sales')
            sh.conditional_format(1,j,len(records),j,{'type':'data_bar','bar_color':'#82B4F7'})
    q=wb.add_worksheet('Kualitas Data')
    q.hide_gridlines(2);q.set_column('A:A',33);q.set_column('B:B',20)
    q.write_row(0,0,['Pemeriksaan','Jumlah'],header)
    for i,(k,v) in enumerate(quality.items(),1):
        q.write_string(i,0,safe_export_text(k),normal)
        if isinstance(v,(float,int)):q.write_number(i,1,v,numeric)
        else:q.write_string(i,1,safe_export_text(v),normal)
    source=wb.add_worksheet('Sumber Import')
    source.hide_gridlines(2);source.set_column('A:A',52)
    source.set_column('B:C',22);source.set_column('D:D',20)
    source.write_row(0,0,['File','Jumlah Baris','Tanggal Import','Hash pendek'],header)
    for i,r in enumerate(sources,1):
        source.write_string(i,0,safe_export_text(r.get('filename','')),normal)
        source.write_number(i,1,int(r.get('rows_inserted',0)),numeric)
        source.write_string(i,2,safe_export_text(r.get('imported_at','')),normal)
        source.write_string(i,3,str(r.get('file_hash',''))[:12],normal)
    wb.close()
    return buf.getvalue()


def make_pdf(summary: Mapping, grouped: Mapping[str,Sequence[dict]],
             quality: Mapping, sources: Sequence[dict], period_text: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
    from reportlab.graphics.shapes import Drawing,Rect,String
    from reportlab.lib.colors import HexColor
    buf=BytesIO()
    navy=HexColor('#14243D');blue=HexColor('#215ED8');muted=HexColor('#5E6E84')
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=35,leftMargin=35,topMargin=38,bottomMargin=35,
                          title='Business AI Analyst V2')
    ss=getSampleStyleSheet()
    ss.add(ParagraphStyle(name='TitleBAI',parent=ss['Heading1'],fontSize=21,leading=24,textColor=navy,spaceAfter=7))
    ss.add(ParagraphStyle(name='HeadBAI',parent=ss['Heading2'],fontSize=12,leading=17,textColor=navy,spaceBefore=17,spaceAfter=7))
    ss.add(ParagraphStyle(name='SmallBAI',parent=ss['Normal'],fontSize=8.5,leading=12,textColor=muted))
    ss.add(ParagraphStyle(name='CellBAI',parent=ss['Normal'],fontSize=8,leading=10,textColor=navy))
    story=[Paragraph('BUSINESS AI ANALYST',ss['TitleBAI']),
           Paragraph('Laporan analisis penjualan - V2',ss['SmallBAI']),
           Spacer(1,12),Paragraph(f'Periode: {escape(period_text)}',ss['SmallBAI']),
           Paragraph('Dibuat: '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),ss['SmallBAI']),Spacer(1,16)]
    overview_data=[['INDIKATOR','NILAI'],
                   ['Omzet sebelum pajak',_idr(summary.get('sales'))],
                   ['Laba kotor',_idr(summary.get('gross_profit'))],
                   ['Margin laba kotor',f"{summary.get('margin',0):.2f}%"],
                   ['Transaksi unik',f"{summary.get('transactions',0):,.0f}"],
                   ['Unit terjual',f"{summary.get('qty',0):,.0f}"],
                   ['Cabang aktif',str(summary.get('branches',0))]]
    t=Table(overview_data,colWidths=[270,230],hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('TEXTCOLOR',(0,0),(-1,0),colors.white),
         ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,HexColor('#F2F6FC')]),
         ('LEFTPADDING',(0,0),(-1,-1),11),('TOPPADDING',(0,0),(-1,-1),8),
         ('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,-1),(-1,-1),.3,HexColor('#CBD5E1'))]))
    story.append(t)
    for sheet_name,key in REPORT_SHEETS[:5]:
        rows=list(grouped.get(key,[]))[:10]
        if not rows:continue
        story.append(Paragraph('Top '+sheet_name,ss['HeadBAI']))
        rows_print=[['#',sheet_name.upper(),'OMZET']]
        for idx,r in enumerate(rows,1):
            nm=r.get('label') or r.get('item') or r.get('cabang') or '(tanpa nama)'
            rows_print.append([str(idx),Paragraph(escape(str(nm)[:65]),ss['CellBAI']),_idr(r.get('sales'))])
        tb=Table(rows_print,colWidths=[28,307,165],hAlign='LEFT',repeatRows=1)
        tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('TEXTCOLOR',(0,0),(-1,0),colors.white),
          ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,HexColor('#F2F6FC')]),
          ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),
          ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.append(tb)
    story.append(Paragraph('Pemeriksaan data',ss['HeadBAI']))
    qrows=[['Keterangan','Jumlah']]+[[escape(k.replace('_',' ').title()),str(v)] for k,v in quality.items()]
    qt=Table(qrows,colWidths=[310,190],hAlign='LEFT',repeatRows=1)
    qt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,HexColor('#F2F6FC')]),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(qt)
    story.append(Spacer(1,15))
    story.append(Paragraph('Catatan: angka berasal dari transaksi terfilter. Gross Profit bukan laba bersih. '
       'Laporan hanya berisi agregat non-PII, bukan nama pelanggan atau rincian personal. '
       'Tidak semua perubahan penjualan memiliki penyebab yang dapat ditentukan dari data transaksi saja.',ss['SmallBAI']))
    story.append(Paragraph('Sumber file: '+str(len(sources))+' impor (nama dan hash di laporan Excel).',ss['SmallBAI']))
    def footer(canvas,document):
        canvas.saveState()
        canvas.setStrokeColor(HexColor('#D8E0EE'))
        canvas.line(35,30,A4[0]-35,30)
        canvas.setFont('Helvetica',8);canvas.setFillColor(muted)
        canvas.drawString(35,19,'Business AI Analyst V2 | Data agregat bisnis')
        canvas.drawRightString(A4[0]-35,19,f'Halaman {document.page}')
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()
