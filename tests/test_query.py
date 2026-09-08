import unittest
import re
from unittest.mock import patch
from pydantic import ValidationError
from backend.models import ChartPlan
from backend.query import compile_chart
from backend.ai import request_plan, AIError
from fastapi.testclient import TestClient
from backend.main import app

CATALOG={'datasets':[{'name':'dbo.DemoSales','fields':[
    {'name':'SaleDate','type':'datetime'}, {'name':'Amount','type':'float'},
    {'name':'Customer','type':'varchar'}, {'name':'weird]column','type':'varchar'}]}]}


def plan(**changes):
    base={'title':'Продажи','dataset':'dbo.DemoSales','chart_type':'bar',
          'dimensions':[{'field':'SaleDate','grain':'month'}],
          'measures':[{'field':'Amount','aggregate':'sum','label':'Сумма'}],
          'sort_by':'d0','sort_direction':'asc'}
    base.update(changes)
    return ChartPlan.model_validate(base)


class QueryTests(unittest.TestCase):
    def setUp(self):
        mock = patch('backend.query.configuration', return_value={'database': {
            'allowed_views': ['dbo.DemoSales'], 'max_result_rows': 1000}})
        mock.start()
        self.addCleanup(mock.stop)

    def test_month_includes_year(self):
        sql,params,_,_=compile_chart(plan(),CATALOG)
        self.assertIn('CONVERT(char(7), [SaleDate], 126)',sql)
        self.assertIn('GROUP BY',sql)
        self.assertEqual(params,[])

    def test_filter_value_cannot_be_sql(self):
        value="'; DROP TABLE invoices; --"
        sql,params,_,_=compile_chart(plan(filters=[{'field':'Customer','operator':'eq','value':value}]),CATALOG)
        self.assertNotIn('DROP',sql)
        self.assertEqual(params,[value])

    def test_unknown_dataset_rejected(self):
        with self.assertRaises(ValueError):compile_chart(plan(dataset='dbo.sysobjects'),CATALOG)

    def test_unknown_column_rejected(self):
        with self.assertRaises(ValueError):compile_chart(plan(dimensions=[{'field':'x]; DELETE x;--'}]),CATALOG)

    def test_empty_allowlist_denies_everything(self):
        with patch('backend.query.configuration',return_value={'database':{'allowed_views':[]}}):
            with self.assertRaises(ValueError):compile_chart(plan(),CATALOG)

    def test_unknown_sql_property_rejected(self):
        with self.assertRaises(ValidationError):plan(sql='DELETE FROM anything')

    def test_sum_text_rejected(self):
        with self.assertRaises(ValueError):compile_chart(plan(measures=[{'field':'Customer','aggregate':'sum','label':'x'}]),CATALOG)

    def test_identifier_bracket_escaped(self):
        sql,*_=compile_chart(plan(dimensions=[{'field':'weird]column'}]),CATALOG)
        self.assertIn('[weird]]column]',sql)

    def test_like_wildcards_literal(self):
        sql,params,*_=compile_chart(plan(filters=[{'field':'Customer','operator':'contains','value':'a%_['}]),CATALOG)
        self.assertIn("ESCAPE '~'",sql)
        self.assertEqual(params,['%a~%~_~[%'])

    def test_sort_injection_rejected(self):
        with self.assertRaises(ValueError):compile_chart(plan(sort_by='m0; DELETE x'),CATALOG)

    def test_limit_hard_cap(self):
        with self.assertRaises(ValidationError):plan(limit=1000000)

    def test_count_rows_supported(self):
        sql,*_=compile_chart(plan(measures=[{'field':'*','aggregate':'count','label':'Строки'}]),CATALOG)
        self.assertIn('COUNT_BIG(*)',sql)


class ApiTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(app)

    def test_write_requires_local_token(self):
        self.assertEqual(self.client.post('/api/ask',json={'question':'test'}).status_code,403)

    def test_external_host_denied(self):
        self.assertEqual(self.client.get('/api/status',headers={'host':'attacker.test'}).status_code,400)

    def test_cross_origin_denied(self):
        token=self.client.get('/api/status').json()['token']
        result=self.client.post('/api/ask',headers={'x-local-token':token,'origin':'https://attacker.test'},json={'question':'test'})
        self.assertEqual(result.status_code,403)

    def test_status_has_no_secrets(self):
        data=self.client.get('/api/status').json()
        self.assertNotIn('password',data)
        self.assertNotIn('api_key',data)

    def test_built_module_has_javascript_mime(self):
        page = self.client.get('/')
        if page.status_code == 503:
            self.skipTest('Build frontend before checking static assets')
        self.assertEqual(page.status_code, 200)
        script = re.search(r'<script[^>]+src="([^"]+)"', page.text)
        self.assertIsNotNone(script)
        result = self.client.get(script.group(1))
        self.assertEqual(result.status_code, 200)
        self.assertIn(result.headers['content-type'].split(';')[0],
                      {'text/javascript', 'application/javascript'})

    def test_missing_key_never_calls_provider(self):
        with patch('backend.ai.secrets',return_value={}),patch('backend.ai.httpx.Client') as client:
            with self.assertRaises(AIError):request_plan('test',CATALOG)
            client.assert_not_called()


if __name__=='__main__':unittest.main()
