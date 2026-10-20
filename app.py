"""Business AI Analyst — business Excel dashboard, deployable on free Streamlit hosting.

No real business data ships with this repository. Each visitor must upload their own dataset.
"""
from __future__ import annotations

import csv
import io
import os
import re
import tempfile
import time
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.assistant import answer_question, explain_with_gemini, idr, num
from src.engine import (
    aggregate, create_database, dataset_info, distinct_values,
    filter_sql, finalize_database, ingest_file, overview, paged_data, trend,
)

def cleanup_expired_databases(max_hours: int=24):
    """Best-effort removal of forgotten temporary databases after a full day."""
    cutoff=time.time()-max_hours*3600
    for path in Path(tempfile.gettempdir()).glob('bai_session_*.sqlite3'):
        try:
            if not path.is_symlink() and path.stat().st_mtime<cutoff:
                path.unlink()
        except OSError:
            pass


st.set_page_config(page_title='Business AI Analyst',page_icon='📊',layout='wide',initial_sidebar_state='expanded')

st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"],.stApp {font-family:Roboto,Arial,sans-serif;}
[data-testid="stAppViewContainer"] {background:#f6f8fc;}
[data-testid="stSidebar"] {background:#ffffff;border-right:1px solid #e7ebf2;}
.block-container {padding-top:1.5rem;padding-bottom:3rem;max-width:1460px;}
h1,h2,h3 {color:#17253d;letter-spacing:-.025em;}
h1{font-size:2rem !important;} h3 {font-size:1.18rem !important;}
div[data-testid="stMetric"] {padding:1rem 1.12rem;border:1px solid #e7edf5;border-radius:15px;background:#fff;box-shadow:0 2px 12px #0f172a05;}
div[data-testid="stMetricLabel"] p {font-size:.86rem;color:#64748b;}
div[data-testid="stMetricValue"] {font-size:1.45rem;font-weight:800;color:#0f2946;}
[data-testid="stVerticalBlockBorderWrapper"] {background:#fff;border-color:#e6ebf3;border-radius:15px;}
.stButton>button[kind="primary"] {background:#1766e8;border-color:#1766e8;color:#fff;font-weight:600;border-radius:9px;}
.stButton>button {border-radius:9px;font-weight:500;}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] {gap:4px;}
.note {font-size:.87rem;color:#6b7280;}
.pill {display:inline-block;background:#eaf2ff;color:#245db6;font-size:.76rem;padding:5px 10px;border-radius:30px;font-weight:600;}
.brand {display:flex;gap:11px;align-items:center;margin-bottom:16px;}
.brand-icon {font-size:1.35rem;background:#eff6ff;color:#2054a5;border-radius:12px;padding:8px;}
.brand-name {font-size:1.12rem;font-weight:800;color:#15233c;line-height:1.3;}
.brand-desc {font-size:.72rem;color:#64748b;}
[data-testid="stFileUploader"] section {border-radius:12px;border:1.5px dashed #b6c7e4;background:#f8fbff;}
@media(max-width:768px){.block-container{padding:1rem .7rem 2.5rem} h1{font-size:1.48rem !important;}div[data-testid="stMetricValue"] {font-size:1.1rem;}}
</style>''', unsafe_allow_html=True)

COLORS=['#1766e8','#16a6a6','#f5a524','#874bee','#ef6480','#4b78c5','#6c9f36','#64748b']


def plot_style(fig, height=355):
    fig.update_layout(height=height,margin=dict(t=22,l=5,r=8,b=10),
        font=dict(family='Roboto,Arial,sans-serif',size=12,color='#46546a'),
        plot_bgcolor='white',paper_bgcolor='white',
        legend=dict(orientation='h',y=-.23),
        hoverlabel=dict(bgcolor='white',font_size=12))
    fig.update_xaxes(showgrid=False,zeroline=False)
    fig.update_yaxes(gridcolor='#eff2f8',zeroline=False)
    return fig


def compact_rupiah(amount):
    a=float(amount or 0)
    if abs(a)>=1e12: return f'Rp{a/1e12:,.2f} T'.replace(',','~').replace('.',',').replace('~','.')
    if abs(a)>=1e9: return f'Rp{a/1e9:,.2f} M'.replace(',','~').replace('.',',').replace('~','.')
    if abs(a)>=1e6: return f'Rp{a/1e6:,.2f} jt'.replace(',','~').replace('.',',').replace('~','.')
    return idr(a)


def export_csv(df: pd.DataFrame) -> bytes:
    """Excel-compatible CSV, protecting against spreadsheet formula injection."""
    safe=df.copy()
    for col in safe.select_dtypes(include=['object','string']).columns:
        safe[col]=safe[col].map(lambda v: ("'"+v) if isinstance(v,str) and
            re.match(r'^\s*[=+\-@]',v) else v)
    return ('\ufeff'+safe.to_csv(index=False)).encode('utf-8')


def show_bar(rows, dimension, metric_name, horizontal=True, height=420):
    if not rows:
        st.info('Belum ada data untuk ditampilkan.');return
    frame=pd.DataFrame(rows)
    if horizontal:
        frame=frame.iloc[::-1]
        fig=px.bar(frame,x='value',y='label',orientation='h',color_discrete_sequence=[COLORS[0]],
            labels={'value':metric_name,'label':dimension})
        fig.update_traces(marker_line_width=0,hovertemplate='%{y}<br>%{x:,.0f}<extra></extra>')
        fig.update_yaxes(categoryorder='array',categoryarray=frame['label'].tolist(),tickfont=dict(size=10))
    else:
        fig=px.bar(frame,x='label',y='value',color_discrete_sequence=[COLORS[0]],
                   labels={'value':metric_name,'label':dimension})
        fig.update_xaxes(tickangle=-35)
    st.plotly_chart(plot_style(fig,height),use_container_width=True)


def reveal_data(db_path: str):
    info=dataset_info(db_path)
    st.sidebar.markdown('#### Filter Analisis')
    start_default=date.fromisoformat(info['min_date'])
    end_default=date.fromisoformat(info['max_date'])
    a=st.sidebar.date_input('Dari tanggal',start_default,min_value=start_default,max_value=end_default)
    b=st.sidebar.date_input('Sampai tanggal',end_default,min_value=start_default,max_value=end_default)
    stores=st.sidebar.multiselect('Cabang',distinct_values(db_path,'store'),placeholder='Semua cabang')
    categories=st.sidebar.multiselect('Kategori',distinct_values(db_path,'category'),placeholder='Semua kategori')
    statuses=distinct_values(db_path,'status')
    default=['Completed'] if 'Completed' in statuses else statuses
    chosen=st.sidebar.multiselect('Status penjualan',statuses,default=default)
    if a>b:
        st.warning('Tanggal awal tidak boleh melewati tanggal akhir.'); st.stop()
    if statuses and not chosen:
        st.warning('Pilih minimal satu status transaksi.'); st.stop()
    where,params=filter_sql(a.isoformat(),b.isoformat(),stores,categories,chosen)
    return info,where,params


def put_file(file_obj,name,pg):
    return ingest_file(pg,file_obj,name)


def process_inputs(files):
    if not files:
        st.warning('Pilih minimal satu file terlebih dahulu.');return
    total_size=sum(f.size for f in files)
    if total_size>90*1024*1024:
        st.error('Total file melebihi batas aman 90 MB untuk demo hosting gratis. Proses per bagian atau gunakan komputer sendiri.');return
    new_path=create_database()
    progress=st.progress(0,text='Menyiapkan database sesi...')
    stats=[]
    try:
        for i,f in enumerate(files):
            progress.progress(int(i/len(files)*100),text=f'Membaca {f.name}...')
            stats.append(ingest_file(new_path,f,f.name,
                progress=lambda x,i=i:progress.progress(min(99,int((i+x/100)/len(files)*100)),
                                                      text=f'Memproses {f.name}...')))
        progress.progress(98,text='Membuat indeks untuk mempercepat dashboard...')
        finalize_database(new_path)
        previous=st.session_state.get('db_path')
        st.session_state['db_path']=new_path
        st.session_state['messages']=[]
        st.session_state['import_stats']=stats
        st.session_state['upload_version']=st.session_state.get('upload_version',0)+1
        if previous:
            try: Path(previous).unlink(missing_ok=True)
            except OSError: pass
        progress.progress(100,text='Selesai. Dashboard siap digunakan.')
        st.rerun()
    except Exception as exc:
        try: Path(new_path).unlink(missing_ok=True)
        except OSError: pass
        st.error(f'Gagal membaca data: {exc}')


def reset_data():
    previous=st.session_state.pop('db_path',None)
    if previous:
        try: Path(previous).unlink(missing_ok=True)
        except OSError: pass
    st.session_state['messages']=[]
    st.session_state['upload_version']=st.session_state.get('upload_version',0)+1
    st.rerun()


def title_bar(title,subtitle=''):
    st.title(title)
    if subtitle: st.caption(subtitle)


def page_overview(db,where,params,info):
    title_bar('Ringkasan Bisnis','Pantau performa berdasarkan file yang diunggah dan filter aktif.')
    v=overview(db,where,params)
    a,b,c,d=st.columns(4)
    with a: st.metric('Omzet Sebelum Pajak',compact_rupiah(v['sales']))
    with b: st.metric('Laba Kotor',compact_rupiah(v['gross_profit']))
    with c: st.metric('Margin Kotor',f"{v['margin']:.2f}%")
    with d: st.metric('Transaksi Unik',num(v['transactions']))
    e,f,g,h=st.columns(4)
    with e: st.metric('Unit Terjual',num(v['qty']))
    with f: st.metric('Cabang Aktif',num(v['branches']))
    with g: st.metric('SKU Aktif',num(v['products']))
    with h: st.metric('Omzet Termasuk Pajak',compact_rupiah(v['sales_inc_tax']))
    if v['rows']==0: st.warning('Data tidak ditemukan dalam filter saat ini.');return
    if v['days']==1:
        st.info('Data terfilter hanya mencakup satu tanggal. Grafik di bawah menampilkan omzet **per jam**; growth harian/bulanan belum dapat dihitung.')
    c1,c2=st.columns([1.75,1],gap='medium')
    with c1:
        with st.container(border=True):
            st.subheader('Tren Omzet')
            is_hour=v['days']==1
            series=trend(db,where,params,hour=is_hour)
            df=pd.DataFrame(series)
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=df['period'],y=df['sales'],mode='lines+markers',
                line=dict(color=COLORS[0],width=3),marker=dict(size=6),
                fill='tozeroy',fillcolor='rgba(23,102,232,.075)',name='Omzet'))
            fig.update_layout(yaxis_title='Omzet (Rp)',xaxis_title='Jam' if is_hour else 'Tanggal',showlegend=False)
            st.plotly_chart(plot_style(fig,350),use_container_width=True)
    with c2:
        with st.container(border=True):
            st.subheader('Kategori Teratas')
            cats=aggregate(db,where,params,'category',limit=7)
            df=pd.DataFrame(cats)
            pie=px.pie(df,names='label',values='value',hole=.62,
                color_discrete_sequence=COLORS)
            pie.update_traces(textinfo='percent',textposition='inside',hovertemplate='%{label}<br>Rp%{value:,.0f}<extra></extra>')
            st.plotly_chart(plot_style(pie,350),use_container_width=True)
    c1,c2=st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader('Top 10 Cabang')
            show_bar(aggregate(db,where,params,'store',limit=10),'Cabang','Omzet (Rp)',height=430)
    with c2:
        with st.container(border=True):
            st.subheader('Top 10 Produk')
            show_bar(aggregate(db,where,params,'item',limit=10),'Produk','Omzet (Rp)',height=430)
    with st.container(border=True):
        st.subheader('Insight Otomatis')
        best=aggregate(db,where,params,'store',limit=1)
        topcat=aggregate(db,where,params,'category',limit=1)
        hour=trend(db,where,params,hour=True) if v['days']==1 else []
        peak=max(hour,key=lambda x:x['sales']) if hour else None
        lines=[]
        if best: lines.append(f"**Cabang beromzet tertinggi:** {best[0]['label']} ({idr(best[0]['value'])}).")
        if topcat: lines.append(f"**Kategori terbesar:** {topcat[0]['label']} ({idr(topcat[0]['value'])}).")
        if peak: lines.append(f"**Jam penjualan terpadat berdasarkan omzet:** {peak['period']} ({idr(peak['sales'])}).")
        lines.append(f"**Margin laba kotor:** {v['margin']:.2f}% dari omzet sebelum pajak. Ini bukan margin laba bersih.")
        for ln in lines: st.markdown('- '+ln)
        st.caption('Temuan bersifat deskriptif, bukan bukti penyebab perubahan bisnis.')
    with st.expander('Informasi Dataset & Transparansi Perhitungan'):
        st.write(f"Periode: {info['min_date']} sampai {info['max_date']}; total {num(info['rows'])} baris sumber. Filter aktif: {num(v['rows'])} baris.")
        st.write('Omzet = SUM(Sales), belum termasuk pajak. Omzet termasuk pajak = SUM(Sales (Inc Tax)). Laba kotor = SUM(Gross Profit). Transaksi unik = pasangan Store Code + Sales Ref Code.')
        st.write('File sumber tidak disertakan dalam repository dan kolom pelanggan tidak disimpan.')


def page_branches(db,where,params):
    title_bar('Analisis Cabang','Bandingkan kontribusi omzet, laba kotor, unit, dan transaksi.')
    labels={'sales':'Omzet (Rp)','gross_profit':'Laba kotor (Rp)','qty':'Unit terjual','transactions':'Transaksi'}
    metric=st.selectbox('Urut berdasarkan',list(labels),format_func=lambda x:labels[x])
    rows=aggregate(db,where,params,'store',metric,limit=500)
    if not rows: st.info('Data tidak tersedia.');return
    df=pd.DataFrame(rows).rename(columns={'label':'Cabang','value':labels[metric],'lines':'Baris Detail'})
    a,b,c=st.columns(3)
    a.metric('Cabang pada Filter',num(len(df)))
    b.metric('Top 1',df.iloc[0]['Cabang'])
    c.metric('Nilai Tertinggi',compact_rupiah(df.iloc[0][labels[metric]]) if metric in {'sales','gross_profit'} else num(df.iloc[0][labels[metric]]))
    with st.container(border=True):
        st.subheader('Peringkat 15 Cabang Teratas')
        show_bar(rows[:15],'Cabang',labels[metric],height=550)
    st.subheader('Tabel Semua Cabang')
    st.dataframe(df,use_container_width=True,hide_index=True)
    st.download_button('Unduh CSV Cabang',export_csv(df),'analisis_cabang.csv','text/csv')


def page_products(db,where,params):
    title_bar('Analisis Produk','Temukan produk dengan kontribusi penjualan tertinggi.')
    metric=st.selectbox('Urut berdasarkan',['sales','qty','gross_profit'],format_func=lambda x:{'sales':'Omzet','qty':'Qty terjual','gross_profit':'Laba kotor'}[x])
    rows=aggregate(db,where,params,'item',metric,limit=100)
    if not rows: st.info('Data tidak tersedia.');return
    df=pd.DataFrame(rows).rename(columns={'label':'Produk','value':metric,'lines':'Baris Detail'})
    with st.container(border=True):
        st.subheader('Top 15 Produk')
        show_bar(rows[:15],'Produk',metric,height=580)
    st.subheader('Peringkat Produk')
    st.dataframe(df,use_container_width=True,hide_index=True)
    st.download_button('Unduh CSV Produk',export_csv(df),'analisis_produk.csv','text/csv')


def page_categories(db,where,params):
    title_bar('Kategori & Brand','Lihat kontribusi jenis barang, merek, dan supplier.')
    tab1,tab2,tab3=st.tabs(['Kategori','Brand','Supplier'])
    for tab,dim,title in [(tab1,'category','Kategori Produk'),(tab2,'brand','Merek Produk'),(tab3,'supplier','Supplier')]:
        with tab:
            metric=st.selectbox('Metrik', ['sales','qty','gross_profit'],
                format_func=lambda x:{'sales':'Omzet','qty':'Jumlah terjual','gross_profit':'Laba kotor'}[x],key='metric_'+dim)
            rows=aggregate(db,where,params,dim,metric,limit=100)
            if not rows: st.info('Tidak ada data.');continue
            show_bar(rows[:15],title,metric,height=480)
            df=pd.DataFrame(rows).rename(columns={'label':title,'value':metric,'lines':'Baris Detail'})
            st.dataframe(df,use_container_width=True,hide_index=True)
            st.download_button('Unduh CSV '+title,export_csv(df),f'{dim}.csv','text/csv',key='csv_'+dim)


def page_explorer(db,where,params):
    title_bar('Data Explorer','Preview baris penjualan yang telah dibersihkan dari kolom identitas pelanggan.')
    st.caption('Tabel dibuat dengan pagination sehingga Excel besar tidak dibuka seluruhnya ke memori browser.')
    col1,col2=st.columns([1,3])
    with col1: size=st.selectbox('Baris per halaman',[25,50,100],index=1)
    with col2: page=st.number_input('Halaman',min_value=1,step=1,value=1)
    total,rows=paged_data(db,where,params,page,size)
    max_page=max(1,(total+size-1)//size)
    if page>max_page:
        st.warning(f'Halaman yang tersedia hanya 1 hingga {num(max_page)}.');return
    st.caption(f'{num(total)} baris • halaman {num(page)} dari {num(max_page)}')
    df=pd.DataFrame(rows)
    st.dataframe(df,use_container_width=True,hide_index=True,height=565)
    if not df.empty:
        st.download_button('Unduh CSV Halaman Ini',export_csv(df),'preview_penjualan.csv','text/csv')
    st.warning('Demi keamanan, fitur unduh mengekspor halaman preview saja, bukan seluruh data transaksi yang mungkin sensitif.')


def get_api_key():
    try:
        return st.secrets.get('GEMINI_API_KEY','') or os.environ.get('GEMINI_API_KEY','')
    except Exception:
        return os.environ.get('GEMINI_API_KEY','')


def page_ai(db,where,params,info):
    title_bar('AI Analyst','Tanyakan soal omzet, laba, produk, kategori, cabang, hingga penjualan per jam.')
    key=get_api_key()
    colA,colB=st.columns([2,1])
    with colA:
        st.caption('Semua jawaban numerik dihitung dari database SQLite, bukan ditebak oleh model bahasa.')
    with colB:
        use_llm=st.checkbox('Interpretasi Gemini (opsional)',value=False,disabled=not bool(key),
            help='Jika aktif, ringkasan agregat dan pertanyaan dikirim ke Gemini. File Excel dan identitas pelanggan tidak dikirim.')
    if not key:
        st.info('Mode analitik lokal aktif dan gratis tanpa API. AI generatif opsional dapat diaktifkan pengelola melalui GEMINI_API_KEY pada Streamlit Secrets.')
    else:
        st.caption('Mode generatif hanya berjalan bila kamu mencentang kotak persetujuan di atas.')
    suggestions=['Ringkaskan performa penjualan','Top 10 cabang berdasarkan omzet',
                 'Top 10 produk berdasarkan qty','Kategori dengan laba kotor tertinggi',
                 'Jam berapa omzet tertinggi?','Berapa margin laba kotor?']
    st.markdown('**Pertanyaan cepat**')
    cols=st.columns(3)
    clicked=None
    for idx,text in enumerate(suggestions):
        with cols[idx%3]:
            if st.button(text,use_container_width=True,key=f'q_{idx}'):
                clicked=text
    if 'messages' not in st.session_state: st.session_state['messages']=[]
    for i,message in enumerate(st.session_state['messages']):
        with st.chat_message(message['role']):
            st.markdown(message['content'])
            if message['role']=='assistant' and message.get('table'):
                st.dataframe(pd.DataFrame(message['table']),use_container_width=True,hide_index=True)
    prompt=clicked or st.chat_input('Contoh: Berapa laba kotor 10 cabang tertinggi?')
    if prompt:
        st.session_state['messages'].append({'role':'user','content':prompt})
        with st.chat_message('user'): st.markdown(prompt)
        with st.chat_message('assistant'):
            with st.spinner('Menghitung data...'):
                result=answer_question(prompt,db,where,params)
                explanation=result['answer']
                if use_llm:
                    try:
                        generated=explain_with_gemini(prompt,result,key)
                        explanation+=f'\n\n---\n**Penjelasan AI generatif (opsional)**\n\n{generated}'
                    except Exception as exc:
                        explanation+=f'\n\n*Interpretasi generatif tidak tersedia: {exc}*'
            st.markdown(explanation)
            st.caption('Sumber: dataset yang diunggah • filter aktif • hasil perhitungan SQL')
            if result.get('table'): st.dataframe(pd.DataFrame(result['table']),use_container_width=True,hide_index=True)
        st.session_state['messages'].append({'role':'assistant','content':explanation,'table':result.get('table',[])})
    if st.session_state['messages'] and st.button('Hapus riwayat chat'):
        st.session_state['messages']=[]
        st.rerun()


def page_guide():
    title_bar('Panduan Penggunaan','Cara membaca dan menganalisis file Detailed Sales dengan aman.')
    st.markdown('''
    1. Klik **Upload Excel** di sidebar lalu pilih file `.xlsx` atau `.csv`.
    2. Klik **Proses Data**. Proses mungkin memerlukan waktu, terutama untuk file besar.
    3. Gunakan menu **Ringkasan**, **Cabang**, **Produk**, dan **Kategori & Brand**.
    4. Gunakan filter periode, cabang, kategori dan status transaksi di sidebar.
    5. Buka **AI Analyst** untuk bertanya dengan bahasa Indonesia.
    6. Ekspor hasil peringkat ke CSV yang bisa dibuka di Excel.
    ''')
    st.markdown('''**Definisi angka**
    - Omzet = kolom **Sales** (sebelum pajak).
    - Omzet termasuk pajak = **Sales (Inc Tax)**.
    - Laba kotor = **Gross Profit** yang tercatat; bukan laba bersih.
    - Transaksi unik dihitung dari kombinasi **Store Code + Sales Ref Code**.
    - Jika hanya satu tanggal, tidak akan muncul klaim pertumbuhan antarhari.

    **Privasi**
    - Kolom Customer, Customer ID, KTP, NPWP, Phone, Address dan Membership tidak diimpor.
    - Data tersimpan sementara di server selama digunakan, **bukan** jaminan penyimpanan lokal perangkat.
    - Uploadlah hanya data yang diizinkan perusahaan. Jangan gunakan server publik gratis untuk data rahasia tanpa persetujuan.
    - Klik **Hapus Data Sesi** ketika selesai. Sesi dapat terhapus sendiri saat server restart.
    ''')
    st.info('Jika ingin database permanen, login per pengguna, histori upload, dan sinkronisasi real-time, dibutuhkan pengembangan backend dan storage berikutnya.')


with st.sidebar:
    st.markdown('''<div class="brand"><span class="brand-icon">◈</span>
        <div><div class="brand-name">Business AI Analyst</div>
        <div class="brand-desc">Excel to Insights • Free MVP</div></div></div>''',unsafe_allow_html=True)
    st.caption('WORKSPACE')
    NAV=['Ringkasan','Cabang','Produk','Kategori & Brand','Data Explorer','AI Analyst','Panduan']
    nav=st.radio('Navigasi',NAV,label_visibility='collapsed')
    st.divider()
    st.markdown('#### Upload Excel')
    uploaded=st.file_uploader('Pilih file penjualan',type=['xlsx','csv'],accept_multiple_files=True,
        help='File diproses sementara di server; jangan unggah jika belum ada izin. Maksimum gabungan 90 MB.',
        key=f"files_{st.session_state.get('upload_version',0)}")
    if st.button('Proses Data',type='primary',use_container_width=True):
        process_inputs(uploaded)
    if st.session_state.get('db_path'):
        st.caption('Dataset aktif dalam sesi ini')
        if st.button('Hapus Data Sesi',use_container_width=True): reset_data()
    st.divider()
    st.caption('Tanpa biaya hosting dengan Streamlit Community Cloud. Tidak ada database publik permanen.')

db=st.session_state.get('db_path')
if 'cleanup_ran' not in st.session_state:
    cleanup_expired_databases()
    st.session_state['cleanup_ran']=True
if db and Path(db).exists():
    try: os.utime(db,None)
    except OSError: pass
if db and not Path(db).exists():
    st.session_state.pop('db_path',None)
    db=None

if not db:
    title_bar('AI Data Analyst untuk Penjualan','Upload data Detailed Sales, lalu lihat analisis bisnis secara otomatis.')
    st.markdown('<span class="pill">Tidak butuh API berbayar untuk analisis dasar</span>',unsafe_allow_html=True)
    st.write('Aplikasi membaca data Excel besar secara bertahap, menghitung metrik penjualan menggunakan SQL, dan menghapus kolom identitas pelanggan dari database analitik.')
    a,b,c=st.columns(3)
    with a:
        with st.container(border=True):
            st.subheader('📤 Smart Import')
            st.write('Baca Excel/CSV, multi-file, auto-detect header Detailed Sales dan agregasi transaksi.')
    with b:
        with st.container(border=True):
            st.subheader('📊 Business Analytics')
            st.write('Omzet, profit, transaksi, margin, jam ramai, cabang, produk, kategori, brand.')
    with c:
        with st.container(border=True):
            st.subheader('💬 Ask Analyst')
            st.write('Tanya metrik bisnis dengan bahasa Indonesia tanpa harus menulis rumus Excel.')
    st.subheader('Mulai dengan data contoh')
    st.caption('Data demo sepenuhnya sintetis; gunakan untuk mencoba aplikasi sebelum mengunggah laporan perusahaan.')
    if st.button('Gunakan Data Demo',type='primary'):
        with open(Path(__file__).parent/'examples'/'demo_sales.csv','rb') as f:
            wrapper=io.BytesIO(f.read())
            wrapper.name='demo_sales.csv'
            # process_inputs is intentionally called with an object having name/size.
            wrapper.size=wrapper.getbuffer().nbytes
            process_inputs([wrapper])
    st.warning('Untuk publikasi, upload hanya source code yang ada di ZIP. Jangan unggah spreadsheet asli milik perusahaan ke GitHub publik.')
    st.stop()

info,where,params=reveal_data(db)
if nav=='Ringkasan': page_overview(db,where,params,info)
elif nav=='Cabang':page_branches(db,where,params)
elif nav=='Produk':page_products(db,where,params)
elif nav=='Kategori & Brand':page_categories(db,where,params)
elif nav=='Data Explorer':page_explorer(db,where,params)
elif nav=='AI Analyst':page_ai(db,where,params,info)
elif nav=='Panduan':page_guide()

st.divider()
st.caption('Business AI Analyst • Streamlit Community Cloud Edition 1.1 • Hasil analisis mengikuti data dan filter; bukan laporan audit keuangan.')
