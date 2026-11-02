"""Reproduce the 12 x 10 quota sample from saved browser catalog pools.

Usage: python scripts/select_catalog.py pools.json selected.json
Only operates on saved visible-page evidence; does not fetch hidden APIs.
"""
import argparse
import json
from pathlib import Path
import random
from sklearn.feature_extraction.text import TfidfVectorizer

PREFERRED = {
    'คอมพิวเตอร์และเทคโนโลยี': ['NCSA00983', 'bde00978', 'bde00977'],
    'สุขภาพและการแพทย์': ['ICCS00985'],
    'ธุรกิจและการบริหารจัดการ': ['TAT00986'],
}


def select(pools, per_category=10):
    selected = []
    for pool in pools:
        courses = list({c['url']: dict(c) for c in pool['courses']}.values())
        if len(courses) < per_category:
            raise ValueError(f"Not enough candidates in {pool['category']}")
        for c in courses:
            lines = [line.strip() for line in c['text'].splitlines() if line.strip()]
            c.update(institution=lines[0], title=lines[1], category=pool['category'])
        matrix = TfidfVectorizer(analyzer='char', ngram_range=(2, 4)).fit_transform([c['title'] for c in courses])
        similarity = (matrix @ matrix.T).toarray()
        chosen = [i for key in PREFERRED.get(pool['category'], []) for i, c in enumerate(courses)
                  if c['url'].endswith('/' + key)]
        order = list(range(len(courses)))
        random.Random(42).shuffle(order)
        if not chosen:
            chosen = [order[0]]
        while len(chosen) < per_category:
            institutions = {courses[i]['institution'] for i in chosen}
            candidate = max((i for i in order if i not in chosen), key=lambda i:
                1-float(max(similarity[i, j] for j in chosen))
                + (0.15 if courses[i]['institution'] not in institutions else 0))
            chosen.append(candidate)
        selected.extend(courses[i] for i in chosen)
    if len({c['url'] for c in selected}) != len(selected):
        raise ValueError('Duplicate course across categories')
    return selected


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pools'); parser.add_argument('output')
    args = parser.parse_args()
    chosen = select(json.loads(Path(args.pools).read_text(encoding='utf-8')))
    Path(args.output).write_text(json.dumps(chosen, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Selected {len(chosen)} unique courses')
