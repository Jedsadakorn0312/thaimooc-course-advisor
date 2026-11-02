import unittest
from thaimooc.snapshot import parse_snapshot


class SnapshotTests(unittest.TestCase):
    def record(self):
        return {'title': 'วิชาทดสอบ', 'institution': 'สถาบันทดสอบ', 'category': 'คอมพิวเตอร์และเทคโนโลยี',
                'url': 'https://thaimooc.ac.th/courses/TEST001', 'collected_at': '2026-11-02T12:00:00Z',
                'rendered_text': '\n'.join(['วิชาทดสอบ', 'สถาบันทดสอบ', 'เกี่ยวกับรายวิชานี้', 'ข้อมูลสำหรับเรียน',
                'ผลลัพธ์การเรียนรู้', '•', 'เข้าใจข้อมูล', 'ผู้สอน', 'อาจารย์', 'ภาพรวมรายวิชา',
                'หมวดหมู่รายวิชา', 'คอมพิวเตอร์และเทคโนโลยี', 'ระดับ', 'เบื้องต้น', 'ระยะเวลา',
                '3 ชั่วโมง', 'สำหรับผู้เรียน', 'ความรู้พื้นฐาน', 'ไม่มี', 'เกณฑ์การประเมิน', '70'])}

    def test_extracts_visible_evidence_without_navigation(self):
        course = parse_snapshot(self.record())
        self.assertEqual(course.description, 'ข้อมูลสำหรับเรียน')
        self.assertEqual(course.learning_outcomes, 'เข้าใจข้อมูล')
        self.assertEqual(course.duration_hours, 3)
        self.assertEqual(course.prerequisites, 'ไม่มี')

    def test_wrong_title_fails_instead_of_importing_stale_page(self):
        record = self.record(); record['title'] = 'หน้าที่ยังไม่โหลด'
        with self.assertRaises(ValueError): parse_snapshot(record)

    def test_empty_outcomes_remain_missing(self):
        record = self.record(); record['rendered_text'] = record['rendered_text'].replace('เข้าใจข้อมูล\n', '')
        self.assertEqual(parse_snapshot(record).learning_outcomes, '')

    def test_institution_case_is_normalized_from_detail_evidence(self):
        record = self.record(); record['institution'] = 'TEST UNIVERSITY'
        record['rendered_text'] = record['rendered_text'].replace('สถาบันทดสอบ', 'Test University')
        self.assertEqual(parse_snapshot(record).institution, 'Test University')

    def test_mismatched_category_is_not_silently_relabelled(self):
        record = self.record(); record['category'] = 'ภาษา'
        with self.assertRaises(ValueError): parse_snapshot(record)

    def test_unrecognized_duration_is_not_guessed(self):
        record = self.record(); record['rendered_text'] = record['rendered_text'].replace('3 ชั่วโมง', 'ประมาณครึ่งวัน')
        with self.assertRaises(ValueError): parse_snapshot(record)


if __name__ == '__main__': unittest.main()
