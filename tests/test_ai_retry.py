import unittest
from unittest.mock import patch
import httpx
from backend.ai import request_plan, AIError

class RetryTests(unittest.TestCase):
    def call(self, statuses):
        good={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"title":"Уточнение","clarification":"Какой период?","charts":[]}'}]}}]}
        with patch('backend.ai.configuration',return_value={'ai':{'provider':'gemini','external_data_policy':'question_and_schema','api_key_env':'AI_API_KEY','base_url':'https://generativelanguage.googleapis.com/v1beta','model':'gemini-2.5-flash'}}), patch('backend.ai.secrets',return_value={'AI_API_KEY':'test'}), patch('backend.ai.httpx.Client') as factory, patch('backend.ai.time.sleep') as sleep:
            client=factory.return_value.__enter__.return_value
            client.post.side_effect=[httpx.Response(s,json=good if s==200 else {}) for s in statuses]
            try:
                result=request_plan('Покажи отчёт',{'datasets':[]})
            except AIError as exc:
                result=exc
            return result,client.post.call_count,sleep.call_count
    def test_recovers_from_503(self):
        result,calls,sleeps=self.call([503,200])
        self.assertEqual(result.clarification,'Какой период?')
        self.assertEqual((calls,sleeps),(2,1))
    def test_stops_after_three(self):
        result,calls,sleeps=self.call([503,503,503])
        self.assertEqual(result.status,503)
        self.assertEqual((calls,sleeps),(3,2))
    def test_does_not_retry_key_or_quota_errors(self):
        for status in [400,403,429]:
            with self.subTest(status=status):
                result,calls,sleeps=self.call([status])
                self.assertIsInstance(result,AIError)
                self.assertEqual((calls,sleeps),(1,0))
