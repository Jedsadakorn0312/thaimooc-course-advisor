"""Evidence-linked known-target retrieval diagnostic, not human-judged relevance.

Queries and targets are frozen to JSON before running either engine. No model,
threshold, sampling or query edits are selected using the scores from this run.
"""
from collections import Counter, defaultdict
import argparse
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
from time import perf_counter
import numpy as np
from thaimooc.data import ROOT, read_courses
from thaimooc.search import SearchEngine, eligible_indices
from thaimooc.semantic import SemanticEngine, corpus_fingerprint

# Assistant-authored targets verified against course text; NOT independent gold.
TARGETS = [
 ('PDPC00984', 'อยากรู้สิทธิของฉันเมื่อบริษัทเก็บข้อมูลส่วนตัวและวิธีรับมือเมื่อข้อมูลรั่ว', 'I want to understand my rights over personal information and respond to a data breach', 'สิทธิของเจ้าของข้อมูล'),
 ('CMU00088', 'อยากให้นักเรียนมีส่วนร่วมในชั้นและกล้าถามตอบมากกว่านั่งฟังครูอย่างเดียว', 'I want students to participate actively and ask questions instead of only listening to lectures', 'กระตือรือร้น'),
 ('KMUTT00291', 'ไม่เคยเขียนโค้ด อยากเริ่มไพธอนและลองใช้ Pandas จัดข้อมูลกับวาดกราฟ', 'I am new to programming and want to learn Python with pandas and simple plots', 'Pandas'),
 ('CU00148', 'อยากรู้วิธีเปลี่ยนขยะพลาสติกให้กลายเป็นน้ำมันเชื้อเพลิง', 'I want to turn discarded plastic into liquid fuel', 'ขยะพลาสติก'),
 ('CRRU00120', 'อยากปรับแต่งรูปและจัดวางองค์ประกอบภาพดิจิทัลด้วยโปรแกรมแต่งภาพ', 'I want to edit digital pictures and arrange visual elements with an image editor', 'การปรับแต่งภาพ'),
 ('CMU00099', 'อยากออกแบบโครงสร้างข้อมูลแบบมิติและโหลดข้อมูลเพื่อวิเคราะห์ด้วย OLAP', 'I want to design dimensional data models and load data for OLAP analysis', 'ไดเมนชัน'),
 ('BUU00061', 'อยากมองปัญหาในองค์กรให้เห็นความเชื่อมโยงของหลายส่วนก่อนลงมือแก้', 'I want to understand interconnected organizational problems using systems thinking', 'การคิดเชิงระบบ'),
 ('NU00418', 'อยากสร้างทีมให้ทำงานร่วมกันได้ดีและเข้าใจปัจจัยที่ทำให้ทีมมีประสิทธิภาพ', 'I want to build an effective team and understand what makes people work well together', 'การสร้างทีมงานที่มีประสิทธิภาพ'),
 ('NU00420', 'อยากวางแผนเงินของตัวเองด้วย Excel และทำความเข้าใจการลงทุนเน้นคุณค่า', 'I want to plan my personal finances in Excel and understand value investing', 'Excel'),
 ('DEPA00173', 'อยากเริ่มธุรกิจใหม่ หาไอเดียลูกค้าและเตรียมนำเสนอแผนให้ผู้ลงทุน', 'I want to launch a startup, identify customers and pitch my business to investors', 'Pitch'),
 ('NOU00376', 'อยากพูดภาษาจีนใช้ในชีวิตประจำวันเวลาไปไต้หวัน เช่น ร้านอาหารและถามทาง', 'I want everyday Mandarin phrases for ordering food and asking directions in Taiwan', 'Taiwan'),
 ('CU00150', 'อยากฝึกเขียนอธิบายตาราง กราฟ และชาร์ตเป็นภาษาอังกฤษ', 'I want English vocabulary and phrases for describing tables, graphs and charts', 'แนะนำคำศัพท์ภาษาอังกฤษ'),
 ('ICCS00894', 'อยากตรวจสภาพแบตเตอรี่เก่า วัดน้ำกรดและเรียนการใช้เครื่องฟื้นฟู', 'I want to test old batteries, measure acid concentration and learn battery restoration', 'น้ำกรดแบตเตอรี่'),
 ('NU00448', 'อยากออกแบบอาคารและเลือกเทคโนโลยีก่อสร้างที่ลดผลกระทบต่อสิ่งแวดล้อม', 'I want to design environmentally friendly buildings and choose green construction technologies', 'เทคนิคการออกแบบทางสถาปัตยกรรม'),
 ('ICCS00904', 'อยากเรียนวิธีเขียนลายและปักสไบมอญแบบสมุทรสาคร', 'I want to design and embroider traditional Mon sabai garments from Samut Sakhon', 'การปักลาย'),
 ('DRU00183', 'อยากฝึกถ่ายทอดอารมณ์ผ่านสีหน้าแววตาและร่างกายสำหรับการแสดงหน้ากล้อง', 'I want to express emotions through facial expressions and body movement when acting on camera', 'สีหน้า แววตา'),
 ('EAU00184', 'อยากเข้าใจการรวมกลุ่มของประเทศอาเซียนและความท้าทายของประชาคม', 'I want to understand ASEAN integration and the challenges facing its member countries', 'การรวมกลุ่มอาเซียน'),
 ('HU00189', 'อยากเข้าใจความรับผิดทางอาญา เจตนา ประมาท และเหตุลดหย่อนโทษ', 'I want to study criminal liability, intent, negligence and grounds for reducing punishment', 'การกระทำโดยเจตนา'),
 ('SRU00898', 'อยากหาหลักสูตรดูแลผู้ป่วยที่ลุกจากเตียงไม่ได้ รวมถึงอาหารทางสายยางและการดูแลแผล', 'I want a course on caring for bedridden patients including tube feeding and wound care', 'การให้อาหารทางสายยาง'),
 ('DDC00170', 'อยากเรียนแนวทางสำหรับบุคลากรดูแลผู้สัมผัสโรคพิษสุนัขบ้าและการให้วัคซีน', 'I want a course for healthcare staff about rabies exposure management and vaccination', 'การฉีดวัคซีนป้องกันโรคพิษสุนัขบ้า'),
 ('ICCS00957', 'อยากฝึกทำวุ้นแฟนซี ช่อม่วง และคิดต้นทุนตั้งราคาขายขนม', 'I want to make Thai sweets such as fancy jelly and chor muang and calculate selling prices', 'ขนมช่อม่วง'),
 ('SRU00813', 'อยากแปรรูปโกโก้เป็นช็อกโกแลตและเรียนเรื่องคุณภาพบรรจุภัณฑ์กับการเก็บรักษา', 'I want to process cocoa into chocolate and learn quality control, packaging and storage', 'บรรจุภัณฑ์และการเก็บรักษา'),
 ('CMU00069', 'อยากปลูกเลี้ยงผสมพันธุ์กล้วยไม้และรู้ปัจจัยที่ทำให้เจริญเติบโต', 'I want to cultivate and breed orchids and understand their growing conditions', 'การผสมพันธุ์'),
 ('DEPA00178', 'อยากใช้เซ็นเซอร์ควบคุมการให้น้ำแปลงเกษตรอัตโนมัติผ่านโทรศัพท์', 'I want to use sensors and a phone to control automatic crop irrigation', 'การให้น้ำอัตโนมัติ'),
]


