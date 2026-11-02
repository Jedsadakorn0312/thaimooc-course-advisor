# Thai MOOC Course Advisor · MOOC Compass

ระบบค้นหารายวิชาจาก **เป้าหมายการเรียนรู้** ผู้เรียนพิมพ์สิ่งที่อยากทำได้ เลือกเวลาและระดับ แล้วดูวิชาที่เกี่ยวข้องพร้อมลิงก์ต้นทาง มีฐานข้อมูลตัวอย่างจริง 120 วิชา และการทดลองเปรียบเทียบ TF-IDF กับ Semantic Search บนข้อมูลชุดเดียวกัน

โปรเจกต์ต้นแบบสำหรับเรียนรู้และแสดงผลงาน ไม่ใช่เว็บไซต์ทางการของ Thai MOOC ระบบหลักใช้งานได้โดยไม่ต้องมี LLM, API key หรือดาวน์โหลด embedding model

## หน้าเว็บและสถานะการทำงาน

| หน้า | ใช้ทำอะไร |
|---|---|
| `/` | หน้าผู้เรียน: เป้าหมาย → ตัวกรอง → ผลค้นหาไม่เกิน 5 วิชา → ลิงก์ไปหน้ารายวิชา |
| `/research` | สรุปผลทดลองที่บันทึกไว้ พร้อมวิธีวัด ข้อจำกัด และดาวน์โหลดรายงาน |
| `/compare` | Search Lab: ดูอันดับ TF-IDF และ Semantic เคียงกันบนข้อมูลและตัวกรองเดียวกัน |
| `/docs` | ทดลอง API ผ่าน Swagger UI |

หน้าหลักใช้ **character TF-IDF** พร้อมเกณฑ์คะแนนเริ่มต้น 0.10 ส่วน Search Lab ใช้ fixed Top K และปิดเกณฑ์คะแนนทั้งสองวิธีเพื่อเปรียบเทียบอันดับ จึงอาจมีวิชาที่ไม่เกี่ยวข้องอยู่ในผลทดลอง

- ใช้งานแล้ว: JSONL → validation → SQLite upsert, data quality report, CLI, FastAPI และหน้าเว็บภาษาไทย
- ใช้งานแล้ว: Semantic Search ด้วย `intfloat/multilingual-e5-small` และดัชนีที่สร้างไว้ในเครื่อง
- มีโค้ดเชื่อม Ollama สำหรับ `/recommend` และ CLI `--rag` แต่ **ยังไม่ได้ประเมินคำตอบจาก Qwen3 จริง** และหน้าหลักไม่ได้เรียก LLM
- ยังไม่ได้ทำ: hybrid ranking, human-validated held-out test, บัญชีผู้ใช้ หรือระบบนำขึ้น production

## เริ่มใช้งานในเครื่อง

ต้องมี Python 3.10+; ตรวจสอบการทำงานในเครื่องพัฒนาด้วย Python 3.12 บน Windows คำสั่งต่อไปนี้ใช้ PowerShell และต้องรันจากโฟลเดอร์โปรเจกต์

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m thaimooc.cli import data/catalog/courses_120.jsonl
.\.venv\Scripts\python.exe -m thaimooc.cli quality
.\.venv\Scripts\python.exe -m uvicorn thaimooc.api:app --host 127.0.0.1 --port 8000
```

เปิด [หน้าค้นหารายวิชา](http://127.0.0.1:8000/) แล้วลอง `อยากเรียนการออกแบบ Data Visualization` หรือ `อยากเรียนเรื่องรสยาสมุนไพรและธาตุเจ้าเรือน` หยุดเซิร์ฟเวอร์ด้วย `Ctrl+C`

บน macOS/Linux ใช้ `.venv/bin/python` แทน `.\.venv\Scripts\python.exe` ไม่จำเป็นต้อง activate environment หากเรียก interpreter ตาม path นี้

การติดตั้งครั้งแรกต้องมีอินเทอร์เน็ตสำหรับ dependencies หลัง import แล้ว หน้าค้นหาทำงานในเครื่องโดยไม่เรียกบริการโมเดลภายนอก ส่วนการเปิดลิงก์วิชาปลายทางต้องเชื่อมต่อเว็บไซต์ Thai MOOC

## เปิด Semantic Search เพิ่มเติม

ทำขั้นตอนนี้เฉพาะเมื่อต้องการใช้ `/compare` หรือรัน benchmark:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[semantic]"
.\.venv\Scripts\python.exe scripts/prepare_semantic.py
```

