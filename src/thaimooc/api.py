from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .data import read_courses, quality_report, ROOT
from .search import SearchEngine
from .generation import recommend
from .semantic import SemanticEngine
from .comparison import compare_engines
import logging
import json
from zipfile import BadZipFile


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    max_hours: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    level: str | None = None
    category: str | None = None


@asynccontextmanager
async def lifespan(app):
    courses = read_courses()
    app.state.engine = SearchEngine(courses)
    app.state.quality = quality_report(courses)
    app.state.semantic = None
    try:
        app.state.semantic = SemanticEngine.from_disk(courses)
    except (OSError, ValueError, ImportError, KeyError, TypeError, RuntimeError, BadZipFile, EOFError):
        logging.getLogger(__name__).warning('Semantic index unavailable; run scripts/prepare_semantic.py', exc_info=True)
    yield


app = FastAPI(title="Thai MOOC Course Advisor", version="0.1.0", lifespan=lifespan)
WEB = Path(__file__).parent / "web"
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


@app.get('/compare', include_in_schema=False)
def comparison_page():
    return FileResponse(WEB / 'compare.html', headers={'Cache-Control': 'no-cache'})


@app.get('/research', include_in_schema=False)
def research_page():
    return FileResponse(WEB / 'research.html', headers={'Cache-Control': 'no-cache'})


@app.get('/research/data', include_in_schema=False)
def research_summary():
    try:
        target = json.loads((ROOT / 'reports/known_target_benchmark_v1.json').read_text(encoding='utf-8'))
        pilot = json.loads((ROOT / 'reports/relevance_pilot_results.json').read_text(encoding='utf-8'))
        summary = {'corpus_count': target['corpus_count'], 'fingerprint': target['corpus_fingerprint'],
            'target': {'summary': target['summary'], 'run_at': target['run_at']},
            'pilot': {'queries': pilot['queries'], 'unique_pairs': pilot['unique_query_course_pairs'],
                      'summary': pilot['summary']}}
        if target['corpus_fingerprint'] != pilot['corpus_fingerprint'] or target['corpus_count'] != pilot['corpus_count']:
            raise ValueError('Saved reports refer to different corpora')
        return summary
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=503, detail='ยังโหลดรายงานผลการทดลองไม่ได้ กรุณาลองใหม่')


REPORT_DOWNLOADS = {
    'target-summary': 'retrieval_recommendation_v1.txt',
    'target-rankings': 'known_target_rankings_v1.csv',
    'pilot-summary': 'ai_relevance_pilot_summary.txt',
    'pilot-judgments': 'ai_relevance_judgments_99.csv',
    'pilot-details': 'relevance_pilot_results.json',
}


@app.get('/research/download/{report_name}', include_in_schema=False)
def download_research_report(report_name: str):
    filename = REPORT_DOWNLOADS.get(report_name)
    if filename is None:
        raise HTTPException(status_code=404, detail='ไม่พบรายงานนี้')
    path = ROOT / 'reports' / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail='ยังไม่มีไฟล์รายงานนี้')
    return FileResponse(path, filename=filename, headers={'Cache-Control': 'no-cache'})


@app.get("/catalog")
def catalog():
    courses = app.state.engine.courses
    return {"count": len(courses), "levels": sorted({c.level for c in courses if c.level}),
            "categories": sorted({c.category for c in courses if c.category})}


@app.get("/health")
def health():
    return {"status": "ok", "data_quality": app.state.quality, "retrieval": "char_tfidf", "llm": "optional_ollama",
            'semantic_available': app.state.semantic is not None}


@app.post('/compare')
def comparison(request: SearchRequest):
    if app.state.semantic is None:
        raise HTTPException(status_code=503, detail='ระบบค้นหาความหมายยังไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง')
    try:
        return compare_engines(app.state.engine, app.state.semantic, request.query, top_k=request.top_k,
                               max_hours=request.max_hours, level=request.level, category=request.category)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def retrieve(request):
    try:
        return app.state.engine.search(request.query, top_k=request.top_k, max_hours=request.max_hours,
                                       level=request.level, category=request.category)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/search")
def search(request: SearchRequest):
    results = retrieve(request)
    return {"query": request.query, "count": len(results), "results": results}


@app.post("/recommend")
async def recommendations(request: SearchRequest):
    results = retrieve(request)
    return await run_in_threadpool(recommend, request.query, results)
