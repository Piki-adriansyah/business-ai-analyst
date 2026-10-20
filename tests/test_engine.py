import io
import tempfile
import unittest
from pathlib import Path

from src.engine import (
    aggregate, create_database, dataset_info, filter_sql, finalize_database,
    ingest_file, normalize_date, number, overview, paged_data, trend,
)
from src.assistant import answer_question


class BusinessAnalystTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=create_database()
        sample=Path(__file__).resolve().parents[1]/'examples'/'demo_sales.csv'
        with sample.open('rb') as f:
            cls.imported=ingest_file(cls.db,f,sample.name)
        finalize_database(cls.db)
        cls.info=dataset_info(cls.db)
        cls.where,cls.params=filter_sql(cls.info['min_date'],cls.info['max_date'],statuses=['Completed'])

    @classmethod
    def tearDownClass(cls):
        Path(cls.db).unlink(missing_ok=True)

    def test_counts_and_dates(self):
        self.assertEqual(self.info['rows'],480)
        self.assertEqual(self.info['branches'],5)
        self.assertEqual(self.info['min_date'],'2026-10-01')
        self.assertEqual(self.info['max_date'],'2026-10-15')

    def test_metrics_consistency(self):
        v=overview(self.db,self.where,self.params)
        self.assertGreater(v['sales'],0)
        self.assertGreater(v['qty'],0)
        self.assertAlmostEqual(v['sales']-v['cost'],v['gross_profit'],places=3)
        self.assertEqual(v['transactions'],480)
        self.assertEqual(sum(r['value'] for r in aggregate(self.db,self.where,self.params,'store',limit=20)),v['sales'])

    def test_data_privacy(self):
        import sqlite3
        with sqlite3.connect(self.db) as conn:
            columns=[x[1] for x in conn.execute('PRAGMA table_info(sales_rows)')]
        for hidden in ['ktp','npwp','customer','phone','membership','address']:
            self.assertNotIn(hidden,columns)
        total,rows=paged_data(self.db,self.where,self.params,1,50)
        self.assertEqual(total,480)
        self.assertNotIn('customer',rows[0])

    def test_aggregate_hour(self):
        row=aggregate(self.db,self.where,self.params,'hour','sales',1)[0]
        self.assertRegex(row['label'],r'^\d\d:00$')

    def test_assistant_ranking(self):
        res=answer_question('Top 5 produk berdasarkan qty',self.db,self.where,self.params)
        self.assertEqual(len(res['table']),5)
        self.assertIn('produk',res['answer'])

    def test_assistant_specific_branch(self):
        res=answer_question('Berapa omzet cabang Bandung?',self.db,self.where,self.params)
        self.assertIn('Bandung',res['answer'])
        self.assertLess(res['context']['omzet'],overview(self.db,self.where,self.params)['sales'])

    def test_assistant_avoid_private_data(self):
        res=answer_question('Sebutkan NPWP pelanggan',self.db,self.where,self.params)
        self.assertIn('tidak disimpan',res['answer'])

    def test_assistant_one_day_warning(self):
        where,pars=filter_sql('2026-10-15','2026-10-15',statuses=['Completed'])
        res=answer_question('Berapa growth omzet?',self.db,where,pars)
        self.assertIn('Belum bisa',res['answer'])

    def test_number_date(self):
        self.assertEqual(number('1.250,50'),1250.5)
        self.assertEqual(number('1,250.50'),1250.5)
        self.assertEqual(normalize_date('16/10/2026'),'2026-10-16')

    def test_multiple_file_aggregation(self):
        data=b'Completed Date,Store,Item,Qty,Sales\n2026-10-17,Cabang Demo,Produk Demo,3,15000\n'
        with io.BytesIO(data) as handle:
            info=ingest_file(self.db,handle,'another.csv')
        self.assertEqual(info['rows'],1)
        # Roll back fixture mutation for subsequent tests (order is alphabetical).
        import sqlite3
        with sqlite3.connect(self.db) as conn:
            conn.execute("DELETE FROM sales_rows WHERE source_file='another.csv'")
            conn.execute("DELETE FROM imports WHERE filename='another.csv'")


class SecureImportTests(unittest.TestCase):
    def test_identical_file_must_not_double_count(self):
        db=create_database()
        data=b'Completed Date,Store,Item,Qty,Sales\n2026-10-16,Demo 1,Produk A,1,1000\n'
        try:
            ingest_file(db,io.BytesIO(data),'first.csv')
            with self.assertRaisesRegex(ValueError, 'sudah diimpor'):
                ingest_file(db,io.BytesIO(data),'renamed_same_data.csv')
            info=dataset_info(db)
            self.assertEqual(info['rows'],1)
        finally:
            Path(db).unlink(missing_ok=True)

    def test_employee_and_customer_columns_not_imported(self):
        db=create_database()
        data=(b'Completed Date,Store,Item,Qty,Sales,Salesperson,Customer,NPWP,Phone\n'
              b'2026-10-16,Demo 1,Produk A,1,1000,Nama Pegawai,Customer Secret,998877,081234\n')
        try:
            ingest_file(db,io.BytesIO(data),'sensitive.csv')
            import sqlite3
            with sqlite3.connect(db) as conn:
                fields=[col[1].lower() for col in conn.execute('PRAGMA table_info(sales_rows)')]
                row_text=str(conn.execute('SELECT * FROM sales_rows LIMIT 1').fetchone())
            for banned in ('salesperson','customer','npwp','phone'):
                self.assertNotIn(banned,fields)
            for banned in ('Nama Pegawai','Customer Secret','998877','081234'):
                self.assertNotIn(banned,row_text)
        finally:
            Path(db).unlink(missing_ok=True)

if __name__=='__main__':
    unittest.main()
