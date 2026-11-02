from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from thaimooc.data import Course, load_jsonl, save_courses, read_courses, quality_report, ROOT
from thaimooc.search import SearchEngine
from thaimooc.generation import recommend, validate_recommendations
from thaimooc.collector import parse_course
from thaimooc.evaluation import evaluate


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.courses = load_jsonl(ROOT / "data/seed/courses.jsonl")
        cls.engine = SearchEngine(cls.courses)

    def test_thai_relevance(self):
        result = self.engine.search("รสยาสมุนไพร ธาตุเจ้าเรือน")
        self.assertEqual(result[0]["course"]["course_id"], "ICCS00985")

    def test_missing_duration_does_not_pass_cap(self):
        engine = SearchEngine([replace(self.courses[0], duration_hours=None)])
        self.assertEqual(engine.search("ท่องเที่ยว", max_hours=5), [])

    def test_filters_are_hard_constraints(self):
        results = self.engine.search("ไซเบอร์", max_hours=3)
        self.assertNotIn("NCSA00983", [r["course"]["course_id"] for r in results])
        self.assertEqual(self.engine.search("ไซเบอร์", level="สูงมาก"), [])

    def test_no_lexical_overlap(self):
        self.assertEqual(self.engine.search("zzzzzzzz"), [])

    def test_natural_language_query_excludes_incidental_overlap(self):
        results = self.engine.search("อยากเรียนเรื่องรสยาสมุนไพรและธาตุเจ้าเรือน")
        self.assertEqual([r["course"]["course_id"] for r in results], ["ICCS00985"])

    def test_unsupported_goal_is_not_filled_with_unrelated_courses(self):
        self.assertEqual(self.engine.search("อยากเป็น Data Analyst"), [])

    def test_blank_query(self):
        with self.assertRaises(ValueError): self.engine.search("  ")

    def test_reimport_updates_not_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder)/"courses.sqlite3"
            save_courses(self.courses, db)
            save_courses([replace(self.courses[0], title="Updated")], db)
            records = read_courses(db)
            self.assertEqual(len(records), 3)
            self.assertTrue(any(c.title == "Updated" for c in records))

    def test_unapproved_source_rejected(self):
        with self.assertRaises(ValueError): replace(self.courses[0], url="https://evil.example/courses/TAT00986")

    def test_unknown_llm_citation_rejected(self):
        with self.assertRaises(ValueError):
            validate_recommendations('{"recommendations":[{"course_id":"FAKE","reason":"x"}]}', self.engine.search("สมุนไพร"))

    def test_server_owns_url(self):
        hits = self.engine.search("สมุนไพร")
        cid = hits[0]["course"]["course_id"]
        out = validate_recommendations(json.dumps({"recommendations":[{"course_id":cid,"reason":"เหมาะกับเป้าหมาย"}]}), hits)
        self.assertEqual(out[0]["course"]["url"], hits[0]["course"]["url"])

    def test_ollama_offline_falls_back_honestly(self):
        with patch("thaimooc.generation.urlopen", side_effect=URLError("offline")):
            self.assertEqual(recommend("สมุนไพร", self.engine.search("สมุนไพร"))["mode"], "retrieval_fallback")

    def test_no_matches_skips_llm(self):
        with patch("thaimooc.generation.urlopen") as request:
            self.assertEqual(recommend("x", [])["mode"], "no_matches")
            request.assert_not_called()

    def test_parser_rejects_javascript_shell(self):
        with self.assertRaises(ValueError): parse_course("<h1>Thai MOOC</h1>Loading...", self.courses[0].url)

    def test_parser_extracts_only_known_fields(self):
        html = '<h1>ตัวอย่าง</h1><h3>เกี่ยวกับรายวิชานี้</h3><p>ข้อมูลวิชา</p><h3>ผลลัพธ์การเรียนรู้</h3><p>สิ่งที่เรียน</p><h3>ผู้สอน</h3><h3>ภาพรวมรายวิชา</h3><div>ระดับ</div><div>เบื้องต้น</div><div>ระยะเวลา</div><div>2 ชั่วโมง</div>'
        c = parse_course(html, self.courses[0].url)
        self.assertEqual(c.title, "ตัวอย่าง")
        self.assertEqual(c.duration_hours, 2)
        self.assertIsNone(c.institution)

    def test_metrics_require_judged_results(self):
        with self.assertRaises(ValueError):
            evaluate(self.engine, [{"query":"สมุนไพร ท่องเที่ยว ไซเบอร์", "relevance":{"ICCS00985":2}}])


if __name__ == "__main__": unittest.main()
