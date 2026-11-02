"""Rebuild the normalized JSONL from saved rendered course snapshots."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from thaimooc.snapshot import parse_snapshot
from thaimooc.data import quality_report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot_directory')
    parser.add_argument('output')
    args = parser.parse_args()
    courses = []
    for path in sorted(Path(args.snapshot_directory).glob('*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(record, dict) and 'rendered_text' in record:
            courses.append(parse_snapshot(record))
    if not courses:
        raise ValueError('No rendered course snapshots found')
    if len({c.course_id for c in courses}) != len(courses):
        raise ValueError('Duplicate course IDs in snapshots')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(asdict(c), ensure_ascii=False)+'\n' for c in courses), encoding='utf-8')
    print(json.dumps(quality_report(courses), ensure_ascii=False, indent=2))
