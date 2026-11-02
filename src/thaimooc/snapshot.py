"""Parse a rendered, public course-page snapshot captured through the browser.

No network requests and no inferred course metadata. The catalog title and
institution must be present verbatim in the corresponding detail snapshot.
"""
import re
from .data import Course


def parse_snapshot(record):
    lines = [line.strip() for line in record['rendered_text'].splitlines()
             if line.strip() and line.strip() != '•']
    if record['title'] not in lines:
        raise ValueError(f"Catalog title not verified on detail page: {record['url']}")
    title_index = lines.index(record['title'])
    institution_matches = [line for line in lines[title_index + 1:]
                           if line.casefold() == record['institution'].casefold()]
    if not institution_matches:
        raise ValueError(f"Catalog institution not verified on detail page: {record['url']}")

    def section(start, stop, required=True):
        begin = lines.index(start) + 1
        end = lines.index(stop, begin)
        content = '\n'.join(lines[begin:end]).strip()
        if required and not content:
            raise ValueError(f"Empty {start}: {record['url']}")
        return content

    overview = lines[lines.index('ภาพรวมรายวิชา') + 1:lines.index('สำหรับผู้เรียน')]

    def metadata(label):
        if label not in overview:
            return None
        index = overview.index(label) + 1
        return overview[index] if index < len(overview) else None

    category = metadata('หมวดหมู่รายวิชา')
    if category != record['category']:
        raise ValueError(f"Category differs from selected category: {record['url']}")
    duration = metadata('ระยะเวลา')
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*ชั่วโมง', duration or '')
    if duration and not match:
        raise ValueError(f"Unknown duration format: {duration}")
    return Course(
        course_id=record['url'].rstrip('/').split('/')[-1],
        title=record['title'], institution=institution_matches[0],
        description=section('เกี่ยวกับรายวิชานี้', 'ผลลัพธ์การเรียนรู้'),
        learning_outcomes=section('ผลลัพธ์การเรียนรู้', 'ผู้สอน', required=False),
        prerequisites=section('ความรู้พื้นฐาน', 'เกณฑ์การประเมิน'),
        category=category, level=metadata('ระดับ'),
        duration_hours=float(match.group(1)) if match else None,
        url=record['url'], collected_at=record['collected_at'],
        provenance='browser_rendered_snapshot; exact visible text; source snapshot: '
                   + record['url'].rstrip('/').split('/')[-1] + '.json',
    )
