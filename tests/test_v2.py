"""Regression, math, report and security tests for the V2 updater."""
from datetime import date
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from src.engine import create_database, ingest_file, finalize_database, dataset_info, filter_sql, overview
from src.advanced import (enriched_aggregate, quality_report, product_abc, previous_period,
                          branch_comparison, anomaly_days, insight_cards)
from src.assistant import answer_question
from src.reports import make_excel, make_pdf
from src.security import safe_export_text, check_access, validate_uploads

ROOT=Path(__file__).resolve().parents[1]


class V2AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=create_database()
        with (ROOT/'examples'/'demo_sales.csv').open('rb') as f:
            ingest_file(cls.db,f,'demo_sales.csv')
        finalize_database(cls.db)
        cls.info=dataset_info(cls.db)
        cls.where,cls.params=filter_sql(cls.info['min_date'],cls.info['max_date'],statuses=['Completed'])

    @classmethod
    def tearDownClass(cls):
        Path(cls.db).unlink(missing_ok=True)

    def test_enriched_and_reconciliation(self):
        result=enriched_aggregate(self.db,self.where,self.params,'store','sales',50)
        v=overview(self.db,self.where,self.params)
        self.assertAlmostEqual(sum(r['sales'] for r in result),v['sales'],places=2)
        self.assertTrue(result[0]['sales']>=result[-1]['sales'])
        self.assertTrue(all('margin' in r for r in result))

    def test_extra_filters_work_without_interpolated_user_strings(self):
        brands={r['label'] for r in enriched_aggregate(self.db,self.where,self.params,'brand',limit=100)}
        known=next(iter(brands))
        where,params=filter_sql(self.info['min_date'],self.info['max_date'],statuses=['Completed'],brands=[known])
        group=enriched_aggregate(self.db,where,params,'brand')
        self.assertEqual(len(group),1)
        self.assertEqual(group[0]['label'],known)
        hostile="'); DROP TABLE sales_rows;--"
        w,p=filter_sql(self.info['min_date'],self.info['max_date'],stores=[hostile])
        self.assertEqual(overview(self.db,w,p)['rows'],0)
        self.assertEqual(overview(self.db,self.where,self.params)['rows'],480)

    def test_abc_is_based_on_all_skus(self):
        x=product_abc(self.db,self.where,self.params,preview_limit=3)
        self.assertGreater(x['total_skus'],3)
        self.assertEqual(sum(x['classes'].values()),x['total_skus'])
        self.assertEqual(len(x['items']),3)
        self.assertAlmostEqual(x['items'][0]['sales_share'],100*x['items'][0]['sales']/x['total_positive_sales'])

    def test_quality_and_auto_insights(self):
        q=quality_report(self.db,self.where,self.params)
        self.assertEqual(q['rows'],480)
        self.assertGreaterEqual(q['missing_sku'],0)
        self.assertTrue(insight_cards(self.db,self.where,self.params))

    def test_safe_comparison_requires_two_full_windows(self):
        res=previous_period(self.db,date(2026,10,9),date(2026,10,15),statuses=['Completed'])
        self.assertTrue(res['comparable'],res['why_not'])
        self.assertIsNotNone(res['growth_pct'])
        self.assertEqual(res['span_days'],7)
        lines=branch_comparison(self.db,date(2026,10,9),date(2026,10,15),statuses=['Completed'])
        self.assertTrue(lines['rows'])
        self.assertTrue(all('selisih' in r for r in lines['rows']))
        bad=previous_period(self.db,date(2026,10,1),date(2026,10,15),statuses=['Completed'])
        self.assertFalse(bad['comparable'])
        self.assertIsNone(bad['growth_pct'])

    def test_anomaly_require_days(self):
        single_where,single_params=filter_sql('2026-10-15','2026-10-15',statuses=['Completed'])
        self.assertFalse(anomaly_days(self.db,single_where,single_params)['enough_data'])
        self.assertTrue(anomaly_days(self.db,self.where,self.params)['enough_data'])

    def test_chat_advanced_intents(self):
        abc=answer_question('Analisis ABC Pareto produk',self.db,self.where,self.params)
        self.assertIn('ABC',abc['answer'])
        qc=answer_question('Periksa kualitas data',self.db,self.where,self.params)
        self.assertIn('SKU kosong',qc['answer'])
        comparison=answer_question('growth periode ini',self.db,self.where,self.params,
            period_context={'start':date(2026,10,9),'end':date(2026,10,15),'statuses':['Completed']})
        self.assertIn('Perubahan omzet',comparison['answer'])

    def test_pdf_and_excel_reports(self):
        data=overview(self.db,self.where,self.params)
        grouped={'cabang':enriched_aggregate(self.db,self.where,self.params,'store'),
                 'produk':enriched_aggregate(self.db,self.where,self.params,'item'),
                 'kategori':enriched_aggregate(self.db,self.where,self.params,'category'),
                 'brand':enriched_aggregate(self.db,self.where,self.params,'brand'),
                 'supplier':enriched_aggregate(self.db,self.where,self.params,'supplier'),
                 'tren':[{'period':'2026-10-15','sales':1000.0}]}
        q=quality_report(self.db,self.where,self.params)
        xlsx=make_excel(data,grouped,q,self.info['imports'],'1 s.d. 15 Oktober 2026')
        pdf=make_pdf(data,grouped,q,self.info['imports'],'1 s.d. 15 Oktober 2026')
        self.assertGreater(len(xlsx),5000)
        with zipfile.ZipFile(io.BytesIO(xlsx)) as z:
            self.assertIn('xl/workbook.xml',z.namelist())
            workbook=z.read('xl/workbook.xml').decode()
            self.assertIn('Kualitas Data',workbook)
            self.assertIn('Supplier',workbook)
        self.assertGreater(len(pdf),1000)
        self.assertTrue(pdf.startswith(b'%PDF'))


class V2SecurityTests(unittest.TestCase):
    def test_csv_spreadsheet_injection(self):
        for value in ('=SUM(1,1)','+1+2','-1+2','@foo','\t=1'):
            self.assertTrue(safe_export_text(value).startswith("'"))
        self.assertEqual(safe_export_text('Produk A'),'Produk A')

    def test_login_constant_time_comparator(self):
        self.assertTrue(check_access('very-secure-password','very-secure-password'))
        self.assertFalse(check_access('bad','very-secure-password'))
        self.assertFalse(check_access('anything',''))

    def test_invalid_mandatory_numeric_rows_are_skipped(self):
        db=create_database()
        content=(b'Completed Date,Store,Item,Qty,Sales\n'
                 b'2026-10-16,Cabang C,Produk A,1,10000\n'
                 b'2026-10-16,Cabang C,Produk B,invalid,5000\n')
        try:
            result=ingest_file(db,io.BytesIO(content),'invalid-numbers.csv')
            self.assertEqual(result['rows'],1)
            self.assertEqual(result['invalid_numbers'],1)
        finally:
            Path(db).unlink(missing_ok=True)

    def test_upload_validation_limits(self):
        class F:
            def __init__(self,name,size):self.name=name;self.size=size
        self.assertTrue(validate_uploads([F('sales.xlsx',30000000)])[0])
        self.assertFalse(validate_uploads([F('evil.xlsm',100)])[0])
        self.assertFalse(validate_uploads([F('too-big.xlsx',70*1024*1024)])[0])
        self.assertFalse(validate_uploads([F('small.csv',0)])[0])

if __name__=='__main__':unittest.main()