จากนั้นเริ่มเซิร์ฟเวอร์ใหม่ และเปิด [Search Lab](http://127.0.0.1:8000/compare)

- โมเดล: `intfloat/multilingual-e5-small`
- revision เริ่มต้น: `614241f622f53c4eeff9890bdc4f31cfecc418b3` ตรงกับรอบทดลองที่บันทึกไว้; เปลี่ยนได้โดยระบุ `--revision` อย่างชัดเจน
- ครั้งแรกดาวน์โหลด checkpoint จาก Hugging Face ไป `models/` และสร้าง `data/processed/semantic/`
- ตอนเปิด API โหลดโมเดลแบบ local-only ไม่ดาวน์โหลดขณะรับคำค้น หากส่วน semantic ใช้ไม่ได้ หน้าค้นหาหลักยังใช้งานได้ แต่ `/compare` จะตอบ 503
- หากเปลี่ยนข้อมูลรายวิชา ต้องสร้าง index ใหม่และเริ่มเซิร์ฟเวอร์ใหม่ เพราะตรวจ corpus fingerprint ก่อนใช้ cache
- ใช้ CPU และตั้ง PyTorch 4 threads; ขนาดโมเดลและดัชนีไม่รวมใน Git

`requirements-lock.txt` เป็น snapshot ของ environment ที่ใช้ตรวจงานบน Windows/Python 3.12 รวม semantic และเครื่องมือทดสอบ ไม่ใช่ lock ข้ามทุกระบบ หากต้องการใช้ environment นี้ ให้ติดตั้ง `pip install -r requirements-lock.txt` แล้ว `pip install -e . --no-deps` สำหรับการเริ่มต้นทั่วไปใช้คำสั่งติดตั้งด้านบน

## ข้อมูล 120 วิชามาจากไหน

ข้อมูลจริงที่บันทึกจากหน้า Thai MOOC วันที่ 2 พฤศจิกายน 2026: 12 หมวด หมวดละ 10 วิชา จาก 64 สถาบัน ระยะเวลา 1–50 ชั่วโมง ทุกวิชาระบุระดับเบื้องต้น มี 3 วิชาที่ไม่ระบุผลลัพธ์การเรียนรู้ จึงเก็บช่องนั้นว่าง

| ไฟล์ | เนื้อหา |
|---|---|
| `data/catalog/courses_120.jsonl` | ข้อมูลพร้อม import พร้อม URL และ provenance รายวิชา |
| `data/catalog/catalog_pools.json` | รายการตัวเลือกจากหน้าหมวดที่ใช้คัดเลือก |
| `data/catalog/selection_manifest.json` | วิธีเลือก seed และข้อจำกัด |
| `reports/data_quality_120.json` | จำนวนข้อมูลซ้ำและช่องที่ขาด |
| `data/seed/` | สรุป 3 วิชาจริงสำหรับ unit tests แยกจาก corpus 120 วิชา |

คัดแบบ quota และเพิ่มความหลากหลายของหัวข้อ/สถาบันจากหน้าแรกของแต่ละหมวด ใช้ character TF-IDF บนชื่อวิชาเป็น heuristic และ seed 42 **ไม่ใช่ตัวอย่างสุ่มแทนทั้งแพลตฟอร์ม** หลักฐาน browser snapshots เก็บเฉพาะในเครื่องที่ `data/raw/browser_snapshots/` และไม่รวมใน Git ผู้ clone ใช้ JSONL ที่เตรียมไว้ได้ทันที แต่จะสร้างใหม่จาก snapshots ไม่ได้หากไม่มีไฟล์หลักฐาน

ทำซ้ำการคัดจากรายการที่บันทึกไว้:

```powershell
.\.venv\Scripts\python.exe scripts/select_catalog.py data/catalog/catalog_pools.json data/processed/selected.json
```

SQLite import เป็น upsert ตาม `course_id`: อัปเดตและเพิ่มวิชา แต่ไม่ลบวิชาเดิมที่หายไปจากไฟล์ใหม่ หากต้องการ corpus 120 วิชาเท่ากับชุดทดลอง ให้ใช้ฐานข้อมูลใหม่ตั้งแต่ต้น ไม่ import seed หรือ catalog อื่นปนลงฐานเดียวกัน

## วิธีค้นหา

```text
JSONL → ตรวจ schema/URL → SQLite
                              ↓
เป้าหมาย + ตัวกรอง → ข้อความชื่อ/รายละเอียด/ผลลัพธ์การเรียนรู้ → จัดอันดับ → หน้าเว็บ
                              ├─ TF-IDF: หน้าผู้เรียน
                              └─ E5: ห้องทดลองเปรียบเทียบ
```

- ทั้งสองวิธีใช้ชื่อวิชาซ้ำสองครั้ง + description + learning_outcomes และตัวกรองเดียวกัน
- TF-IDF ใช้ character n-grams 2–5 จึงไม่ต้องอาศัยการเว้นวรรคคำไทย
- E5 ใช้ prefix `query: ` / `passage: ` และ normalized embeddings แบ่งเนื้อหายาวครั้งละ 448 tokens ซ้อน 64 tokens แล้วเลือกคะแนน chunk สูงสุดของแต่ละวิชา
- คำค้น E5 ยาวเกินบริบท 512 tokens อาจถูกตัด ควรระบุเป้าหมายกระชับ
- เวลา ระดับ และหมวดเป็นเงื่อนไขตายตัว ไม่ผ่อนอัตโนมัติ วิชาที่ไม่ทราบเวลาจะไม่ผ่านตัวกรองชั่วโมง
- similarity ไม่ใช่ความน่าจะเป็นว่าคำแนะนำถูกต้อง และคะแนนดิบของ TF-IDF กับ E5 เทียบกันโดยตรงไม่ได้
- เกณฑ์ TF-IDF 0.10 ยังเป็น heuristic ไม่ได้ calibrate กับผู้ใช้จริง ระบบอาจพลาดคำที่มีความหมายใกล้กันหรือจับคำร่วมที่ไม่ตรงเป้าหมาย

## ผลเปรียบเทียบที่บันทึกไว้

### 1. ค้นพบวิชาเป้าหมายใน Top 5

72 คำถามจาก 24 วิชาเป้าหมาย ครบ 12 หมวด บน corpus เดียวกัน 120 วิชา ปิด threshold ทั้งสองวิธี:

| กลุ่มคำถาม | TF-IDF Hit@5 | Semantic E5 Hit@5 |
|---|---:|---:|
| ตรงชื่อวิชา | 24/24 | 24/24 |
| เป้าหมายภาษาไทย | 24/24 | 23/24 |
| เป้าหมายภาษาอังกฤษ | 2/24 | 23/24 |
| รวม | 50/72 | 70/72 |

Median query latency หลังอุ่นเครื่อง: TF-IDF **2.12 ms**, E5 **21.46 ms** วัดซ้ำคำถามละ 5 รอบ สลับลำดับด้วย seed 42 บนเครื่องพัฒนา ไม่รวมโหลดโมเดล สร้างดัชนี หรือเครือข่าย ตัวกรองผ่าน 25 กรณีต่อวิธี

คำถามเขียนโดยผู้ช่วยจากรายละเอียดต้นทาง และบางหัวข้อเคยใช้ระหว่างพัฒนา จึงเป็น **development diagnostic** ไม่ใช่ independent held-out benchmark การพบ target ไม่ได้ยืนยันว่าทั้ง 5 อันดับถูกต้อง และวิชาอื่นที่เกี่ยวข้องแต่ไม่ใช่ target จะไม่ได้เครดิตจากเกณฑ์นี้

รายละเอียด: `evaluation/known_target_cases_v1.json`, `reports/known_target_benchmark_v1.json`, `reports/known_target_rankings_v1.csv`, `reports/retrieval_recommendation_v1.txt`

### 2. ตรวจความเกี่ยวข้องของทั้งห้าอันดับโดย AI

รอบนำร่อง 12 คำถามภาษาไทย รวม 99 คู่คำถาม–วิชาไม่ซ้ำ หรือ 60 ตำแหน่งต่อวิธี:

| คะแนนร่าง | TF-IDF | Semantic E5 |
|---|---:|---:|
| ตรงชัดเจน (2) | 12/60 | 11/60 |
| เกี่ยวข้องบางส่วน (1) | 3/60 | 6/60 |
| ไม่ตรงจากข้อความที่ตรวจ (0) | 45/60 | 43/60 |
| Strict Precision@5 (เฉพาะ grade 2) | 20.0% | 18.3% |
| Precision@5 รวมบางส่วน | 25.0% | 28.3% |
| Pooled nDCG@5 | 0.9375 | 0.9061 |

ผู้ประเมินคือ **Codex assistant ในแชต** ไม่ใช่ Qwen3/API ภายนอก และไม่มีคนตรวจ ผู้ช่วยคนเดิมเคยสร้างคำถามและเห็นผลก่อนหน้า แม้ packet ซ่อนชื่อวิธี/อันดับ/คะแนน ก็ไม่ใช่การตรวจอิสระหรือ strictly blind ส่วนใหญ่ใช้ข้อความคัดย่อและอ่านเต็มเฉพาะบางรายการ จึงอาจพลาดเนื้อหาที่ไม่ได้แสดง

Pooled nDCG ใช้ ideal ranking จากผลรวม Top 5 สองวิธี ไม่ใช่ทุกวิชาใน catalog คะแนนสูงจึงไม่ได้แปลว่าทั้งห้าวิชาถูกต้อง หาก pool ไม่มี grade บวก nDCG จะเป็น `null` และไม่รวมในค่าเฉลี่ย nDCG ส่วน precision ยังรวมกรณีนั้น

**ข้อสรุปปัจจุบัน:** ใช้ TF-IDF เป็นตัวเริ่มต้นสำหรับคำถามไทยในชุดนี้ ส่วน E5 เด่นด้านค้นข้ามภาษา ยังไม่ฟันธงผู้ชนะสำหรับการใช้งานจริง ผล AI pilot ต่างกันเพียง 1 รายการที่ตรงชัดเจนจาก 60 ตำแหน่ง และชี้ว่าการบังคับครบ 5 อันดับทำให้มีรายการไม่เกี่ยวข้องตามมา ต้องเก็บคำถามผู้ใช้จริงและตรวจ relevance อิสระก่อนยืนยันคุณภาพ

รายละเอียด: `evaluation/llm_judge_pilot/`, `reports/relevance_pilot_results.json`, `reports/ai_relevance_judgments_99.csv`, `reports/ai_relevance_pilot_summary.txt` หน้า `/research` อ่านผลเดิมเหล่านี้ ไม่รันทดลองใหม่เมื่อเปิดหน้า

## ทดสอบและทำซ้ำ

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

ชุดทดสอบไม่ดาวน์โหลดโมเดลและไม่เรียก Ollama: ตรวจ schema, upsert, ตัวกรอง, parser, citation/fallback, การเปรียบเทียบด้วย fake encoder, API, รายงาน และ pooled metrics นี่เป็นการตรวจความถูกต้องของซอฟต์แวร์ ไม่ใช่การรับรองความเหมาะสมของรายวิชาสำหรับผู้ใช้จริง

ทำซ้ำ benchmark เมื่อเตรียม semantic แล้ว:

```powershell
.\.venv\Scripts\python.exe scripts/run_target_benchmark.py
```

อ่านชุดคำถามที่ freeze ไว้โดยไม่เขียนทับ และเก็บผลใหม่ใน `reports/runs/<UTC timestamp>/` ระบุโฟลเดอร์อื่นด้วย `--output-dir` ได้ แต่จะปฏิเสธหากมีผลชื่อเดียวกันอยู่แล้ว ค่าเวลาอาจต่างตามเครื่องและโหลดขณะรัน รายงาน v1 ที่หน้าเว็บแสดงจะยังเหมือนเดิม

คำนวณ AI pilot ใหม่จากคะแนนเดิม โดยส่ง output ไปโฟลเดอร์ชั่วคราว:

```powershell
.\.venv\Scripts\python.exe scripts/score_pooled_judgments.py reports/known_target_benchmark_v1.json evaluation/llm_judge_pilot/assistant_judgments_v1.json evaluation/llm_judge_pilot/mapping.json data/processed/relevance_recomputed.json
```

คำสั่งนี้คำนวณ metrics จาก labels เดิม ไม่ได้เรียก LLM มาตัดสินใหม่ `scripts/run_comparison_exploration.py` เป็นตัวอย่างสำรวจ 12 คำถามสำหรับพัฒนา และเมื่อรันจะเขียนทับไฟล์ exploration เดิม จึงควรสำรองก่อนใช้

## API และ CLI

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/health` | สถานะ คุณภาพข้อมูล และความพร้อม semantic |
| GET | `/catalog` | จำนวนวิชา ระดับ และหมวดที่มีจริง |
| POST | `/search` | ค้นหา TF-IDF โดยไม่ใช้ LLM |
| POST | `/compare` | อันดับจากสองวิธี; 503 หาก semantic ไม่พร้อม |
| POST | `/recommend` | ค้นหาแล้วเรียบเรียงผ่าน Ollama หรือ fallback |
| GET | `/research/data` | สรุปรายงานเดิม; 503 หากอ่านไม่ได้หรือ corpus ต่างกัน |
| GET | `/research/download/{report_name}` | ดาวน์โหลดเฉพาะรายงานที่อยู่ใน allowlist |

Request สำหรับค้นหา/เปรียบเทียบ:

```json
{"query":"อยากเรียนสมุนไพร","top_k":5,"max_hours":3,"level":"เบื้องต้น","category":null}
```

`query` ยาว 1–2000 ตัวอักษรและต้องไม่ว่าง, `top_k` 1–20, `max_hours` เป็นจำนวนบวก ส่วนหน้าเว็บผู้เรียนกำหนดผลสูงสุด 5 วิชา

```powershell
.\.venv\Scripts\python.exe -m thaimooc.cli search "สมุนไพร" --max-hours 3
.\.venv\Scripts\python.exe -m thaimooc.cli --db data/processed/smoke.sqlite3 import data/seed/courses.jsonl
.\.venv\Scripts\python.exe -m thaimooc.cli --db data/processed/smoke.sqlite3 evaluate evaluation/smoke_queries.json --k 1
```

smoke queries ใช้เฉพาะตรวจ seed 3 วิชา ไม่ใช่ benchmark ของ corpus 120 วิชา CLI รองรับ `--level`; ตัวกรอง `category` ใช้ผ่าน API และ Search Lab

## Ollama / RAG (ส่วนเสริม)

หากติดตั้ง Ollama และเปิด service แล้ว สามารถเปิดใช้ภายหลังได้:

```powershell
ollama pull qwen3:8b
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "qwen3:8b"
.\.venv\Scripts\python.exe -m thaimooc.cli search "อยากเรียนสมุนไพร" --rag
```

`.env.example` เป็นตัวอย่างเท่านั้น โปรแกรมไม่ได้โหลด `.env` อัตโนมัติ LLM ได้เฉพาะรายวิชาที่ผ่าน retrieval และตัวกรอง ตรวจ schema, รหัสอ้างอิงและรหัสซ้ำ แล้วดึงชื่อ/URL จากฐานข้อมูล หาก service หรือคำตอบมีปัญหาจะ fallback เป็นผลค้นหา การตรวจรหัสไม่ได้รับรองว่าเหตุผลไม่หลอน ต้องประเมิน grounding เพิ่ม

## ตัวเก็บข้อมูลและข้อจำกัด

`thaimooc collect data/seed/course_urls.txt` รับ URL รายวิชาที่ระบุชัด ตรวจ robots.txt เว้นช่วง request และเก็บ HTML ดิบ ไม่ไล่ pagination อัตโนมัติ หาก TLS ไม่ผ่านจะหยุดโดยไม่ปิดการตรวจ certificate และหากเป็น JavaScript shell จะปฏิเสธแทนสร้างข้อมูลว่าง

เครื่องพัฒนาพบ certificate verification error จึงยังไม่ได้ยืนยัน HTTP collection แบบ end-to-end ตัว parser ตรวจด้วย fixtures ส่วน corpus 120 วิชาใช้ rendered browser snapshots

## โครงสร้างโปรเจกต์

```text
src/thaimooc/
  api.py              FastAPI, หน้าเว็บ และรายงานดาวน์โหลด
  data.py             schema, JSONL, SQLite, quality
  search.py           TF-IDF และตัวกรองร่วม
  semantic.py         E5, chunking, index และ fingerprint
  comparison.py       paired ranking และเวลาค้นหา
  generation.py       optional Ollama และ citation validation
  evaluation.py       metrics สำหรับ judged queries ผ่าน CLI
  collector.py        HTTP collector และ HTML parser
  snapshot.py         rendered snapshot parser
  cli.py              import / quality / search / evaluate / collect
  web/                HTML, CSS, JavaScript ทั้ง 3 หน้า
data/catalog/         corpus 120 วิชาและวิธีคัดเลือก
data/seed/            fixtures จาก 3 วิชาจริง
evaluation/           คำถามและ labels ที่บันทึกไว้
reports/              ผลทดลองและข้อจำกัด
scripts/              เตรียมข้อมูล/โมเดล และรันการประเมิน
tests/                unit และ API regression tests
.github/workflows/    CI สำหรับ baseline และ tests โดยไม่ดาวน์โหลดโมเดล
```

## ก่อนนำขึ้น GitHub

เก็บ source, tests, README, `pyproject.toml`, ข้อมูล catalog/seed, evaluation และ reports เพื่อให้ผู้อื่นเริ่มใช้งานและตรวจผลได้ ส่วน `.venv/`, `models/`, `.env`, raw snapshots, SQLite, semantic vectors และ logs ถูกยกเว้นใน `.gitignore` แล้ว ตรวจรายการไฟล์อีกครั้งก่อน commit โดยเฉพาะเมื่อเพิ่มไฟล์ใหม่

ข้อมูลและเนื้อหารายวิชามาจาก Thai MOOC โดยมี URL รายแถว โปรเจกต์นี้ยังไม่ได้ประกาศ license สำหรับ source code และไม่ได้ให้สิทธิใหม่เหนือเนื้อหารายวิชาของผู้เผยแพร่ต้นทาง

งานต่อไป: เก็บเป้าหมายผู้ใช้จริง แยก development/test ตรวจ relevance โดยผู้ตรวจอิสระ และประเมินกรณีไม่มีวิชาที่ตรง ก่อนทดลอง hybrid หรือเพิ่ม LLM เพื่อปรับอันดับ
