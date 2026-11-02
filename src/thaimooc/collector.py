"""Conservative HTTP collector. Never disables certificate verification.

Accepts explicit course URLs; does not assume JS catalog pages are complete.
"""
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from dataclasses import asdict
from .data import Course


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        if not self.skip and tag in {"h1", "h2", "h3", "p", "li", "div", "section", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip-1)
        if not self.skip and tag in {"h1", "h2", "h3", "p", "li", "div", "section"}:
            self.parts.append("\n")

    def handle_data(self, text):
        if not self.skip:
            self.parts.append(text)


def parse_course(html, url):
    p = TextParser()
    p.feed(html)
    lines = [re.sub(r"\s+", " ", x).strip() for x in "".join(p.parts).splitlines() if x.strip()]
    text = "\n".join(lines)
    def section(start, end):
        if start not in text or end not in text.split(start, 1)[1]:
            raise ValueError(f"Missing rendered course section: {start}")
        return text.split(start, 1)[1].split(end, 1)[0].strip()
    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", html, re.S | re.I)
    if not title_match:
        raise ValueError("Missing course heading")
    title_parser = TextParser(); title_parser.feed(title_match.group(1))
    title = "".join(title_parser.parts).strip()
    if title in {"Thai MOOC", "Loading...", ""}:
        raise ValueError("Page is a JavaScript shell, not a rendered course")
    description = section("เกี่ยวกับรายวิชานี้", "ผลลัพธ์การเรียนรู้")
    outcomes = section("ผลลัพธ์การเรียนรู้", "ผู้สอน")
    def value_after(label):
        # Metadata labels are taken only from the overview, not navigation filters.
        overview = lines[lines.index("ภาพรวมรายวิชา"):] if "ภาพรวมรายวิชา" in lines else []
        if label in overview:
            i = overview.index(label)
            return overview[i+1] if i+1 < len(overview) else None
        return None
    duration = value_after("ระยะเวลา")
    match = re.fullmatch(r"([\d.]+)\s*(?:ชั่วโมง|ชม\.)", duration or "")
    return Course(course_id=urlsplit(url).path.rstrip("/").split("/")[-1], title=title,
        description=description, learning_outcomes=outcomes, url=url,
        collected_at=datetime.now(timezone.utc).isoformat(), category=value_after("หมวดหมู่รายวิชา"),
        level=value_after("ระดับ"), duration_hours=float(match.group(1)) if match else None)


def collect(url_file, output, raw_dir, delay=2.0):
    urls = list(dict.fromkeys(x.strip() for x in Path(url_file).read_text(encoding="utf-8-sig").splitlines() if x.strip() and not x.startswith("#")))
    if delay < 1:
        raise ValueError("Use at least one second between course requests")
    for url in urls:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "thaimooc.ac.th" or not re.fullmatch(r"/courses/[A-Za-z0-9_-]+", parts.path) or parts.query or parts.fragment:
            raise ValueError("Only canonical public Thai MOOC course URLs are accepted")
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    robots = RobotFileParser("https://thaimooc.ac.th/robots.txt")
    # A transport failure stops collection; do not infer permission from a failed fetch.
    robots.read()
    results = []
    for url in urls:
        if not robots.can_fetch("ThaiMoocCourseAdvisor", url):
            raise ValueError(f"robots.txt disallows {url}")
        request = Request(url, headers={"User-Agent": "ThaiMoocCourseAdvisor/0.1 (educational portfolio)"})
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8")
        cid = urlsplit(url).path.split("/")[-1]
        Path(raw_dir, f"{cid}.html").write_text(html, encoding="utf-8")
        results.append(asdict(parse_course(html, url)))
        # Checkpoint each successful record so a later error does not lose progress.
        Path(output).write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in results), encoding="utf-8")
        time.sleep(delay)
    return len(results)
