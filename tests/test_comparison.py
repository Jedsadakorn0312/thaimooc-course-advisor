from dataclasses import replace
import unittest
import numpy as np
from thaimooc.data import load_jsonl, ROOT
from thaimooc.search import SearchEngine
from thaimooc.semantic import SemanticEngine, corpus_fingerprint, token_windows
from thaimooc.comparison import compare_engines


class FakeEncoder:
    def encode(self, texts, **kwargs):
        assert texts[0].startswith('query: ')
        return np.array([[1.0, 0.0]], dtype=np.float32)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.courses = load_jsonl(ROOT / 'data/seed/courses.jsonl')
        self.baseline = SearchEngine(self.courses)
        self.manifest = {'corpus_fingerprint': corpus_fingerprint(self.courses), 'model_id': 'fake-unit-test', 'revision': 'test'}
        self.vectors = np.array([[.2,.98],[.9,.43],[.1,.99],[.6,.8]], dtype=np.float32)
        self.owners = np.array([0,0,1,2])
        self.semantic = SemanticEngine(self.courses, FakeEncoder(), self.vectors, self.owners, self.manifest)

    def test_max_chunk_aggregation_returns_unique_courses(self):
        hits = self.semantic.search('test', top_k=3)
        self.assertEqual(hits[0]['course']['course_id'], self.courses[0].course_id)
        self.assertAlmostEqual(hits[0]['score'], .9, places=5)
        self.assertEqual(len({r['course']['course_id'] for r in hits}), 3)

    def test_comparison_uses_fixed_k_even_without_lexical_overlap(self):
        result = compare_engines(self.baseline, self.semantic, 'zzzzzz', top_k=3)
        self.assertEqual(len(result['tfidf']['results']), 3)
        self.assertTrue(all(r['score'] == 0 for r in result['tfidf']['results']))
        self.assertEqual(len(result['semantic']['results']), 3)
        self.assertEqual(result['corpus_count'], 3)

    def test_identical_strict_duration_filter(self):
        result = compare_engines(self.baseline, self.semantic, 'เรียน', top_k=5, max_hours=3)
        for method in ['tfidf', 'semantic']:
            self.assertTrue(all(r['course']['duration_hours'] <= 3 for r in result[method]['results']))
            self.assertEqual(len(result[method]['results']), result['eligible_count'])

    def test_no_eligible_courses_yields_two_empty_rankings(self):
        result = compare_engines(self.baseline, self.semantic, 'เรียน', top_k=5, category='ไม่พบหมวดนี้')
        self.assertEqual(result['eligible_count'], 0)
        self.assertEqual(result['tfidf']['results'], [])
        self.assertEqual(result['semantic']['results'], [])

    def test_changed_metadata_invalidates_cache(self):
        changed = [replace(self.courses[0], duration_hours=99), *self.courses[1:]]
        with self.assertRaises(ValueError):
            SemanticEngine(changed, FakeEncoder(), self.vectors, self.owners, self.manifest)

    def test_compare_rejects_different_corpora(self):
        different = SearchEngine([replace(self.courses[0], title='Changed'), *self.courses[1:]])
        with self.assertRaises(ValueError): compare_engines(different, self.semantic, 'เรียน')

    def test_every_course_must_have_embeddings(self):
        with self.assertRaises(ValueError):
            SemanticEngine(self.courses, FakeEncoder(), self.vectors, np.array([0,0,1,1]), self.manifest)

    def test_long_document_windows_cover_tail(self):
        chunks = list(token_windows(list(range(1400))))
        self.assertTrue(all(len(c) <= 448 for c in chunks))
        self.assertEqual(set(x for chunk in chunks for x in chunk), set(range(1400)))
        self.assertEqual(chunks[-1][-1], 1399)


if __name__ == '__main__': unittest.main()
