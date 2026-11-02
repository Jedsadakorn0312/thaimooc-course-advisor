"""Score frozen 0/1/2 query-course judgments against paired saved rankings.

nDCG uses the judged union of the two Top-5 lists as the ideal pool. It is not
catalog-wide nDCG: relevant courses missed by BOTH methods are not judged.
Pools with no positive labels have undefined nDCG (None); omit them from the
mean nDCG while retaining them in precision and Top-1 metrics.
"""
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean


def metrics(grades, pooled_grades, k=5):
    if len(grades) != k:
        raise ValueError('This pilot requires exactly five judged results per ranking')
    if any(type(g) is not int or g not in (0, 1, 2) for g in [*grades, *pooled_grades]):
        raise ValueError('Grades must be 0, 1, or 2')
    dcg=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(grades))
    ideal=sorted(pooled_grades,reverse=True)[:k]
    idcg=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(ideal))
    return {'precision_at_5_strict':sum(g==2 for g in grades)/k,
            'precision_at_5_including_partial':sum(g>=1 for g in grades)/k,
            'pooled_ndcg_at_5':dcg/idcg if idcg else None,
            'top_1_strict':int(grades[0]==2),
            'grade_counts':{str(g):grades.count(g) for g in (0,1,2)}}


def evaluate(benchmark, judgments, mapping):
    by_id={r['candidate_id']:r for r in judgments['judgments']}
    if (not mapping or len(by_id)!=len(judgments['judgments'])
            or len({(m['original_case_id'],m['course_id']) for m in mapping})!=len(mapping)
            or len(by_id)!=len(mapping) or set(by_id)!={m['candidate_id'] for m in mapping}):
        raise ValueError('All pooled candidates must have exactly one judgment')
    lookup={(m['original_case_id'],m['course_id']):by_id[m['candidate_id']] for m in mapping}
    case_ids=list(dict.fromkeys(m['original_case_id'] for m in mapping))
    originals={c['case_id']:c for c in benchmark['cases']}
    rows=[]
    for case_id in case_ids:
        original=originals[case_id]
        union={r['course']['course_id']:r['course'] for method in ('tfidf','semantic') for r in original[method]['ranking']}
        pool=[lookup[case_id,cid]['grade'] for cid in union]
        row={'case_id':case_id,'query':original['query'],'methods':{}}
        for cid,course in union.items():
            judgment=lookup[case_id,cid]
            source=course['description']+'\n'+course['learning_outcomes']
            if not all(quote in source for quote in judgment['evidence_quotes']):
                raise ValueError('Evidence quote does not occur in source')
        for method in ('tfidf','semantic'):
            grades=[lookup[case_id,item['course']['course_id']]['grade'] for item in original[method]['ranking']]
            row['methods'][method]={'grades':grades,**metrics(grades,pool)}
        rows.append(row)
    summary={}
    for method in ('tfidf','semantic'):
        def average(key):
            values = [r['methods'][method][key] for r in rows if r['methods'][method][key] is not None]
            return mean(values) if values else None
        summary[method]={key:average(key)
                         for key in ('precision_at_5_strict','precision_at_5_including_partial','pooled_ndcg_at_5','top_1_strict')}
        summary[method]['positions']=len(rows)*5
        summary[method]['grade_counts']={str(g):sum(r['methods'][method]['grades'].count(g) for r in rows) for g in (0,1,2)}
    return {'evaluation_type':'AI self-judged source-relevance pilot, not human validation',
            'queries':len(rows),'unique_query_course_pairs':len(mapping),
            'corpus_count':benchmark['corpus_count'],'corpus_fingerprint':benchmark['corpus_fingerprint'],
            'judge':{k:v for k,v in judgments.items() if k!='judgments'},
            'metric_limit':'nDCG ideal is the judged pooled union of Top 5, not all 120 courses; precision counts only grade 2 as strict relevance.',
            'summary':summary,'cases':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('benchmark');parser.add_argument('judgments');parser.add_argument('mapping');parser.add_argument('output')
    args=parser.parse_args()
    load=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    result=evaluate(load(args.benchmark),load(args.judgments),load(args.mapping))
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'queries':result['queries'],'pairs':result['unique_query_course_pairs'],'summary':result['summary']},ensure_ascii=False,indent=2))
