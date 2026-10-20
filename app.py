"""Business AI Analyst V2 - Streamlit Community Cloud / public-source edition.

Preserves the V1 features while adding advanced, transparent business analytics.
Only a visitor's temporary, business-only SQLite dataset is used. No customer PII.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path
import os
import sqlite3
import tempfile
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.engine import (aggregate, create_database, dataset_info, distinct_values,
                        filter_sql, finalize_database, ingest_file, overview, paged_data, trend)
from src.advanced import (enriched_aggregate, quality_report, product_abc, previous_period,
                          anomaly_days, insight_cards, branch_comparison)
from src.assistant import answer_question, explain_with_gemini, idr, num
from src.reports import make_excel, make_pdf
from src.security import check_access, safe_export_text, validate_uploads

st.set_page_config(page_title='Business AI Analyst V2',page_icon='📈',
                   layout='wide', initial_sidebar_state='expanded')

NAV = ['Ringkasan','Cabang','Produk','Kategori & Brand','Advanced Analytics',
       'Data Explorer','AI Analyst','Laporan','Dataset','Panduan']
PALETTE=['#2F68DC','#00B7A4','#F5AA42','#9775FA','#F07182','#20A5CE','#86B75C','#5A6C84']
LABEL_METRIC={'sales':'Omzet (Rp)','gross_profit':'Laba Kotor (Rp)',
              'qty':'Unit Terjual','transactions':'Transaksi Unik','cost':'HPP (Rp)',
              'margin':'Margin Laba Kotor (%)'}


def secret(name: str, default: str = '') -> str:
    try:
        v=st.secrets.get(name,default)
    except Exception:
        v=os.environ.get(name,default)
    return str(v) if v is not None else default


def is_dark() -> bool:
    return st.session_state.get('theme_select','Terang')=='Gelap'


def css():
    dark=is_dark()
    bg='#0D1422' if dark else '#F4F7FC'
    surface='#17263B' if dark else '#FFFFFF'
    sidebar='#111C2E' if dark else '#FFFFFF'
    ink='#F0F6FF' if dark else '#172640'
    dim='#A7BAD2' if dark else '#6F7F96'
    border='#334761' if dark else '#E0E8F2'
    html=f'''<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;600;700;800&display=swap');
    html,body,[class*="css"],.stApp,button,input,textarea {{font-family:Roboto,Arial,sans-serif!important;}}
    [data-testid="stAppViewContainer"] {{background:{bg};color:{ink};}}
    [data-testid="stHeader"] {{background:transparent;}}
    [data-testid="stSidebar"] {{background:{sidebar};border-right:1px solid {border};}}
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{color:{ink};}}
    .block-container {{padding:1.2rem 1.6rem 3rem!important;max-width:1540px;}}
    [data-testid="stMetric"] {{background:{surface};border:1px solid {border};
        border-radius:15px;padding:17px 19px;min-height:108px;box-shadow:0 4px 19px #00000007;}}
    [data-testid="stMetricLabel"] p {{color:{dim};font-size:.83rem;font-weight:600;}}
    [data-testid="stMetricValue"] {{font-size:clamp(1.2rem,2vw,1.7rem);font-weight:800;color:{ink};}}
    [data-testid="stMetricDelta"] p {{font-size:.75rem;}}
    [data-testid="stVerticalBlockBorderWrapper"] {{background:{surface};border-radius:16px;
      border-color:{border};box-shadow:0 4px 16px #00000006;}}
    div[data-testid="stMarkdownContainer"] h1 {{font-size:1.8rem;letter-spacing:-.038em;}}
    div[data-testid="stMarkdownContainer"] h2 {{font-size:1.4rem;letter-spacing:-.028em;}}
    div[data-testid="stMarkdownContainer"] h3 {{font-size:1.08rem;letter-spacing:-.02em;}}
    .stButton button {{border-radius:9px;min-height:38px;font-weight:600;}}
    .stButton>button[kind="primary"] {{background:#2467E9;color:white;border-color:#2467E9;}}
    [data-testid="stDataFrame"] {{border-radius:10px;overflow:hidden;}}
    .bai-top {{background:linear-gradient(110deg,#132B51,#2050A8 64%,#1E76C5);color:white;
        border-radius:18px;padding:22px 27px;margin:4px 0 16px;}}
    .bai-top h1 {{color:#FFF!important;margin:1px 0 5px;font-weight:800;font-size:1.75rem;}}
    .bai-top p {{color:#D6E6FF!important;margin:0;font-size:.88rem;}}
    .bai-eyebrow {{font-size:.69rem;color:#A8D2FF;letter-spacing:.16em;font-weight:800;}}
    .bai-brand {{display:flex;gap:10px;align-items:center;padding:8px 0 17px;}}
    .bai-brandmark {{display:flex;align-items:center;justify-content:center;width:40px;height:40px;
     background:#215ED8;border-radius:13px;color:white;font-size:23px;font-weight:800;}}
    .bai-brandhead {{font-size:1.03rem;font-weight:800;line-height:1.15;color:{ink};}}
    .bai-branddesc {{font-size:.73rem;color:{dim};margin-top:4px;}}
    .bai-chip {{display:inline-block;font-size:.72rem;font-weight:700;background:#DDECFF;color:#185AB9;
      padding:5px 9px;border-radius:8px;}}
    .bai-help {{font-size:.82rem;color:{dim};line-height:1.55;}}
    .bai-insight {{border-left:3px solid #2F68DC;padding:12px 15px;background:{surface};
       border-radius:0 9px 9px 0;border-top:1px solid {border};
       border-bottom:1px solid {border};border-right:1px solid {border};margin-bottom:10px;}}
    .bai-insight-title {{font-weight:700;color:{ink};font-size:.85rem;}}
    .bai-insight-body {{font-size:.83rem;color:{dim};margin-top:5px;}}
    .bai-footer {{font-size:.75rem;color:{dim};margin-top:20px;}}
    [data-testid="stFileUploader"] section {{border:1px dashed #93B5EB;border-radius:12px;}}
    @media (max-width:800px) {{.block-container{{padding:.75rem .6rem 2rem!important;}}
       .bai-top{{padding:17px 16px;border-radius:13px;}}.bai-top h1{{font-size:1.33rem;}}
       [data-testid="stMetric"]{{padding:11px 12px;min-height:86px;}}
       [data-testid="stMetricValue"]{{font-size:1.08rem;}}
    }}
    </style>'''
    st.markdown(html,unsafe_allow_html=True)


def hero(title: str, subtitle: str, eyebrow: str='BUSINESS INTELLIGENCE / V2'):
    # Escape any app-supplied text before writing HTML.
    st.markdown(f'<div class="bai-top"><div class="bai-eyebrow">{escape(eyebrow)}</div>'
                f'<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>',unsafe_allow_html=True)


def chart_style(fig, height:int=380,legend:bool=True):
    fg='#D7E4F5' if is_dark() else '#52627B'
    plotbg='#17263B' if is_dark() else '#FFFFFF'
    fig.update_layout(height=height,margin=dict(l=8,r=9,t=19,b=14),
        paper_bgcolor=plotbg,plot_bgcolor=plotbg,
        font=dict(family='Roboto,Arial,sans-serif',size=11,color=fg),
        hoverlabel=dict(bgcolor='#FFFFFF',font_color='#233248'),
        showlegend=legend,legend=dict(orientation='h',y=-.27))
    fig.update_xaxes(showgrid=False,zeroline=False)
    fig.update_yaxes(showgrid=True,gridcolor='#E2E8F020' if is_dark() else '#EDF1F7',zeroline=False)
    return fig


def money_short(v):
    v=float(v or 0)
    if abs(v)>=1e12:return f'Rp{v/1e12:,.2f} T'.replace(',','~').replace('.',',').replace('~','.')
    if abs(v)>=1e9:return f'Rp{v/1e9:,.2f} M'.replace(',','~').replace('.',',').replace('~','.')
    if abs(v)>=1e6:return f'Rp{v/1e6:,.2f} jt'.replace(',','~').replace('.',',').replace('~','.')
    if abs(v)>=1e3:return f'Rp{v/1e3:,.1f} rb'.replace(',','~').replace('.',',').replace('~','.')
    return idr(v)


def simple_csv(df:pd.DataFrame)->bytes:
    out=df.copy()
    for col in out.select_dtypes(include=['object','string']).columns:
        out[col]=out[col].map(safe_export_text)
    return ('\ufeff'+out.to_csv(index=False)).encode('utf-8')


def cleanup_expired_databases(max_hours:int=8):
    # Best-effort cleanup of temporary, business-only databases after inactivity.
    cutoff=time.time()-max_hours*3600
    for f in Path(tempfile.gettempdir()).glob('bai_session_*.sqlite3'):
        try:
            if f.is_file() and not f.is_symlink() and f.stat().st_mtime<cutoff:
                f.unlink()
        except OSError:pass


def reset_cache():
    for k in ('memo','messages','reports_bytes','reports_signature','filters_signature'):
        st.session_state.pop(k,None)


def memo_call(func,*args,**kwargs):
    """Per-session aggregate cache; never share private results across users."""
    memo=st.session_state.setdefault('memo',OrderedDict())
    key=repr((func.__name__,args,kwargs))
    if key in memo:
        memo.move_to_end(key)
        return memo[key]
    result=func(*args,**kwargs)
    memo[key]=result
    if len(memo)>42:memo.popitem(last=False)
    return result


def process_import(files,append:bool,demo:bool=False):
    valid,reason=validate_uploads(files)
    if not valid:
        st.error(reason);return
    if append and st.session_state.get('dataset_mode')=='demo' and not demo:
        st.error('Data asli tidak boleh digabung ke data demo. Pilih Ganti dataset.');return
    current=st.session_state.get('db_path') if append else None
    new_path=create_database()
    stats=[]
    bar=st.progress(0,text='Menyiapkan analisis...')
    try:
        if current and Path(current).exists():
            bar.progress(3,text='Menyalin dataset sesi ke database sementara...')
            with sqlite3.connect(current) as src,sqlite3.connect(new_path) as dst:
                src.backup(dst,pages=600)
        for i,f in enumerate(files):
            bar.progress(max(5,int(i/len(files)*85)),text=f'Membaca {f.name} ...')
            try:
                stats.append(ingest_file(new_path,f,f.name))
            except ValueError as exc:
                if 'sudah diimpor' in str(exc):
                    st.warning(f'File identik dilewati: {f.name}')
                else:raise
        if not stats:
            st.info('Tidak ada data baru. Dataset lama tidak berubah.');return
        bar.progress(92,text='Membangun indeks SQL...')
        finalize_database(new_path)
        if dataset_info(new_path)['rows']>850_000:
            raise ValueError('Gabungan lebih dari 850.000 baris. Pisahkan dataset untuk kapasitas cloud gratis.')
        old=st.session_state.get('db_path')
        st.session_state['db_path']=new_path
        st.session_state['dataset_mode']='demo' if demo else 'live'
        st.session_state['last_import_stats']=stats
        st.session_state['upload_version']=st.session_state.get('upload_version',0)+1
        reset_cache()
        if old and old!=new_path:
            Path(old).unlink(missing_ok=True)
        bar.progress(100,text='Selesai')
        st.rerun()
    except Exception as exc:
        # Do not leak Python tracebacks, secret environment, or raw content.
        st.error(f'Import gagal: {str(exc)[:450]}')
    finally:
        if st.session_state.get('db_path')!=new_path:
            Path(new_path).unlink(missing_ok=True)


def load_demo():
    demo=Path(__file__).parent/'examples'/'demo_sales.csv'
    f=BytesIO(demo.read_bytes());f.name='demo_sales.csv';f.size=len(f.getvalue())
    process_import([f],append=False,demo=True)


def delete_session():
    current=st.session_state.pop('db_path',None)
    if current:
        try:Path(current).unlink(missing_ok=True)
        except OSError:pass
    reset_cache()
    st.session_state['upload_version']=st.session_state.get('upload_version',0)+1
    st.rerun()


def access_screen(password: str):
    if not password:
        return True
    if st.session_state.get('access_ok'):
        return True
    hero('Akses Business AI Analyst','Masukkan kata sandi yang diberikan pengelola aplikasi.','AKSES TERBATAS')
    _,center,_=st.columns([1,1.2,1])
    with center:
        with st.form('gate'):
            provided=st.text_input('Kata sandi',type='password',max_chars=200)
            go=st.form_submit_button('Masuk ke Aplikasi',type='primary',use_container_width=True)
        if go:
            failed=st.session_state.get('login_failures',0)
            last=st.session_state.get('login_last_failure',0)
            if failed>=5 and time.time()-last<300:
                st.error('Terlalu banyak percobaan. Tunggu 5 menit lalu coba lagi.')
            elif check_access(provided,password):
                st.session_state['access_ok']=True
                st.session_state['login_failures']=0
                st.rerun()
            else:
                st.session_state['login_failures']=failed+1
                st.session_state['login_last_failure']=time.time()
                st.error('Kata sandi tidak sesuai.')
        st.caption('Kata sandi dibaca dari Secrets di Streamlit, bukan dari source GitHub.')
    st.stop()


def bar_plot(rows:list,metric:str='sales',h:int=390,title=''):
    if not rows:
        st.info('Tidak ada data pada filter ini.');return
    frame=pd.DataFrame(rows[:16]).iloc[::-1]
    fig=go.Figure(go.Bar(x=frame[metric],y=frame['label'].str.slice(0,33),
        orientation='h',marker_color=PALETTE[0],marker_line_width=0,
        customdata=frame['label'],hovertemplate='%{customdata}<br>%{x:,.0f}<extra></extra>'))
    st.plotly_chart(chart_style(fig,h,False),use_container_width=True,
                    config={'displaylogo':False})


def trend_plot(data:list,xlabel='Tanggal',metric='sales'):
    if not data:
        st.info('Tidak ada data pada periode ini.');return
    df=pd.DataFrame(data)
    x=df['period']; y=df[metric]
    fig=go.Figure(go.Scatter(x=x,y=y,mode='lines+markers',
        line={'width':3,'color':PALETTE[0]},marker={'size':6},
        fill='tozeroy',fillcolor='rgba(47,104,220,0.075)',name='Omzet',
        hovertemplate='%{x}<br>Rp%{y:,.0f}<extra></extra>'))
    fig.update_layout(xaxis_title=xlabel,yaxis_title='Rupiah')
    st.plotly_chart(chart_style(fig,330,False),use_container_width=True,
                    config={'displaylogo':False})


def show_table_export(df:pd.DataFrame,filename:str,height:int=450):
    st.dataframe(df,use_container_width=True,hide_index=True,height=height)
    st.download_button('Unduh CSV ringkasan',simple_csv(df),filename,
                       'text/csv',key='download_'+filename,use_container_width=False)


def filter_controls(db):
    info=memo_call(dataset_info,db)
    dmin=date.fromisoformat(info['min_date']);dmax=date.fromisoformat(info['max_date'])
    st.sidebar.caption('FILTER ANALISIS')
    start=st.sidebar.date_input('Mulai',value=dmin,min_value=dmin,max_value=dmax)
    end=st.sidebar.date_input('Sampai',value=dmax,min_value=dmin,max_value=dmax)
    stores=st.sidebar.multiselect('Cabang',memo_call(distinct_values,db,'store'),placeholder='Semua cabang')
    categories=st.sidebar.multiselect('Kategori',memo_call(distinct_values,db,'category'),placeholder='Semua kategori')
    statuses=memo_call(distinct_values,db,'status')
    default=['Completed'] if 'Completed' in statuses else statuses
    chosen=st.sidebar.multiselect('Status transaksi',statuses,default=default)
    with st.sidebar.expander('Filter lanjutan',expanded=False):
        brands=st.multiselect('Brand',memo_call(distinct_values,db,'brand'))
        suppliers=st.multiselect('Supplier',memo_call(distinct_values,db,'supplier'))
    if start>end:st.error('Tanggal awal lebih besar dari tanggal akhir.');st.stop()
    if statuses and not chosen:st.warning('Pilih minimal satu status transaksi.');st.stop()
    where,params=filter_sql(start.isoformat(),end.isoformat(),stores,categories,chosen,brands,suppliers)
    context={'start':start,'end':end,'stores':stores,'categories':categories,
             'statuses':chosen,'brands':brands,'suppliers':suppliers}
    signature=repr((str(db),where,params))
    if st.session_state.get('filters_signature')!=signature:
        # Keep chat answers tied to the data/filters used to calculate them.
        st.session_state['messages']=[]
        st.session_state['filters_signature']=signature
        st.session_state.pop('reports_bytes',None)
        st.session_state.pop('reports_signature',None)
    return info,where,params,context


def overview_page(db,where,params,info,filters):
    hero('Business Overview','Ringkasan penjualan, profitabilitas dan aktivitas usaha dari dataset terfilter.')
    o=memo_call(overview,db,where,params)
    if not o['rows']:
        st.warning('Tidak ada data pada filter tersebut.');return
    comp=memo_call(previous_period,db,filters['start'],filters['end'],filters['stores'],
                   filters['categories'],filters['statuses'],filters['brands'],filters['suppliers'])
    change=f"{comp['growth_pct']:+.2f}% vs periode lalu" if comp['growth_pct'] is not None else None
    a,b,c,d=st.columns(4)
    a.metric('TOTAL OMZET',money_short(o['sales']),delta=change,delta_color='normal')
    b.metric('LABA KOTOR',money_short(o['gross_profit']))
    c.metric('MARGIN KOTOR',f"{o['margin']:.2f}%")
    d.metric('TRANSAKSI',num(o['transactions']))
    e,f,g,h=st.columns(4)
    e.metric('UNIT TERJUAL',num(o['qty']))
    f.metric('CABANG AKTIF',num(o['branches']))
    g.metric('SKU AKTIF',num(o['products']))
    h.metric('OMZET + PAJAK',money_short(o['sales_inc_tax']))
    if comp['growth_pct'] is None:
        st.caption('Pertumbuhan tidak ditampilkan: perlu data lengkap untuk dua periode setara. Data satu tanggal tetap dianalisis per jam.')
    c1,c2=st.columns([1.68,1],gap='medium')
    with c1:
        with st.container(border=True):
            st.subheader('Tren Penjualan')
            one_day=o['days']==1
            series=memo_call(trend,db,where,params,one_day)
            trend_plot(series,'Jam' if one_day else 'Tanggal')
    with c2:
        with st.container(border=True):
            st.subheader('Kontribusi Kategori')
            rows=memo_call(aggregate,db,where,params,'category','sales',8,False)
            if rows:
                df=pd.DataFrame(rows)
                fig=px.pie(df,names='label',values='value',hole=.63,color_discrete_sequence=PALETTE)
                fig.update_traces(textinfo='percent',hovertemplate='%{label}: Rp%{value:,.0f}<extra></extra>')
                st.plotly_chart(chart_style(fig,350,True),use_container_width=True,config={'displaylogo':False})
    left,right=st.columns(2,gap='medium')
    with left:
        with st.container(border=True):
            st.subheader('Cabang dengan Omzet Tertinggi')
            bar_plot(memo_call(aggregate,db,where,params,'store','sales',12,False))
    with right:
        with st.container(border=True):
            st.subheader('Produk dengan Omzet Tertinggi')
            bar_plot(memo_call(aggregate,db,where,params,'item','sales',12,False))
    st.subheader('Insight Otomatis')
    insights=memo_call(insight_cards,db,where,params)
    c1,c2=st.columns(2)
    for i,card in enumerate(insights):
        box=c1 if i%2==0 else c2
        with box:
            st.markdown('<div class="bai-insight"><div class="bai-insight-title">'+escape(card['title'])+
                        ' — '+escape(str(card['value']))+'</div><div class="bai-insight-body">'+
                        escape(card['detail'])+'</div></div>',unsafe_allow_html=True)
    with st.expander('Transparansi angka dan filter aktif'):
        st.write(f"Data asli terdeteksi {num(info['rows'])} baris, tanggal {info['min_date']} s.d. {info['max_date']}. "
                 f"Filter aktif: {num(o['rows'])} baris dan {o['days']} tanggal.")
        st.write('Omzet = SUM(Sales), Laba Kotor = SUM(Gross Profit), Margin = Laba Kotor / Omzet. '
                 'Transaksi unik = gabungan Store Code + Sales Ref Code jika tersedia. Ini bukan audit keuangan.')


def branches_page(db,where,params,filters):
    hero('Branch Performance','Bandingkan kontribusi cabang, margin, transaksi, dan perubahan penjualan.')
    metric=st.selectbox('Urut berdasarkan',['sales','gross_profit','qty','transactions','margin'],
                        format_func=lambda x:LABEL_METRIC[x])
    rows=memo_call(enriched_aggregate,db,where,params,'store',metric,500,False)
    if not rows:st.info('Belum ada data cabang.');return
    if metric=='margin':rows=[r for r in rows if r['margin'] is not None and r['sales']>0]
    top=rows[0]
    a,b,c=st.columns(3)
    a.metric('Cabang terfilter',num(len(rows)))
    b.metric('Cabang peringkat 1',top['label'][:29])
    c.metric('Omzet top cabang',money_short(top['sales']))
    with st.container(border=True):
        st.subheader('Peringkat Cabang')
        if metric!='margin':bar_plot(rows,metric,460)
        else:
            st.bar_chart(pd.DataFrame(rows[:20]).set_index('label')['margin'])
    frame=pd.DataFrame(rows)
    frame=frame.rename(columns={'label':'Cabang','sales':'Omzet','gross_profit':'Laba Kotor',
       'cost':'HPP','qty':'Unit','transactions':'Transaksi','margin':'Margin (%)','lines':'Baris'})
    st.subheader('Detail Per Cabang')
    show_table_export(frame,'peringkat_cabang.csv',500)
    with st.expander('Perbandingan dengan periode sebelumnya'):
        cmp=memo_call(branch_comparison,db,filters['start'],filters['end'],filters['stores'],
             filters['categories'],filters['statuses'],filters['brands'],filters['suppliers'],100)
        if cmp['info']['comparable']:
            st.dataframe(pd.DataFrame(cmp['rows']),hide_index=True,use_container_width=True)
        else:st.info(cmp['info']['why_not'])


def products_page(db,where,params):
    hero('Product Intelligence','Rangking produk berdasarkan omzet, kuantitas, profit, dan klasifikasi ABC.')
    tb1,tb2=st.tabs(['Peringkat Produk','ABC / Pareto'])
    with tb1:
        metric=st.selectbox('Metrik produk',['sales','qty','gross_profit'],
                             format_func=lambda m:LABEL_METRIC[m],key='prodmetric')
        rows=memo_call(enriched_aggregate,db,where,params,'item',metric,200,False)
        with st.container(border=True):
            st.subheader('20 Produk Teratas')
            bar_plot(rows,metric,490)
        if rows:
            df=pd.DataFrame(rows).rename(columns={'label':'Produk','sales':'Omzet',
                'gross_profit':'Laba Kotor','cost':'HPP','qty':'Unit',
                'transactions':'Transaksi','margin':'Margin (%)','lines':'Baris'})
            show_table_export(df,'peringkat_produk.csv',520)
    with tb2:
        result=memo_call(product_abc,db,where,params,200)
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Total SKU',num(result['total_skus']))
        for col,key in [(c2,'A'),(c3,'B'),(c4,'C')]:
            col.metric('Kelas '+key,num(result['classes'][key]))
        st.caption('ABC dihitung dari seluruh SKU dan kontribusi omzet positif, bukan hanya 200 produk yang terlihat.')
        if result['has_nonpositive_sales']:
            st.warning('Ada SKU dengan omzet nol/negatif. Interpretasikan klasifikasi dengan memperhatikan retur/koreksi.')
        abc=pd.DataFrame(result['items']).rename(columns={'sku':'SKU','item':'Produk','sales':'Omzet',
            'qty':'Qty','gross_profit':'Laba Kotor','sales_share':'Share (%)',
            'cumulative_share':'Kumulatif (%)','abc':'Kelas ABC'})
        if not abc.empty:
            show_table_export(abc,'analisis_abc.csv',520)


def categories_page(db,where,params):
    hero('Category, Brand & Supplier','Pahami kontribusi dan profitabilitas menurut kelompok bisnis.')
    tabs=st.tabs(['Kategori','Brand','Supplier'])
    for tab,dim,filename in zip(tabs,['category','brand','supplier'],
                                ['kategori','brand','supplier']):
        with tab:
            metric=st.selectbox('Urut berdasarkan',['sales','qty','gross_profit','margin'],
                format_func=lambda m:LABEL_METRIC[m],key='metric_'+dim)
            rows=memo_call(enriched_aggregate,db,where,params,dim,metric,100,False)
            if metric=='margin':rows=[r for r in rows if r['margin'] is not None and r['sales']>0]
            if not rows:st.info('Tidak ada data.');continue
            with st.container(border=True):
                st.subheader('Peringkat '+filename.title())
                bar_plot(rows,metric,460) if metric!='margin' else st.bar_chart(
                    pd.DataFrame(rows[:16]).set_index('label')['margin'])
            data=pd.DataFrame(rows).rename(columns={'label':filename.title(),'sales':'Omzet',
                'gross_profit':'Laba Kotor','cost':'HPP','qty':'Unit',
                'transactions':'Transaksi','margin':'Margin (%)'})
            show_table_export(data,f'analisis_{filename}.csv',420)


def advanced_page(db,where,params,filters):
    hero('Advanced Analytics','Bandingkan periode, deteksi sinyal anomali, audit kualitas, dan analisis portofolio.')
    tb1,tb2,tb3,tb4=st.tabs(['Perbandingan Periode','Anomali Penjualan','Kualitas Data','Produktivitas'])
    with tb1:
        result=memo_call(previous_period,db,filters['start'],filters['end'],filters['stores'],
            filters['categories'],filters['statuses'],filters['brands'],filters['suppliers'])
        a,b,c=st.columns(3)
        a.metric('Omzet saat ini',money_short(result['current']['sales']))
        b.metric('Omzet periode lalu',money_short(result['previous']['sales']))
        if result['growth_pct'] is None:
            c.metric('Growth','Tidak tersedia')
            st.warning(result['why_not'] or 'Pembanding dengan omzet nol; perubahan persen tidak terdefinisi.')
        else:
            c.metric('Growth',f"{result['growth_pct']:+.2f}%")
            data=memo_call(branch_comparison,db,filters['start'],filters['end'],filters['stores'],
                filters['categories'],filters['statuses'],filters['brands'],filters['suppliers'],80)
            if data['rows']:
                st.subheader('Kontributor Perubahan Cabang')
                df=pd.DataFrame(data['rows'])
                st.dataframe(df,use_container_width=True,hide_index=True)
        st.caption(f"Periode: {result['current_start']} s.d. {result['current_end']} | "
                   f"Pembanding: {result['prior_start']} s.d. {result['prior_end']}")
    with tb2:
        out=memo_call(anomaly_days,db,where,params)
        st.info(out['note'])
        if out['series']:
            trend_plot([{'period':r['period'],'sales':r['sales']} for r in out['series']],'Tanggal')
        if out['signals']:
            st.dataframe(pd.DataFrame(out['signals']),use_container_width=True,hide_index=True)
        elif out['enough_data']:
            st.success('Tidak ditemukan sinyal anomali kuat pada periode ini.')
    with tb3:
        q=memo_call(quality_report,db,where,params)
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Baris dicek',num(q['rows']))
        c2.metric('SKU kosong',num(q['missing_sku']))
        c3.metric('Sales negatif',num(q['negative_sales']))
        c4.metric('Profit negatif',num(q['negative_gross_profit']))
        st.dataframe(pd.DataFrame([{'Pemeriksaan':k.replace('_',' ').title(),'Jumlah':v}
                                   for k,v in q.items()]),use_container_width=True,hide_index=True)
        st.caption('Nilai nol/negatif bisa terjadi karena retur/penyesuaian. Selisih Gross Profit terhadap Sales − Cost bisa disebabkan basis pajak atau diskon; perlu definisi laporan untuk rekonsiliasi.')
    with tb4:
        v=memo_call(overview,db,where,params)
        a,b,c=st.columns(3)
        a.metric('Rata-rata nilai transaksi',money_short(v['basket']))
        c.metric('Baris per transaksi',f"{v['rows']/v['transactions']:.1f}" if v['transactions'] else 'N/A')
        b.metric('Unit per transaksi',f"{v['qty']/v['transactions']:.2f}" if v['transactions'] else 'N/A')
        st.caption('Dihitung dari transaksi dengan kode referensi. Tidak semua source wajib memiliki kode referensi.')


def explorer_page(db,where,params):
    hero('Data Explorer','Lihat transaksi tanpa data pelanggan, dengan pagination dan ekspor terbatas.')
    a,b=st.columns([1,2])
    with a:size=st.selectbox('Baris per halaman',[25,50,100],index=1)
    with b:page=st.number_input('Halaman',min_value=1,step=1,value=1)
    total,rows=memo_call(paged_data,db,where,params,page,size)
    n_pages=max(1,(total+size-1)//size)
    if page>n_pages:
        st.warning(f'Maksimal halaman adalah {n_pages}.');return
    st.caption(f"{num(total)} baris terfilter • Halaman {page} dari {n_pages}")
    data=pd.DataFrame(rows)
    st.dataframe(data,use_container_width=True,hide_index=True,height=575)
    if not data.empty:
        st.download_button('Unduh CSV halaman ini (tanpa PII)',simple_csv(data),
                           'preview_transaksi.csv','text/csv')
    st.info('Hanya preview halaman aktif yang dapat diunduh. Kolom pelanggan dan pegawai tidak pernah disalin ke database analitik.')


def ai_page(db,where,params,info,filters):
    hero('Ask Business AI','Tanya omzet, perbandingan periode, margin, cabang, ABC, dan anomali menggunakan bahasa Indonesia.')
    key=secret('GEMINI_API_KEY')
    if not key:
        st.caption('Mode analitik deterministik aktif (gratis, tidak membutuhkan API). '
                   'AI generatif opsional dapat diaktifkan via Streamlit Secrets.')
    else:
        st.info('Kunci AI generatif tersedia. Aktifkan hanya jika setuju pertanyaan dan ringkasan agregat dikirim ke penyedia AI.')
    use_ai=st.checkbox('Gunakan interpretasi AI generatif (opsional)',disabled=not bool(key),value=False,
       help='Teks pertanyaan dan agregat bisnis akan dikirim ke Gemini; tidak pernah file Excel penuh atau kolom pelanggan.')
    prompts=['Ringkaskan performa penjualan','Top 10 cabang berdasarkan omzet',
       'Top 10 produk berdasarkan qty','Kategori dengan laba tertinggi',
       'Bagaimana growth omzet dibanding periode sebelumnya?',
       'Analisis ABC produk','Cari anomali omzet harian','Periksa kualitas data']
    st.markdown('**Tanya cepat**')
    cs=st.columns(4)
    clicked=None
    for i,label in enumerate(prompts):
        with cs[i%4]:
            if st.button(label,key='ai_prompt_'+str(i),use_container_width=True):clicked=label
    messages=st.session_state.setdefault('messages',[])
    for m in messages[-24:]:
        with st.chat_message(m['role']):
            st.markdown(m['content'])
            if m.get('table'):
                st.dataframe(pd.DataFrame(m['table']),use_container_width=True,hide_index=True)
    prompt=clicked or st.chat_input('Contoh: Mengapa omzet turun? Tampilkan kontribusi cabang.')
    if prompt:
        prompt=prompt[:1300]
        with st.chat_message('user'):st.markdown(prompt)
        with st.chat_message('assistant'):
            with st.spinner('Menghitung dari dataset...'):
                res=answer_question(prompt,db,where,params,period_context=filters)
                answer=res['answer']
                if use_ai and res.get('context'):
                    try:answer+='\n\n---\n**Penjelasan AI generatif:**\n\n'+explain_with_gemini(prompt,res,key)
                    except Exception as exc:answer+='\n\n*AI generatif tidak tersedia saat ini; hasil hitungan lokal tetap ditampilkan.*'
            st.markdown(answer)
            if res.get('table'):st.dataframe(pd.DataFrame(res['table']),use_container_width=True,hide_index=True)
            st.caption('Sumber: dataset sesi ini + filter aktif + analisis SQL tervalidasi.')
        messages.append({'role':'user','content':prompt})
        messages.append({'role':'assistant','content':answer,'table':res.get('table',[])})
        if len(messages)>26:del messages[:-26]
    if messages and st.button('Hapus riwayat chat'):
        st.session_state['messages']=[];st.rerun()


def report_page(db,where,params,filters,info):
    hero('Report Center','Buat PDF dan Excel profesional dari angka agregat sesuai filter saat ini.')
    v=memo_call(overview,db,where,params)
    period_text=f"{filters['start'].isoformat()} s.d. {filters['end'].isoformat()}"
    st.caption(f"Laporan akan mengikuti periode {period_text}, pilihan cabang, kategori, brand, supplier, dan status.")
    with st.container(border=True):
        a,b,c=st.columns(3)
        a.metric('Omzet terfilter',money_short(v['sales']))
        b.metric('Profit kotor terfilter',money_short(v['gross_profit']))
        c.metric('Baris terfilter',num(v['rows']))
        st.markdown('**Isi laporan:** Ringkasan KPI, peringkat cabang, produk, kategori, brand, supplier, '
                    'tren penjualan, kualitas data, dan sumber import. Tidak menyertakan identitas pelanggan.')
        if st.button('Buat laporan PDF & Excel',type='primary',use_container_width=True):
            with st.spinner('Menghitung agregat dan membuat file laporan...'):
                groups={}
                for dim,key in [('store','cabang'),('item','produk'),('category','kategori'),
                                ('brand','brand'),('supplier','supplier')]:
                    groups[key]=memo_call(enriched_aggregate,db,where,params,dim,'sales',200,False)
                groups['tren']=memo_call(trend,db,where,params,False)
                quality=memo_call(quality_report,db,where,params)
                st.session_state['reports_bytes']={
                    'xlsx':make_excel(v,groups,quality,info['imports'],period_text),
                    'pdf':make_pdf(v,groups,quality,info['imports'],period_text)}
                st.session_state['reports_signature']=st.session_state.get('filters_signature')
                st.success('Laporan siap diunduh.')
    if st.session_state.get('reports_bytes') and (
        st.session_state.get('reports_signature')==st.session_state.get('filters_signature')):
        r=st.session_state['reports_bytes']
        c1,c2=st.columns(2)
        with c1:
            st.download_button('Unduh Laporan Excel (.xlsx)',r['xlsx'],
                'Business_Analyst_V2_Report.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True)
        with c2:
            st.download_button('Unduh Laporan PDF (.pdf)',r['pdf'],
                'Business_Analyst_V2_Report.pdf',mime='application/pdf',use_container_width=True)
        st.caption('Laporan disiapkan di memori sesi dan tidak diunggah otomatis ke GitHub.')


def dataset_page(db,info):
    hero('Dataset Manager','Kelola sumber Excel, pantau jumlah baris, dan cegah impor file identik.')
    a,b,c,d=st.columns(4)
    a.metric('Total baris',num(info['rows']))
    b.metric('File sumber',num(len(info['imports'])))
    c.metric('Cabang',num(info['branches']))
    d.metric('SKU',num(info['products']))
    if st.session_state.get('dataset_mode')=='demo':
        st.info('Kamu sedang menggunakan dataset simulasi, bukan data bisnis asli.')
    st.subheader('Riwayat Import dalam Sesi')
    df=pd.DataFrame(info['imports'])
    if not df.empty:
        df['file_hash']=df['file_hash'].str[:12]
        df=df.rename(columns={'filename':'Nama File','rows_inserted':'Baris Terimpor',
            'rows_bad_date':'Tanggal Invalid','rows_bad_numbers':'Angka Invalid','file_hash':'SHA256 (12)','imported_at':'Waktu Import'})
        st.dataframe(df,use_container_width=True,hide_index=True)
    st.warning('Database bersifat sementara per sesi. Restart server atau penutupan sesi dapat menghapus data. '
               'Jangan gunakan untuk arsip perusahaan jangka panjang.')
    if st.button('Hapus semua data sesi',type='secondary'):
        delete_session()


def guide_page():
    hero('Panduan & Keamanan','Penjelasan tentang cara kerja aplikasi dan perlindungan data bisnis.')
    with st.expander('Cara upload beberapa Excel',expanded=True):
        st.markdown('''1. Klik **Upload Excel** di sidebar.
        2. Pilih hingga 12 file .xlsx/.csv (maksimal 65 MB per file, total 95 MB per proses).
        3. Pilih **Ganti dataset** untuk analisis baru atau **Tambahkan** untuk menggabungkan periode.
        4. Centang konfirmasi izin mengunggah data, lalu klik **Proses File**.
        5. Setelah selesai, gunakan menu Ringkasan, Cabang, Produk, AI Analyst, dan Laporan.

        File identik dikenali melalui hash dan tidak diimpor dua kali. File **berbeda** yang
        mengandung transaksi sama masih dapat terhitung ganda. Periksa rentang dan sumbernya.''')
    with st.expander('Definisi metrik'):
        st.markdown('''- **Omzet**: SUM(Sales), sebelum pajak.
        - **Laba kotor**: SUM(Gross Profit), bukan laba bersih.
        - **Margin kotor**: 100 × laba kotor / omzet.
        - **Transaksi unik**: kombinasi Store Code + Sales Ref Code (jika tersedia).
        - **Growth**: hanya ditampilkan bila periode sekarang dan pembanding punya jumlah hari penuh.
        - **ABC**: kelas A (kontribusi kumulatif awal 80%), B (80–95%), C (sisanya).''')
    with st.expander('Keamanan & privasi'):
        st.markdown('''- File Excel asli **tidak** ikut di-commit ke GitHub.
        - Importer memakai daftar putih kolom bisnis; NPWP, KTP, customer, telepon, dan nama kasir diabaikan.
        - Perhitungan diproses sementara **di server** Streamlit, bukan sepenuhnya di perangkat lokal.
        - Data sesi dipisah dengan database SQLite temporer dan dihapus saat pengguna memilih reset,
          serta dibersihkan otomatis secara best-effort ketika sudah lama tidak aktif.
        - **Jika ingin data rahasia**, aktifkan APP_ACCESS_PASSWORD lewat Streamlit Secrets; ini
          hanya shared-password MVP, **bukan login individual tingkat perusahaan**.
        - Jika mengaktifkan Gemini, pertanyaan dan ringkasan agregat dikirim ke penyedia AI dengan
          persetujuan pengguna; file mentah tidak dikirim.
        - Jangan unggah data bisnis yang belum diizinkan perusahaan ke hosting publik gratis.''')
    with st.expander('Batas gratis dan optimasi'):
        st.markdown('''- Streamlit Community Cloud dapat tidur atau me-restart aplikasi kapan saja.
        - CSV lebih ringan untuk impor. XLSX diproses streaming dari XML untuk mengurangi RAM.
        - Statistik disimpan dalam SQLite temporer; halaman Explorer memakai pagination.
        - Cache agregat hanya di session_state pengguna, tidak digunakan lintas user.
        - Tidak ada auto-backup permanen, multi-user account, scheduled job, atau SLA.''')
    st.caption('Business AI Analyst V2 • Perhitungan bisnis deskriptif, bukan audit keuangan.')


# ------- App entrance -------
css()
configured_password=secret('APP_ACCESS_PASSWORD')
access_screen(configured_password)
if 'ran_cleanup' not in st.session_state:
    cleanup_expired_databases()
    st.session_state['ran_cleanup']=True

with st.sidebar:
    st.markdown('<div class="bai-brand"><div class="bai-brandmark">◆</div>'
        '<div><div class="bai-brandhead">Business AI Analyst</div>'
        '<div class="bai-branddesc">Smart Business Intelligence • V2</div></div></div>',
        unsafe_allow_html=True)
    st.caption('WORKSPACE')
    nav=st.radio('Menu',NAV,label_visibility='collapsed',key='nav_current')
    st.divider()
    st.caption('UPLOAD EXCEL / CSV')
    st.caption('File sementara per sesi • .xlsx / .csv • 65 MB per file')
    uploaded=st.file_uploader('Pilih file penjualan',type=['xlsx','csv'],accept_multiple_files=True,
        key='bai_upload_'+str(st.session_state.get('upload_version',0)),
        help='Gunakan format Detailed Sales. Data pelanggan tidak diambil ke database analitik.')
    exists=bool(st.session_state.get('db_path'))
    import_mode=st.radio('Cara memproses',('Ganti dataset','Tambahkan'),
        horizontal=True,disabled=not exists)
    consent=st.checkbox('Saya berwenang mengunggah data ini ke server.',value=False,
        help='Data file mentah transit di server Streamlit. Jangan unggah informasi rahasia tanpa izin.')
    if st.button('Proses File',type='primary',use_container_width=True):
        if not consent:st.warning('Centang persetujuan terlebih dahulu.')
        else:process_import(uploaded,append=exists and import_mode=='Tambahkan')
    if st.button('Gunakan Data Demo',use_container_width=True):
        load_demo()
    if exists:
        if st.button('Hapus Data Sesi',use_container_width=True):delete_session()
    st.divider()
    st.selectbox('Tema tampilan',['Terang','Gelap'],key='theme_select')
    if configured_password:
        st.caption('Akses dilindungi kata sandi.')
        if st.button('Keluar',use_container_width=True):
            st.session_state['access_ok']=False
            if exists:
                current=st.session_state.pop('db_path',None)
                if current:Path(current).unlink(missing_ok=True)
            reset_cache();st.rerun()
    else:
        st.caption('Aplikasi publik: setiap pengunjung dapat mencoba data demo atau mengunggah datanya sendiri.')

# Ensure stale db path is never reused silently after Streamlit restart.
db=st.session_state.get('db_path')
if db and not Path(db).exists():
    st.session_state.pop('db_path',None);reset_cache();db=None
if db:
    try:os.utime(db,None)
    except OSError:pass

if not db:
    hero('Data to Decisions','Business intelligence profesional untuk membaca laporan Excel bisnis.')
    st.markdown('<span class="bai-chip">Streamlit Cloud • MVP Gratis • V2</span>',unsafe_allow_html=True)
    st.write('Upload beberapa file Detailed Sales, gabungkan periode, analisis omzet dan laba kotor, '
             'temukan peluang lewat ABC dan anomali, lalu ekspor PDF dan Excel.')
    c1,c2,c3=st.columns(3)
    with c1:
        with st.container(border=True):
            st.subheader('01  Smart Import')
            st.write('Parser XLSX streaming untuk ratusan ribu baris; multi-file, cek file identik, dan filter kolom bisnis.')
    with c2:
        with st.container(border=True):
            st.subheader('02  Advanced Analytics')
            st.write('Dashboard, grafik, margin, kontribusi cabang, produk ABC, dan indikator kualitas data.')
    with c3:
        with st.container(border=True):
            st.subheader('03  AI + Reporting')
            st.write('Tanya-jawab berbasis SQL yang dapat diaudit, AI generatif opsional, ekspor laporan PDF/Excel.')
    st.info('Mulai dari tombol **Gunakan Data Demo** di sidebar. Data demo tidak mengandung informasi perusahaan.')
    st.warning('Aplikasi berjalan di server gratis publik. Unggah Excel perusahaan hanya jika mendapat izin.')
    st.stop()

info,where,params,filters=filter_controls(db)
if nav=='Ringkasan':overview_page(db,where,params,info,filters)
elif nav=='Cabang':branches_page(db,where,params,filters)
elif nav=='Produk':products_page(db,where,params)
elif nav=='Kategori & Brand':categories_page(db,where,params)
elif nav=='Advanced Analytics':advanced_page(db,where,params,filters)
elif nav=='Data Explorer':explorer_page(db,where,params)
elif nav=='AI Analyst':ai_page(db,where,params,info,filters)
elif nav=='Laporan':report_page(db,where,params,filters,info)
elif nav=='Dataset':dataset_page(db,info)
elif nav=='Panduan':guide_page()
st.markdown('<div class="bai-footer">Business AI Analyst V2 · Dataset sementara per sesi · '
            'Analitik deskriptif bukan audit laporan keuangan</div>',unsafe_allow_html=True)
