"""Paired ranking comparison, deliberately independent of LLM generation."""
from time import perf_counter
from .search import eligible_indices
from .semantic import corpus_fingerprint


def compare_engines(baseline, semantic, query, **filters):
    fingerprint = corpus_fingerprint(baseline.courses)
    if fingerprint != corpus_fingerprint(semantic.courses):
        raise ValueError('Both retrievers must use identical ordered course records')
    eligible = eligible_indices(baseline.courses, query, **filters)
    start = perf_counter()
    tfidf = baseline.search(query, min_score=None, **filters)
    baseline_ms = (perf_counter()-start)*1000
    start = perf_counter()
    dense = semantic.search(query, **filters)
    semantic_ms = (perf_counter()-start)*1000
    left = {r['course']['course_id'] for r in tfidf}
    right = {r['course']['course_id'] for r in dense}
    top_k = filters.get('top_k', 5)
    return {'query': query, 'filters': filters, 'corpus_count': len(baseline.courses),
            'corpus_fingerprint': fingerprint, 'eligible_count': len(eligible),
            'ranking_mode': 'fixed_top_k_without_relevance_threshold',
            'top_k': top_k, 'overlap_count': len(left & right), 'overlap_ids': sorted(left & right),
            'tfidf': {'label': 'Character TF-IDF', 'elapsed_ms': round(baseline_ms, 3), 'results': tfidf},
            'semantic': {'label': 'Multilingual E5 small', 'model_id': semantic.manifest['model_id'],
                         'revision': semantic.manifest['revision'], 'elapsed_ms': round(semantic_ms, 3), 'results': dense},
            'notes': ['Top-k rankings can contain irrelevant courses; no abstention threshold is applied.',
                      'Scores have different distributions and are not comparable confidence values.',
                      'Timing includes query encoding, filtering, ranking and result construction; excludes startup/index construction/network.',
                      'Overlap and latency do not determine relevance quality; human judgments are required.']}