def rank_metrics(results, target):
    rank = next((i for i, item in enumerate(results, 1) if item['course']['course_id'] == target), None)
    return {'target_rank': rank, 'hit_at_1': int(rank == 1), 'hit_at_5': int(rank is not None),
            'reciprocal_rank_at_5': 1/rank if rank else 0.0}


def summary(rows):
    out = {}
    for group in ['all', 'direct_title', 'thai_goal', 'english_goal']:
        subset = rows if group == 'all' else [r for r in rows if r['kind'] == group]
        out[group] = {'queries': len(subset)}
        for method in ['tfidf', 'semantic']:
            out[group][method] = {metric: float(np.mean([r[method][metric] for r in subset]))
                for metric in ['hit_at_1', 'hit_at_5', 'reciprocal_rank_at_5']}
            out[group][method]['median_query_ms'] = float(np.median([r[method]['median_query_ms'] for r in subset]))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        default=ROOT/'reports/runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    args = parser.parse_args()
    reports = args.output_dir
    output_names = ['known_target_benchmark_v1.json', 'known_target_rankings_v1.csv']
    if any((reports/name).exists() for name in output_names):
        parser.error('Output already exists. Choose a new --output-dir to preserve prior results.')
    reports.mkdir(parents=True, exist_ok=True)
    courses = read_courses(); by_id = {c.course_id: c for c in courses}
    assert len(courses) == 120
    cases = []
    for target, thai, english, evidence in TARGETS:
        course = by_id[target]
        assert evidence in course.search_text(), (target, evidence)
        for kind, query in [('direct_title', 'อยากเรียน ' + course.title), ('thai_goal', thai), ('english_goal', english)]:
            cases.append({'case_id': f'{target}-{kind}', 'target_id': target, 'category': course.category,
                          'kind': kind, 'query': query, 'evidence': evidence, 'source_url': course.url})
    assert len(cases) == 72 and len(Counter(c['category'] for c in cases)) == 12
    # Use the frozen query set; rerunning must not rewrite its timestamp or labels.
    frozen = (ROOT/'evaluation/known_target_cases_v1.json').read_text(encoding='utf-8')
    payload = json.loads(frozen)
    if payload['corpus_fingerprint'] != corpus_fingerprint(courses) or payload['cases'] != cases:
        raise ValueError('Frozen cases differ from the catalog or protocol; create a separately versioned experiment')
    case_hash = hashlib.sha256(frozen.encode()).hexdigest()
    baseline, semantic = SearchEngine(courses), SemanticEngine.from_disk(courses)
    methods = {'tfidf': lambda q, **kw: baseline.search(q, min_score=None, **kw),
               'semantic': lambda q, **kw: semantic.search(q, **kw)}
    for run in methods.values():
        for _ in range(3): run('อยากพัฒนาทักษะการเรียนรู้', top_k=5)
    rng = np.random.default_rng(42)
    rows = []
    for case in cases:
        measurements = {'tfidf': [], 'semantic': []}; rankings = {}
        for repeat in range(5):
            order = ['tfidf', 'semantic'] if rng.integers(2) else ['semantic', 'tfidf']
            for method in order:
                start = perf_counter(); hits = methods[method](case['query'], top_k=5)
                measurements[method].append((perf_counter()-start)*1000)
                if method in rankings:
                    assert [r['course']['course_id'] for r in rankings[method]] == [r['course']['course_id'] for r in hits]
                rankings[method] = hits
        row = dict(case)
        for method in methods:
            row[method] = {**rank_metrics(rankings[method], case['target_id']),
                           'median_query_ms': float(np.median(measurements[method])),
                           'timings_ms': measurements[method], 'ranking': rankings[method]}
        rows.append(row)

    filter_checks = []
    for target, thai, _, _ in TARGETS:
        c = by_id[target]
        filters = {'top_k': 5, 'max_hours': c.duration_hours, 'category': c.category, 'level': c.level}
        expected = set(eligible_indices(courses, thai, **filters))
        check = {'target_id': target, 'filters': filters, 'eligible_count': len(expected)}
        for method, run in methods.items():
            hits = run(thai, **filters)
            allowed = {courses[i].course_id for i in expected}
            check[method] = len(hits) == min(5, len(allowed)) and all(r['course']['course_id'] in allowed for r in hits)
            assert check[method]
        filter_checks.append(check)
    for method, run in methods.items():
        assert run('อยากเรียนรู้', top_k=5, max_hours=.5) == []

    # Paired bootstrap by course, keeping its three query variants together.
    grouped = defaultdict(list)
    for row in rows: grouped[row['target_id']].append(row)
    deltas = np.array([np.mean([r['semantic']['reciprocal_rank_at_5']-r['tfidf']['reciprocal_rank_at_5'] for r in family]) for family in grouped.values()])
    boot = np.mean(deltas[rng.integers(0, len(deltas), size=(3000, len(deltas)))], axis=1)
    report = {'run_at': datetime.now(timezone.utc).isoformat(), 'corpus_count': len(courses),
              'corpus_fingerprint': corpus_fingerprint(courses), 'case_content_sha256': case_hash,
              'semantic_model': semantic.manifest, 'protocol': {'top_k': 5, 'thresholds': 'disabled for both',
              'repeats_per_query': 5, 'warmup_queries_per_method': 3, 'method_order': 'seeded randomized per repetition',
              'device': 'CPU, semantic torch threads=4', 'timing_scope': 'query encoding + filters + ranking + record construction; excludes startup/index/network'},
              'limitations': ['Assistant-authored known targets from source descriptions, not independent human judgments.',
              'Targets are not exhaustive relevance sets; a different relevant result is not credited by these target metrics.',
              'Direct-title queries are deliberately easy; report Thai-goal and English-goal subsets separately.',
              'Some topic families were viewed in earlier exploratory runs; this is a development diagnostic, not a blind held-out benchmark.',
              'No abstention or out-of-scope detection quality is measured, because fixed Top K is forced.',
              '24 course families are not representative of all learner goals or the entire Thai MOOC catalog.'],
              'summary': summary(rows), 'paired_course_bootstrap': {'metric': 'MRR@5 semantic minus tfidf, all three query types',
              'mean_delta': float(np.mean(deltas)), 'descriptive_95_interval': [float(x) for x in np.quantile(boot,[.025,.975])]},
              'filter_checks_passed': {'tfidf': 25, 'semantic': 25}, 'filter_details': filter_checks, 'cases': rows}
    (reports / 'known_target_benchmark_v1.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (reports / 'known_target_rankings_v1.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields=['case_id','kind','query','target_id','target_title','source_url','method','target_rank','hit_at_1','hit_at_5','reciprocal_rank_at_5','median_query_ms','top_5_titles']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:
            for method in methods:
                result=row[method]
                writer.writerow({**{key:row[key] for key in ['case_id','kind','query','target_id','source_url']},
                    'target_title':by_id[row['target_id']].title,'method':method,
                    **{key:result[key] for key in ['target_rank','hit_at_1','hit_at_5','reciprocal_rank_at_5','median_query_ms']},
                    'top_5_titles':' | '.join(r['course']['title'] for r in result['ranking'])})
    print(json.dumps({'summary':report['summary'],'paired_course_bootstrap':report['paired_course_bootstrap'],
                      'output_directory':str(reports),
                      'filter_checks_passed':report['filter_checks_passed']},ensure_ascii=False,indent=2))
