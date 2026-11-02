"""Save exploratory paired results, NOT a relevance benchmark or held-out test."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from thaimooc.data import read_courses, ROOT
from thaimooc.search import SearchEngine
from thaimooc.semantic import SemanticEngine
from thaimooc.comparison import compare_engines

CASES = [
    ('direct', 'อยากเรียนการออกแบบ Data Visualization', {}),
    ('paraphrase', 'อยากเล่าตัวเลขด้วยภาพให้คนเข้าใจง่าย', {}),
    ('direct', 'อยากเรียนคลังข้อมูล', {}),
    ('paraphrase', 'อยากรวบรวมข้อมูลในองค์กรเพื่อช่วยวิเคราะห์และตัดสินใจ', {}),
    ('cross_language', 'I want to learn how to protect my personal data online', {}),
    ('paraphrase', 'อยากทำธุรกิจแต่ยังไม่รู้ว่าจะหาเงินทุนจากไหน', {}),
    ('direct', 'อยากเรียนรสยาสมุนไพรและธาตุเจ้าเรือน', {}),
    ('paraphrase', 'อยากพาชุมชนพัฒนาการท่องเที่ยวโดยไม่ทำลายสิ่งแวดล้อม', {}),
    ('time_filter', 'อยากเข้าใจการใช้ปัญญาประดิษฐ์ในการทำงาน', {'max_hours': 3}),
    ('category_filter', 'อยากฝึกสื่อสารกับคนต่างวัฒนธรรม', {'category': 'ภาษาและการสื่อสาร'}),
    ('possibly_unsupported', 'อยากเรียนดำน้ำลึกและซ่อมอุปกรณ์ดำน้ำ', {}),
    ('no_eligible', 'อยากเรียนไซเบอร์', {'max_hours': .5}),
]


if __name__ == '__main__':
    courses = read_courses()
    baseline, semantic = SearchEngine(courses), SemanticEngine.from_disk(courses)
    # Warm query execution once per method. No first-load cost is included below.
    compare_engines(baseline, semantic, 'ข้อมูล', top_k=5)
    cases = []
    for number, (kind, query, filters) in enumerate(CASES, 1):
        result = compare_engines(baseline, semantic, query, top_k=5, **filters)
        cases.append({'case_id': f'explore-{number:02d}', 'kind': kind, **result})
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'purpose': 'exploratory development examples only',
              'human_judgments_available': False, 'winner': None,
              'timing_protocol': 'one query warmup, one measured execution per case; TF-IDF executed before semantic; not a rigorous latency benchmark',
              'cases': cases}
    directory = ROOT / 'reports'
    directory.mkdir(exist_ok=True)
    (directory / 'comparison_exploration.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (directory / 'comparison_judgments_draft.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['case_id', 'kind', 'query', 'filters', 'method', 'rank', 'course_id', 'title', 'url', 'similarity', 'elapsed_ms', 'relevance_0_1_2', 'reviewer_note']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            for method in ('tfidf', 'semantic'):
                for rank, item in enumerate(case[method]['results'], 1):
                    writer.writerow({'case_id': case['case_id'], 'kind': case['kind'], 'query': case['query'],
                        'filters': json.dumps(case['filters'], ensure_ascii=False), 'method': method, 'rank': rank,
                        'course_id': item['course']['course_id'], 'title': item['course']['title'], 'url': item['course']['url'],
                        'similarity': item['score'], 'elapsed_ms': case[method]['elapsed_ms'],
                        'relevance_0_1_2': '', 'reviewer_note': ''})
    print(json.dumps([{'case_id': c['case_id'], 'query': c['query'],
                      'tfidf_top': [r['course']['title'] for r in c['tfidf']['results'][:2]],
                      'semantic_top': [r['course']['title'] for r in c['semantic']['results'][:2]],
                      'tfidf_ms': c['tfidf']['elapsed_ms'], 'semantic_ms': c['semantic']['elapsed_ms']}
                     for c in cases], ensure_ascii=False, indent=2))
