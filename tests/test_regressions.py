"""Regression cases found during the pre-publication review; no live model/API calls."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from thaimooc import api
from thaimooc.data import ROOT, load_jsonl
from thaimooc.generation import recommend
from thaimooc.search import SearchEngine

spec = importlib.util.spec_from_file_location('pooled_scoring', ROOT/'scripts/score_pooled_judgments.py')
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)


class InputRegressionTests(unittest.TestCase):
    def setUp(self):
        self.course = load_jsonl(ROOT/'data/seed/courses.jsonl')[0]

    def test_invalid_field_types_rejected_before_indexing(self):
        for field, value in [('learning_outcomes', None), ('category', []), ('level', 7),
                             ('institution', {}), ('provenance', None), ('url', None)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(self.course, **{field: value})

    def test_noncanonical_urls_rejected(self):
        for url in [self.course.url+'?tracking=x', self.course.url+'#fragment',
                    self.course.url.replace('https://','https://user:pass@'),
                    self.course.url.replace('thaimooc.ac.th','thaimooc.ac.th:9000')]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                replace(self.course, url=url)

    def test_connection_reset_uses_retrieval_fallback(self):
        hits = SearchEngine([self.course]).search(self.course.title)
        with patch('thaimooc.generation.urlopen', side_effect=ConnectionResetError()):
            self.assertEqual(recommend('เรียน', hits)['mode'], 'retrieval_fallback')

    def test_malformed_ollama_configuration_uses_fallback(self):
        hits = SearchEngine([self.course]).search(self.course.title)
        with patch.dict('os.environ', {'OLLAMA_BASE_URL': 'http://[broken'}):
            self.assertEqual(recommend('เรียน', hits)['mode'], 'retrieval_fallback')


class APIRegressionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        courses = load_jsonl(ROOT/'data/seed/courses.jsonl')
        self.stack.enter_context(patch('thaimooc.api.read_courses', return_value=courses))
        self.stack.enter_context(patch.object(api.SemanticEngine, 'from_disk', return_value=None))
        self.client = self.stack.enter_context(TestClient(api.app))

    def test_user_pages_and_assets_available_without_semantic(self):
        for route in ['/', '/compare', '/research', '/assets/app.js', '/assets/research.js']:
            with self.subTest(route=route): self.assertEqual(self.client.get(route).status_code, 200)
        self.assertFalse(self.client.get('/health').json()['semantic_available'])
        self.assertEqual(self.client.post('/compare', json={'query':'เรียน'}).status_code, 503)

    def test_search_validation_and_strict_filter(self):
        for payload in [{'query':'  '}, {'query':'เรียน','top_k':0}, {'query':'เรียน','max_hours':-1}]:
            self.assertEqual(self.client.post('/search', json=payload).status_code, 422)
        result = self.client.post('/search', json={'query':'ไซเบอร์', 'max_hours':3})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(all(r['course']['duration_hours'] <= 3 for r in result.json()['results']))

    def test_optional_model_runtime_error_does_not_stop_baseline(self):
        with patch.object(api.SemanticEngine, 'from_disk', side_effect=RuntimeError('model unavailable')):
            with self.assertLogs('thaimooc.api', level='WARNING'), TestClient(api.app) as client:
                self.assertEqual(client.post('/search', json={'query':'สมุนไพร'}).status_code, 200)

    def test_report_download_allowlist(self):
        self.assertEqual(self.client.get('/research/download/private-file').status_code, 404)
        for key, filename in api.REPORT_DOWNLOADS.items():
            response = self.client.get('/research/download/'+key)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, (ROOT/'reports'/filename).read_bytes())

    def test_saved_report_summaries_load(self):
        response = self.client.get('/research/data')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['corpus_count'], 120)

    def test_missing_and_malformed_reports_are_unavailable(self):
        with tempfile.TemporaryDirectory() as directory, patch('thaimooc.api.ROOT', Path(directory)):
            self.assertEqual(self.client.get('/research/data').status_code, 503)
            reports = Path(directory)/'reports'; reports.mkdir()
            for filename in ['known_target_benchmark_v1.json', 'relevance_pilot_results.json']:
                (reports/filename).write_text('{}', encoding='utf-8')
            self.assertEqual(self.client.get('/research/data').status_code, 503)

    def test_reports_from_different_corpora_are_unavailable(self):
        with tempfile.TemporaryDirectory() as directory, patch('thaimooc.api.ROOT', Path(directory)):
            reports=Path(directory)/'reports'; reports.mkdir()
            for filename in ['known_target_benchmark_v1.json', 'relevance_pilot_results.json']:
                data=json.loads((ROOT/'reports'/filename).read_text(encoding='utf-8'))
                if filename.startswith('relevance'): data['corpus_fingerprint']='different'
                (reports/filename).write_text(json.dumps(data), encoding='utf-8')
            self.assertEqual(self.client.get('/research/data').status_code, 503)


class ScoringRegressionTests(unittest.TestCase):
    def setUp(self):
        ranking=[{'course':{'course_id':str(i),'description':'source','learning_outcomes':''}} for i in range(5)]
        self.benchmark={'corpus_count':5,'corpus_fingerprint':'fixture','cases':[
            {'case_id':'case','query':'goal','tfidf':{'ranking':ranking},'semantic':{'ranking':ranking}}]}
        self.mapping=[{'candidate_id':str(i),'course_id':str(i),'original_case_id':'case'} for i in range(5)]
        self.judgments={'judgments':[{'candidate_id':str(i),'grade':0,'evidence_quotes':[]} for i in range(5)]}

    def test_all_irrelevant_pool_keeps_ndcg_undefined(self):
        result=scoring.evaluate(self.benchmark,self.judgments,self.mapping)
        self.assertIsNone(result['summary']['tfidf']['pooled_ndcg_at_5'])
        self.assertEqual(result['summary']['tfidf']['precision_at_5_strict'],0)

    def test_duplicate_judgment_rejected(self):
        self.judgments['judgments'][0]['grade']=2
        self.judgments['judgments'].append(deepcopy(self.judgments['judgments'][0]))
        with self.assertRaises(ValueError): scoring.evaluate(self.benchmark,self.judgments,self.mapping)

    def test_empty_pool_rejected(self):
        with self.assertRaises(ValueError): scoring.evaluate(self.benchmark,{'judgments':[]},[])

    def test_boolean_grade_is_not_a_relevance_label(self):
        with self.assertRaises(ValueError): scoring.metrics([True,0,0,0,0],[True,0,0,0,0])


if __name__ == '__main__': unittest.main()
