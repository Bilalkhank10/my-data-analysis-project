from __future__ import annotations

import csv
import io
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

from ai_manager import AIJobManager
from generation_manager import GenerationManager
from job_manager import JobManager
from market_analyzer import MarketAnalyzer
from simple_ui import SIMPLE_HTML
from simple_workflow import SimpleWorkflowManager
from storage import Storage

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "exports"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

storage = Storage(DATA_DIR / "fiverr_phase1.db")
manager = JobManager(storage, OUTPUT_DIR)
ai_manager = AIJobManager(storage)
generation_manager = GenerationManager(storage)
simple_manager = SimpleWorkflowManager(
    storage, manager, ai_manager, generation_manager
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await simple_manager.shutdown()
    await generation_manager.shutdown()
    await ai_manager.shutdown()
    await manager.shutdown()


app = FastAPI(
    title="Fiverr Gig Growth System — Phase 4",
    version="5.0.0",
    description="Crawl, analytics, semantic audits and human-approved Fiverr gig generation.",
    lifespan=lifespan,
)


class FetchRequest(BaseModel):
    niche: str = Field(min_length=2, max_length=100)
    limit: int = Field(default=5, ge=1, le=500)

    @field_validator("niche")
    @classmethod
    def clean_niche(cls, value: str) -> str:
        value = " ".join(value.split()).strip()
        if len(value) < 2:
            raise ValueError("Niche kam az kam 2 characters ka hona chahiye.")
        return value


class AIRunRequest(BaseModel):
    mode: str = Field(default="dry_run", pattern="^(dry_run|test|standard|deep)$")
    max_gigs: int = Field(default=10, ge=1, le=100)
    own_gig_url: str | None = Field(default=None, max_length=500)


class GenerationRunRequest(BaseModel):
    mode: str = Field(default="dry_run", pattern="^(dry_run|test|standard|deep)$")
    target_gig_url: str | None = Field(default=None, max_length=500)
    target_buyer: str = Field(default="", max_length=200)
    positioning_goal: str = Field(default="", max_length=300)
    tone: str = Field(default="professional", max_length=80)
    output_language: str = Field(default="English", max_length=80)
    pricing_preference: str = Field(
        default="market_aligned",
        pattern="^(budget|market_aligned|premium)$",
    )


class ApprovalRequest(BaseModel):
    status: str = Field(pattern="^(draft|approved|rejected)$")


class SimpleWorkflowRequest(BaseModel):
    niche: str = Field(min_length=2, max_length=100)
    quality: str = Field(default="recommended", pattern="^(fast|recommended|best)$")
    buyer: str = Field(default="", max_length=200)
    language: str = Field(default="English", max_length=80)
    existing_url: str | None = Field(default=None, max_length=500)


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return SIMPLE_HTML


@app.get("/advanced", response_class=HTMLResponse)
async def advanced_dashboard() -> str:
    return INDEX_HTML


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "phase": 4,
        "llm_enabled": ai_manager.config.configured,
        "llm_provider": "openrouter",
        "generation_enabled": generation_manager.config.configured,
        "database": str(storage.path.name),
    }


@app.post("/api/simple-workflows", status_code=202)
async def create_simple_workflow(
    request: SimpleWorkflowRequest,
) -> dict[str, Any]:
    try:
        return simple_manager.start(
            niche=request.niche,
            quality=request.quality,
            buyer=request.buyer,
            language=request.language,
            existing_url=request.existing_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/simple-workflows/{workflow_id}")
async def get_simple_workflow(workflow_id: str) -> dict[str, Any]:
    workflow = simple_manager.get(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@app.get("/api/simple-workflows/{workflow_id}/result")
async def get_simple_workflow_result(workflow_id: str) -> dict[str, Any]:
    workflow = simple_manager.get(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow["status"] != "completed":
        raise HTTPException(status_code=409, detail="Workflow is not complete")
    result = simple_manager.result(workflow_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Generated result not found")
    return result


@app.post("/api/jobs", status_code=202)
async def create_job(request: FetchRequest) -> dict[str, Any]:
    return manager.start_job(request.niche, request.limit)


# Backwards-compatible route. It now starts a background job instead of holding
# one HTTP connection open for a potentially long 500-gig crawl.
@app.post("/api/fetch", status_code=202)
async def fetch_niche(request: FetchRequest) -> dict[str, Any]:
    return manager.start_job(request.niche, request.limit)


@app.get("/api/jobs")
async def list_jobs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    jobs = manager.list_jobs(limit)
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs/{job_id}/results")
async def get_job_results(
    job_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    results, total = storage.get_job_results(job_id, offset=offset, limit=limit)
    return {
        "job_id": job_id,
        "status": job["status"],
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": offset + len(results) < total,
        "results": results,
    }


@app.get("/api/jobs/{job_id}/analysis")
async def get_job_analysis(job_id: str) -> dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] in {"queued", "running", "cancelling"}:
        raise HTTPException(status_code=409, detail="Analysis will be available when the crawl finishes")
    analysis = manager.analyze_job(job_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not available")
    return analysis


@app.post("/api/jobs/{job_id}/analysis/rebuild")
async def rebuild_job_analysis(job_id: str) -> dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] in {"queued", "running", "cancelling"}:
        raise HTTPException(status_code=409, detail="Wait for the crawl to finish")
    analysis = manager.analyze_job(job_id, force=True)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not available")
    return analysis


@app.get("/api/jobs/{job_id}/analysis/{section}.csv")
async def export_analysis_section(job_id: str, section: str) -> StreamingResponse:
    allowed = {
        "overview", "rankings", "movement", "keywords", "clusters",
        "pricing", "packages", "competitors", "reviews", "gaps",
    }
    if section not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported analysis section")
    analysis = manager.analyze_job(job_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not available")
    rows = MarketAnalyzer.export_rows(analysis, section)
    output = io.StringIO()
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["message"]
        rows = [{"message": "No rows available for this section"}]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        clean = {
            key: json.dumps(value, ensure_ascii=False)
            if isinstance(value, (dict, list)) else value
            for key, value in row.items()
        }
        writer.writerow(clean)
    filename = f"{job_id}-{section}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/ai/config")
async def ai_config() -> dict[str, Any]:
    return ai_manager.public_config()


@app.post("/api/ai/validate-key")
async def validate_ai_key() -> dict[str, Any]:
    if not ai_manager.config.configured:
        raise HTTPException(
            status_code=409,
            detail="OPENROUTER_API_KEY is not configured. Use a newly rotated environment secret.",
        )
    try:
        return await ai_manager.validate_key()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/ai-runs", status_code=202)
async def start_ai_run(job_id: str, request: AIRunRequest) -> dict[str, Any]:
    try:
        return ai_manager.start_run(
            job_id,
            mode=request.mode,
            max_gigs=request.max_gigs,
            own_gig_url=request.own_gig_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}/ai-runs")
async def list_ai_runs(
    job_id: str, limit: int = Query(default=20, ge=1, le=100)
) -> dict[str, Any]:
    if manager.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    runs = ai_manager.list_runs(job_id, limit)
    return {"runs": runs, "count": len(runs)}


@app.get("/api/ai-runs/{run_id}")
async def get_ai_run(run_id: str) -> dict[str, Any]:
    run = ai_manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="AI run not found")
    return run


@app.get("/api/ai-runs/{run_id}/result")
async def get_ai_result(run_id: str) -> dict[str, Any]:
    run = ai_manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="AI run not found")
    if run["status"] != "completed":
        raise HTTPException(status_code=409, detail="AI run is not complete")
    result = ai_manager.get_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="AI result not available")
    return result


@app.get("/api/generation/config")
async def generation_config() -> dict[str, Any]:
    return generation_manager.public_config()


@app.post("/api/jobs/{job_id}/generation-runs", status_code=202)
async def start_generation_run(
    job_id: str, request: GenerationRunRequest
) -> dict[str, Any]:
    preferences = {
        "target_buyer": request.target_buyer.strip(),
        "positioning_goal": request.positioning_goal.strip(),
        "tone": request.tone.strip(),
        "output_language": request.output_language.strip(),
        "pricing_preference": request.pricing_preference,
    }
    try:
        return generation_manager.start_run(
            job_id,
            mode=request.mode,
            target_gig_url=request.target_gig_url,
            preferences=preferences,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}/generation-runs")
async def list_generation_runs(
    job_id: str, limit: int = Query(default=20, ge=1, le=100)
) -> dict[str, Any]:
    if manager.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    runs = generation_manager.list_runs(job_id, limit)
    return {"runs": runs, "count": len(runs)}


@app.get("/api/generation-runs/{run_id}")
async def get_generation_run(run_id: str) -> dict[str, Any]:
    run = generation_manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Generation run not found")
    return run


@app.get("/api/generation-runs/{run_id}/result")
async def get_generation_result(run_id: str) -> dict[str, Any]:
    run = generation_manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Generation run not found")
    if run["status"] != "completed":
        raise HTTPException(status_code=409, detail="Generation run is not complete")
    result = generation_manager.get_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Generated draft not available")
    return result


@app.get("/api/generation-runs/{run_id}/export.md")
async def export_generation_markdown(run_id: str) -> StreamingResponse:
    content = generation_manager.markdown(run_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Generated draft not available")
    return StreamingResponse(
        iter([content]),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{run_id}-gig-draft.md"'
        },
    )


@app.post("/api/generation-runs/{run_id}/approval")
async def approve_generation(
    run_id: str, request: ApprovalRequest
) -> dict[str, Any]:
    try:
        run = generation_manager.set_approval(run_id, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="Generation run not found")
    return run


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    job = manager.cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/download/{filename}")
async def download(filename: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.(json|csv)", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = OUTPUT_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Export not found")
    media_type = "application/json" if path.suffix == ".json" else "text/csv"
    return FileResponse(path, filename=filename, media_type=media_type)


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fiverr Gig Growth System — Phase 4</title>
  <style>
    :root{--bg:#07120e;--panel:#0f2018;--panel2:#14281f;--line:#29483a;--text:#f3fbf6;--muted:#a5bdb1;--green:#1dbf73;--green2:#75ecb2;--danger:#ff7979;--warn:#ffd37a;--blue:#7cb7ff}
    *{box-sizing:border-box} body{margin:0;min-height:100vh;color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;background:radial-gradient(circle at 12% 4%,rgba(29,191,115,.16),transparent 30rem),radial-gradient(circle at 92% 24%,rgba(124,183,255,.08),transparent 25rem),var(--bg)}
    .wrap{width:min(1180px,calc(100% - 32px));margin:auto;padding:50px 0 80px}.eyebrow{color:var(--green2);font-size:12px;font-weight:900;letter-spacing:.15em;text-transform:uppercase}h1{margin:9px 0 12px;max-width:900px;font-size:clamp(36px,6vw,68px);line-height:1;letter-spacing:-.05em}.lead{max-width:780px;color:var(--muted);font-size:18px;line-height:1.6}
    .search-card{margin-top:30px;padding:20px;display:grid;grid-template-columns:1fr 150px auto;gap:12px;border:1px solid var(--line);background:rgba(15,32,24,.9);border-radius:18px;box-shadow:0 22px 65px rgba(0,0,0,.3)}label{display:block;margin:0 0 8px 2px;color:var(--muted);font-size:12px;font-weight:850;letter-spacing:.08em;text-transform:uppercase}input,select,button,a.button{font:inherit}input,select{width:100%;height:50px;padding:0 15px;color:var(--text);background:#081710;border:1px solid var(--line);border-radius:12px;outline:none}input:focus,select:focus{border-color:var(--green);box-shadow:0 0 0 3px rgba(29,191,115,.12)}
    button,a.button{height:50px;align-self:end;display:inline-flex;align-items:center;justify-content:center;padding:0 21px;border:0;border-radius:12px;color:#03130a;background:var(--green);font-weight:900;text-decoration:none;cursor:pointer}button:hover,a.button:hover{background:var(--green2)}button:disabled{opacity:.55;cursor:not-allowed}.secondary{color:var(--text)!important;background:var(--panel2)!important;border:1px solid var(--line)!important}.danger{color:#fff!important;background:#672c32!important;border:1px solid #a94952!important}.fine{margin:12px 3px 0;color:#7f9a8d;font-size:13px;line-height:1.55}
    .job-panel{display:none;margin-top:24px;padding:20px;border:1px solid var(--line);border-radius:17px;background:var(--panel)}.job-panel.show{display:block}.job-top{display:flex;justify-content:space-between;align-items:flex-start;gap:15px}.job-top h2{margin:0 0 5px;font-size:21px}.job-id{color:#7f9a8d;font:12px ui-monospace,monospace;overflow-wrap:anywhere}.stage{display:inline-flex;margin-top:8px;padding:5px 9px;border-radius:999px;color:var(--green2);background:#092017;border:1px solid #295440;font-size:12px;font-weight:800;text-transform:capitalize}.progress-track{height:12px;margin:18px 0 10px;overflow:hidden;border:1px solid #2b4b3d;border-radius:999px;background:#07120e}.progress-bar{height:100%;width:0;background:linear-gradient(90deg,var(--green),var(--green2));transition:width .35s ease}.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:9px}.metric{padding:11px;background:#091710;border:1px solid #233d32;border-radius:11px}.metric small{display:block;color:#82998e;font-size:11px;text-transform:uppercase}.metric strong{display:block;margin-top:3px;font-size:18px}.job-message{margin:12px 0 0;color:var(--muted);font-size:13px}.warning{margin:10px 0;padding:11px 13px;border:1px solid rgba(255,211,122,.35);border-radius:10px;color:var(--warn);background:rgba(255,211,122,.06);font-size:13px}.error{color:var(--danger)!important}
    .summary{display:none;margin:28px 0 15px;align-items:center;justify-content:space-between;gap:14px}.summary.show{display:flex}.summary h2{margin:0;font-size:25px}.summary p{margin:4px 0 0;color:var(--muted)}.downloads,.pager{display:flex;gap:8px;flex-wrap:wrap}.downloads a.button,.pager button{height:39px;padding:0 14px;color:var(--text);background:var(--panel2);border:1px solid var(--line);font-size:13px}.pager-wrap{display:none;margin:12px 0 18px;align-items:center;justify-content:space-between;gap:12px;color:var(--muted);font-size:13px}.pager-wrap.show{display:flex}
    .results{display:grid;gap:14px}.gig{overflow:hidden;border:1px solid var(--line);border-radius:17px;background:rgba(15,32,24,.92)}.gig-main{padding:19px;display:grid;grid-template-columns:1fr auto;gap:18px}.gig h3{margin:0 0 9px;font-size:19px;line-height:1.35}.gig h3 a{color:var(--text);text-decoration:none}.gig h3 a:hover{color:var(--green2)}.meta{display:flex;gap:7px;flex-wrap:wrap}.chip{padding:6px 9px;color:var(--muted);background:#081710;border:1px solid var(--line);border-radius:999px;font-size:12px}.chip.rank{color:#05140c;background:var(--green2);border-color:var(--green2);font-weight:900}.chip.ad{color:#1b1100;background:var(--warn);border-color:var(--warn);font-weight:900}.price{min-width:110px;text-align:right}.price small{display:block;color:var(--muted)}.price strong{font-size:24px;color:var(--green2)}details{border-top:1px solid var(--line)}summary{padding:14px 20px;color:var(--muted);font-weight:750;cursor:pointer}.detail-body{padding:4px 20px 20px;display:grid;gap:12px}.data-box{overflow:hidden;border:1px solid #28483a;border-radius:13px;background:#08130e}.data-head{min-height:45px;padding:8px 10px 8px 14px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #1e352b;background:#102119}.data-head h4{margin:0;color:var(--green2);font-size:14px}button.copy-btn{width:auto;min-width:72px;height:30px;align-self:auto;padding:0 10px;color:var(--text);background:#183025;border:1px solid #365c4b;border-radius:8px;font-size:12px}button.copy-btn:hover,button.copy-btn.copied{color:#03130a;background:var(--green2)}pre{margin:0;max-height:360px;overflow:auto;padding:14px;white-space:pre-wrap;overflow-wrap:anywhere;color:#d9e9e0;background:#08130e;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
    .analysis-panel{display:none;margin:24px 0;border:1px solid var(--line);border-radius:18px;background:rgba(15,32,24,.94);overflow:hidden}.analysis-panel.show{display:block}.analysis-head{padding:18px 20px;display:flex;align-items:flex-start;justify-content:space-between;gap:15px;border-bottom:1px solid var(--line)}.analysis-head h2{margin:0 0 5px;font-size:23px}.analysis-head p{margin:0;color:var(--muted);font-size:13px}.tabs{display:flex;gap:7px;padding:12px 14px;overflow-x:auto;border-bottom:1px solid var(--line);background:#0a1912}.tabs button{height:35px;min-width:max-content;padding:0 12px;align-self:auto;color:var(--muted);background:#102219;border:1px solid #29483a;border-radius:9px;font-size:12px}.tabs button.active{color:#03130a;background:var(--green2);border-color:var(--green2)}.analysis-content{padding:18px;display:grid;gap:16px}.analytics-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.analytics-card{padding:14px;border:1px solid #29483a;border-radius:12px;background:#081710}.analytics-card small{display:block;color:#82998e;font-size:11px;text-transform:uppercase}.analytics-card strong{display:block;margin-top:5px;color:var(--green2);font-size:22px}.analytics-card span{display:block;margin-top:3px;color:var(--muted);font-size:12px}.panel-block{padding:14px;border:1px solid #29483a;border-radius:13px;background:#091710}.panel-block h3{margin:0 0 11px;font-size:16px}.table-wrap{overflow:auto;max-height:560px;border:1px solid #29483a;border-radius:11px}.analysis-table{width:100%;border-collapse:collapse;min-width:760px;font-size:12px}.analysis-table th{position:sticky;top:0;z-index:1;padding:10px;text-align:left;color:var(--green2);background:#102219;border-bottom:1px solid #355a49;cursor:pointer;white-space:nowrap}.analysis-table td{padding:9px 10px;color:#d8e8df;border-bottom:1px solid #1d342a;vertical-align:top}.analysis-table tr:hover td{background:#0d2017}.bar-list{display:grid;gap:8px}.bar-row{display:grid;grid-template-columns:minmax(110px,220px) 1fr 55px;gap:9px;align-items:center;font-size:12px}.bar-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}.bar-track{height:9px;overflow:hidden;border-radius:99px;background:#07120e;border:1px solid #29483a}.bar-fill{height:100%;background:linear-gradient(90deg,var(--green),var(--blue));border-radius:99px}.bar-value{text-align:right;color:var(--text)}.analysis-note{padding:12px;border-left:3px solid var(--blue);color:var(--muted);background:rgba(124,183,255,.06);font-size:13px;line-height:1.55}.filter-row{display:flex;gap:9px;flex-wrap:wrap}.filter-row input,.filter-row select{width:auto;min-width:150px;height:40px}.empty{padding:24px;text-align:center;color:var(--muted)}
    .ai-panel{display:none;margin:24px 0;border:1px solid #3b4e69;border-radius:18px;background:linear-gradient(145deg,rgba(13,28,27,.97),rgba(14,24,39,.97));overflow:hidden}.ai-panel.show{display:block}.ai-head{padding:18px 20px;display:flex;justify-content:space-between;align-items:flex-start;gap:15px;border-bottom:1px solid #31465c}.ai-head h2{margin:0 0 5px}.ai-head p{margin:0;color:var(--muted);font-size:13px}.ai-state{padding:6px 10px;border:1px solid #3e5c78;border-radius:999px;color:var(--blue);font-size:12px;font-weight:800}.ai-controls{padding:16px 20px;display:grid;grid-template-columns:150px 130px 1fr auto;gap:10px;align-items:end;border-bottom:1px solid #31465c}.ai-controls input,.ai-controls select{height:43px}.ai-controls button{height:43px}.ai-progress{display:none;padding:15px 20px;border-bottom:1px solid #31465c}.ai-progress.show{display:block}.ai-results{display:none}.ai-results.show{display:block}.score-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.score-card{padding:12px;border:1px solid #35506a;border-radius:11px;background:#0a1822}.score-card small{display:block;color:#8da6bc;font-size:11px}.score-card strong{display:block;margin-top:4px;color:var(--blue);font-size:22px}.model-list{display:grid;gap:7px}.model-row{padding:10px;border:1px solid #31465c;border-radius:9px;color:var(--muted);font:12px ui-monospace,monospace}.security-note{padding:12px 20px;color:#a9bfd2;background:rgba(124,183,255,.06);font-size:12px;line-height:1.55}
    .builder-panel{display:none;margin:24px 0;border:1px solid #66513c;border-radius:18px;background:linear-gradient(145deg,rgba(28,24,16,.97),rgba(29,20,31,.97));overflow:hidden}.builder-panel.show{display:block}.builder-head{padding:18px 20px;display:flex;align-items:flex-start;justify-content:space-between;gap:15px;border-bottom:1px solid #5b4637}.builder-head h2{margin:0 0 5px}.builder-head p{margin:0;color:var(--muted);font-size:13px}.builder-controls{padding:16px 20px;display:grid;grid-template-columns:140px 1fr 1fr;gap:10px;border-bottom:1px solid #5b4637}.builder-controls input,.builder-controls select{height:42px}.builder-actions{padding:0 20px 16px;display:flex;gap:9px;flex-wrap:wrap}.builder-actions button,.builder-actions a{height:42px}.draft-text{padding:14px;border:1px solid #5b4637;border-radius:10px;background:#120f0d;color:#eee0d4;white-space:pre-wrap;line-height:1.55}.approval{display:flex;gap:8px;align-items:center}.approval span{color:var(--warn);font-size:12px;font-weight:800}
    footer{margin-top:42px;color:#6e887b;font-size:13px;line-height:1.6}@media(max-width:800px){.search-card{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.analytics-grid,.score-grid{grid-template-columns:repeat(2,1fr)}.ai-controls,.builder-controls{grid-template-columns:1fr}.job-top,.summary,.gig-main,.pager-wrap,.analysis-head,.ai-head,.builder-head{align-items:flex-start;flex-direction:column;display:flex}.summary,.pager-wrap{display:none}.summary.show,.pager-wrap.show{display:flex}.price{text-align:left}}
    /* Premium minimal workspace */
    :root{--bg:#0b0c0e;--panel:#121316;--panel2:#17191d;--line:#27292e;--text:#f4f2ec;--muted:#97989e;--green:#31d889;--green2:#78e8b2;--danger:#ff7878;--warn:#d8b46c;--blue:#8ebcff}
    body{background:radial-gradient(circle at 50% -220px,rgba(49,216,137,.12),transparent 440px),var(--bg);letter-spacing:-.005em}
    .wrap{width:min(1240px,calc(100% - 40px));padding:22px 0 76px}.topbar{height:58px;display:flex;align-items:center;justify-content:space-between;margin-bottom:68px;border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:11px}.brand-mark{width:30px;height:30px;display:grid;place-items:center;border-radius:8px;background:var(--text);color:#0b0c0e;font-size:11px;font-weight:950;letter-spacing:.02em}.brand strong{display:block;font-size:13px}.brand small{display:block;margin-top:1px;color:#777a80;font-size:10px}.topbar-meta{display:flex;align-items:center;gap:7px;color:#85878d;font-size:11px}.privacy-dot{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 0 4px rgba(49,216,137,.09)}
    .eyebrow{font-size:11px;color:#7d827f;letter-spacing:.13em}.wrap>h1{max-width:760px;margin:12px 0 14px;font-size:clamp(38px,5vw,62px);font-weight:720;letter-spacing:-.055em}.lead{max-width:720px;color:#a5a6aa;font-size:17px;line-height:1.65}
    .search-card{margin-top:30px;padding:10px;grid-template-columns:1fr 145px 210px;gap:8px;background:#111216;border:1px solid #292b30;border-radius:14px;box-shadow:0 18px 60px rgba(0,0,0,.22)}.search-card>div{padding:2px 3px}.search-card label{margin:0 0 5px 2px;font-size:9px;color:#74767c}.search-card input,.search-card select{height:43px;border:0;background:#191b1f;border-radius:9px;box-shadow:none}.search-card button{height:43px;border-radius:9px}.fine{max-width:790px;margin-top:10px;color:#6f7278;font-size:11px}
    button,a.button{border-radius:9px;box-shadow:none;transition:transform .15s ease,background .15s ease,border-color .15s ease}button:hover,a.button:hover{transform:translateY(-1px)}
    .workspace-nav{position:sticky;top:10px;z-index:20;margin:34px 0 22px;padding:5px;display:flex;gap:4px;overflow-x:auto;border:1px solid rgba(255,255,255,.07);border-radius:12px;background:rgba(17,18,21,.88);backdrop-filter:blur(18px);box-shadow:0 12px 32px rgba(0,0,0,.2)}.workspace-nav button{height:38px;min-width:max-content;align-self:auto;padding:0 14px;gap:8px;color:#888a90;background:transparent;border:0;border-radius:8px;font-size:11px;font-weight:750}.workspace-nav button span{color:#585b61;font:9px ui-monospace,monospace}.workspace-nav button.active{color:#0a0b0c;background:#f1efe9}.workspace-nav button.active span{color:#4d504f}.workspace-nav button:disabled{opacity:.28;cursor:not-allowed}.workspace-hidden{display:none!important}
    .job-panel,.analysis-panel,.ai-panel,.builder-panel,.gig{border-color:var(--line);background:#111216;box-shadow:0 16px 48px rgba(0,0,0,.16)}.job-panel{padding:18px}.job-top h2,.analysis-head h2,.ai-head h2,.builder-head h2{font-weight:650;letter-spacing:-.025em}.stage,.ai-state{border-color:#2d4238;background:#121c17;color:var(--green2)}.progress-track{height:6px;border:0;background:#202227}.progress-bar{background:linear-gradient(90deg,var(--green),#a8efcb)}.metrics{gap:7px}.metric{padding:10px;border-color:#25272c;background:#15171a}.metric small{font-size:9px}.metric strong{font-size:16px;font-weight:650}
    .summary{padding:4px 2px}.summary h2{font-weight:650}.analysis-panel,.ai-panel,.builder-panel{border-radius:14px}.analysis-head,.ai-head,.builder-head{padding:17px 18px;border-color:var(--line)}.analysis-content{padding:14px}.tabs{padding:7px;background:#0f1012;border-color:var(--line)}.tabs button{height:32px;padding:0 11px;border-color:transparent;background:transparent;color:#777980}.tabs button.active{color:#eeeae1;background:#202226;border-color:#2b2d32}.analytics-grid,.score-grid{gap:7px}.analytics-card,.score-card{padding:12px;border-color:#25272c;background:#15171a}.analytics-card strong,.score-card strong{color:var(--text);font-size:19px;font-weight:650}.panel-block{padding:12px;border-color:#25272c;background:#131518}.table-wrap{border-color:#282a30}.analysis-table th{padding:9px;background:#1a1c20;color:#b7b8ba;border-color:#303239;font-size:10px;text-transform:uppercase;letter-spacing:.04em}.analysis-table td{padding:9px;color:#c5c6c8;border-color:#22242a}.analysis-table tr:hover td{background:#17191d}.analysis-note,.security-note{border-left-color:#62666d;background:#17191d;color:#9b9da2}.bar-track{border:0;background:#24262b}.bar-fill{background:var(--green)}
    .ai-panel,.builder-panel{background:#111216;border-color:var(--line)}.ai-controls,.builder-controls{border-color:var(--line)}.builder-head,.builder-controls{border-color:var(--line)}.builder-actions{padding-top:2px}.data-box{border-color:#26282d;background:#121316}.data-head{background:#17191d;border-color:#26282d}.data-head h4{color:#c6c7c9}.data-box pre{background:#101113;color:#c8cacb}.gig{border-radius:13px}.gig-main{padding:16px}.chip{padding:5px 8px;border-color:#292b31;background:#16181b;color:#92949a}.chip.rank{background:var(--text);border-color:var(--text);color:#111216}.chip.ad{background:#d7b36d;border-color:#d7b36d}.price strong{font-size:20px}.raw-header{margin:28px 2px 12px;display:flex;align-items:flex-end;justify-content:space-between}.raw-header h2{margin:4px 0 0;font-size:24px}.raw-header p{margin:0;color:var(--muted);font-size:12px}.section-kicker{color:#6f7278;font-size:9px;text-transform:uppercase;letter-spacing:.12em}
    footer{padding-top:24px;border-top:1px solid var(--line);font-size:11px}
    @media(max-width:800px){.wrap{width:min(100% - 22px,1240px);padding-top:10px}.topbar{margin-bottom:42px}.topbar-meta{display:none}.search-card{grid-template-columns:1fr}.workspace-nav{top:5px}.workspace-nav button{padding:0 10px}.raw-header{align-items:flex-start;flex-direction:column;gap:5px}}
  </style>
</head>
<body data-workspace="crawl"><main class="wrap">
  <header class="topbar"><div class="brand"><span class="brand-mark">FG</span><div><strong>Fiverr Growth OS</strong><small>Local market intelligence</small></div></div><div class="topbar-meta"><span class="privacy-dot"></span>Private workspace</div></header>
  <div class="eyebrow">Phase 4 · Research-to-action gig builder</div>
  <h1>Fiverr Gig Growth System</h1>
  <p class="lead">Public market crawl, deterministic analytics, optional semantic audit aur evidence-led gig draft generation—human approval, compliance validation aur strict OpenRouter cost controls ke saath.</p>
  <form id="form" class="search-card workspace-crawl">
    <div><label for="niche">Niche / keyword</label><input id="niche" value="Looker Studio" minlength="2" maxlength="100" required></div>
    <div><label for="limit">Maximum gigs</label><select id="limit"><option>3</option><option selected>5</option><option>10</option><option>25</option><option>50</option><option>100</option><option>250</option><option>500</option></select></div>
    <button id="submit" type="submit">Start background job</button>
  </form>
  <p class="fine workspace-crawl">Phase 3/4 AI sirf explicit button par chalega; dono ka default dry-run hai aur zero tokens consume karta hai. Generated gigs drafts hain—automatic Fiverr publishing nahi hoti. API key environment-only hai.</p>

  <nav id="workspaceNav" class="workspace-nav" aria-label="Workspace modules">
    <button type="button" data-workspace="crawl" class="active"><span>01</span>Crawl</button>
    <button type="button" data-workspace="intelligence" disabled><span>02</span>Intelligence</button>
    <button type="button" data-workspace="ai" disabled><span>03</span>AI Audit</button>
    <button type="button" data-workspace="builder" disabled><span>04</span>Gig Builder</button>
    <button type="button" data-workspace="raw" disabled><span>05</span>Raw Data</button>
  </nav>

  <section id="jobPanel" class="job-panel workspace-crawl">
    <div class="job-top"><div><h2 id="jobTitle">Crawl job</h2><div id="jobId" class="job-id"></div><span id="stage" class="stage">queued</span></div><button id="cancel" class="danger" type="button">Cancel job</button></div>
    <div class="progress-track"><div id="progressBar" class="progress-bar"></div></div>
    <div class="metrics">
      <div class="metric"><small>Progress</small><strong id="mProgress">0%</strong></div>
      <div class="metric"><small>Pages</small><strong id="mPages">0</strong></div>
      <div class="metric"><small>Discovered</small><strong id="mDiscovered">0</strong></div>
      <div class="metric"><small>Processed</small><strong id="mProcessed">0</strong></div>
      <div class="metric"><small>Success</small><strong id="mSuccess">0</strong></div>
      <div class="metric"><small>Failed</small><strong id="mFailed">0</strong></div>
    </div>
    <p id="jobMessage" class="job-message"></p><div id="warnings"></div>
  </section>

  <section id="summary" class="summary workspace-crawl"><div><h2 id="summaryTitle">Results</h2><p id="summaryMeta"></p></div><div id="downloads" class="downloads"></div></section>

  <section id="analysisPanel" class="analysis-panel workspace-intelligence">
    <div class="analysis-head"><div><h2>Phase 2 Market Intelligence</h2><p id="analysisMeta">Deterministic analytics · No LLM</p></div><a id="analysisCsv" class="button secondary" href="#">Download tab CSV</a></div>
    <div id="analysisTabs" class="tabs">
      <button type="button" data-tab="overview" class="active">Overview</button>
      <button type="button" data-tab="rankings">Rankings</button>
      <button type="button" data-tab="movement">Movement</button>
      <button type="button" data-tab="keywords">Keywords</button>
      <button type="button" data-tab="clusters">Clusters</button>
      <button type="button" data-tab="pricing">Pricing</button>
      <button type="button" data-tab="packages">Packages</button>
      <button type="button" data-tab="competitors">Competitors</button>
      <button type="button" data-tab="reviews">Reviews</button>
      <button type="button" data-tab="gaps">Market Gaps</button>
    </div>
    <div id="analysisContent" class="analysis-content"></div>
  </section>

  <section id="aiPanel" class="ai-panel workspace-ai">
    <div class="ai-head"><div><h2>Phase 3 Semantic Audit</h2><p>OpenRouter · structured JSON · evidence-first · cached</p></div><span id="aiKeyState" class="ai-state">Checking configuration…</span></div>
    <div class="ai-controls">
      <div><label for="aiMode">Mode</label><select id="aiMode"><option value="dry_run" selected>Dry run — $0</option><option value="test">Tiny live test</option><option value="standard">Standard audit</option><option value="deep">Deep audit</option></select></div>
      <div><label for="aiMaxGigs">Max gigs</label><select id="aiMaxGigs"><option>1</option><option>5</option><option selected>10</option><option>15</option><option>25</option></select></div>
      <div><label for="ownGigUrl">Your gig URL — optional</label><input id="ownGigUrl" placeholder="https://www.fiverr.com/user/your-gig"></div>
      <button id="runAi" type="button">Run Phase 3</button>
    </div>
    <div class="security-note">Dry run is recommended first and consumes zero tokens. Real modes require a newly rotated <code>OPENROUTER_API_KEY</code> environment secret. The key is never persisted or returned.</div>
    <div id="aiProgress" class="ai-progress"><div class="progress-track"><div id="aiProgressBar" class="progress-bar"></div></div><p id="aiProgressText" class="job-message"></p></div>
    <div id="aiResults" class="ai-results">
      <div id="aiTabs" class="tabs"><button type="button" data-ai-tab="ai_overview" class="active">AI Overview</button><button type="button" data-ai-tab="intents">Intent Map</button><button type="button" data-ai-tab="scores">Scores</button><button type="button" data-ai-tab="similarity">Similarity</button><button type="button" data-ai-tab="synthesis">Market Synthesis</button><button type="button" data-ai-tab="evidence">Evidence</button><button type="button" data-ai-tab="usage">Usage & Cost</button></div>
      <div id="aiContent" class="analysis-content"></div>
    </div>
  </section>

  <section id="builderPanel" class="builder-panel workspace-builder">
    <div class="builder-head"><div><h2>Phase 4 Gig Builder</h2><p>Evidence-led draft · human approval required · no auto-publish</p></div><div class="approval"><span id="builderStatus">Dry run available</span><button id="approveDraft" class="secondary" type="button" style="display:none">Approve draft</button></div></div>
    <div class="builder-controls">
      <div><label for="builderMode">Mode</label><select id="builderMode"><option value="dry_run" selected>Dry run — $0</option><option value="test">Tiny live draft</option><option value="standard">Standard draft</option><option value="deep">Deep refine</option></select></div>
      <div><label for="builderTargetUrl">Existing gig URL — optional</label><input id="builderTargetUrl" placeholder="https://www.fiverr.com/user/gig"></div>
      <div><label for="builderBuyer">Target buyer</label><input id="builderBuyer" placeholder="e.g. ecommerce marketing teams"></div>
      <div><label for="builderPositioning">Positioning goal</label><input id="builderPositioning" placeholder="e.g. premium GA4 + dashboard specialist"></div>
      <div><label for="builderTone">Tone</label><select id="builderTone"><option>professional</option><option>consultative</option><option>technical</option><option>friendly</option><option>premium</option></select></div>
      <div><label for="builderPricing">Pricing</label><select id="builderPricing"><option value="market_aligned">Market aligned</option><option value="budget">Budget entry</option><option value="premium">Premium</option></select></div>
    </div>
    <div class="builder-actions"><button id="runBuilder" type="button">Build Phase 4 draft</button><a id="downloadDraft" class="button secondary" href="#" style="display:none">Download Markdown</a></div>
    <div class="security-note">Start with dry run. Real generation requires a newly rotated environment key. Generated assets remain drafts and are never posted to Fiverr automatically.</div>
    <div id="builderProgress" class="ai-progress"><div class="progress-track"><div id="builderProgressBar" class="progress-bar"></div></div><p id="builderProgressText" class="job-message"></p></div>
    <div id="builderResults" class="ai-results"><div id="builderTabs" class="tabs"><button type="button" data-builder-tab="draft" class="active">Final Gig</button><button type="button" data-builder-tab="packages">Packages</button><button type="button" data-builder-tab="faq">FAQ & Requirements</button><button type="button" data-builder-tab="visuals">Visuals & Video</button><button type="button" data-builder-tab="compliance">Compliance</button><button type="button" data-builder-tab="evidence">Evidence</button><button type="button" data-builder-tab="comparison">Before/After</button><button type="button" data-builder-tab="builder_usage">Usage</button></div><div id="builderContent" class="analysis-content"></div></div>
  </section>

  <div class="raw-header workspace-raw"><div><span class="section-kicker">Source records</span><h2>Raw gig data</h2></div><p>Every extracted section, preserved for inspection and export.</p></div>
  <div id="pagerWrap" class="pager-wrap workspace-raw"><span id="pagerInfo"></span><div class="pager"><button id="prev" class="secondary" type="button">Previous</button><button id="next" class="secondary" type="button">Next</button></div></div>
  <section id="results" class="results workspace-raw"></section>
  <footer>Phase 4 outputs are evidence-led drafts requiring human review. The system never auto-publishes, copies competitor text, requests fake reviews, or claims access to Fiverr private metrics/secret ranking weights. Always use a rotated limited-credit key and start with dry run.</footer>
</main>
<script>
const $=id=>document.getElementById(id); const PAGE_SIZE=20;
let currentJobId=null,pollTimer=null,currentOffset=0,currentTotal=0,analysisData=null,activeAnalysisTab='overview',aiConfig=null,currentAiRunId=null,aiPollTimer=null,aiResult=null,activeAiTab='ai_overview',builderConfig=null,currentBuilderRunId=null,builderPollTimer=null,builderResult=null,activeBuilderTab='draft';
const workspaceNames=['crawl','intelligence','ai','builder','raw'];
function switchWorkspace(name,scroll=true){if(!workspaceNames.includes(name))name='crawl';document.body.dataset.workspace=name;for(const item of workspaceNames){document.querySelectorAll('.workspace-'+item).forEach(node=>node.classList.toggle('workspace-hidden',item!==name))}document.querySelectorAll('#workspaceNav button').forEach(button=>button.classList.toggle('active',button.dataset.workspace===name));if(scroll)window.scrollTo({top:Math.max(0,$('workspaceNav').offsetTop-12),behavior:'smooth'})}
function enableResearchWorkspaces(enabled=true){document.querySelectorAll('#workspaceNav button').forEach(button=>{if(button.dataset.workspace!=='crawl')button.disabled=!enabled})}
document.querySelectorAll('#workspaceNav button').forEach(button=>button.onclick=()=>{if(!button.disabled)switchWorkspace(button.dataset.workspace)});
switchWorkspace('crawl',false);
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined&&text!==null)n.textContent=text;return n}
function chip(text,extra=''){return el('span','chip '+extra,text)}
function detailMessage(d,fallback='Request failed'){const x=d&&d.detail;if(!x)return fallback;if(typeof x==='string')return x;if(Array.isArray(x))return x.map(i=>i.msg||i.message||JSON.stringify(i)).join('; ');return x.message||x.msg||JSON.stringify(x)}
async function api(url,options={}){const r=await fetch(url,options);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(detailMessage(d,'Request failed'));return d}
async function copyText(text,button){try{if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(text);else{const a=document.createElement('textarea');a.value=text;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}button.textContent='Copied ✓';button.classList.add('copied');setTimeout(()=>{button.textContent='Copy';button.classList.remove('copied')},1300)}catch{button.textContent='Select text';setTimeout(()=>button.textContent='Copy',1500)}}
function section(parent,title,value){if(value===undefined||value===null||value===''||(Array.isArray(value)&&!value.length))return;const text=typeof value==='string'?value:JSON.stringify(value,null,2);const box=el('section','data-box');const head=el('div','data-head');head.appendChild(el('h4','',title));const b=el('button','copy-btn','Copy');b.type='button';b.onclick=()=>copyText(text,b);head.appendChild(b);box.appendChild(head);box.appendChild(el('pre','',text));parent.appendChild(box)}
function fieldLines(fields){return fields.filter(([,v])=>v!==undefined&&v!==null&&v!=='').map(([k,v])=>k+': '+v).join('\n')}
function renderGig(gig,index){const search=gig.search||{};const card=el('article','gig');const main=el('div','gig-main');const left=el('div');const h=el('h3');const link=el('a','',gig.title||search.card_title||gig.url);link.href=gig.url;link.target='_blank';link.rel='noopener';h.appendChild(link);left.appendChild(h);const meta=el('div','meta');if(search.global_position)meta.appendChild(chip('Rank #'+search.global_position,'rank'));meta.appendChild(chip(search.is_sponsored?'Sponsored':'Organic',search.is_sponsored?'ad':''));if(search.page_number)meta.appendChild(chip('Page '+search.page_number+' · Pos '+search.page_position));if(search.organic_position)meta.appendChild(chip('Organic #'+search.organic_position));if(gig.seller_name||gig.seller_username)meta.appendChild(chip('Seller: '+(gig.seller_name||gig.seller_username)));if(gig.seller_level)meta.appendChild(chip(gig.seller_level));if(gig.rating)meta.appendChild(chip('★ '+gig.rating+(gig.review_count?' ('+gig.review_count+')':'')));if(search.seller_online)meta.appendChild(chip('Online'));if(gig.error)meta.appendChild(chip('Error'));left.appendChild(meta);main.appendChild(left);const price=el('div','price');price.appendChild(el('small','','Starting price'));price.appendChild(el('strong','',gig.starting_price_usd!=null?'$'+gig.starting_price_usd:'—'));main.appendChild(price);card.appendChild(main);
const details=el('details');details.open=index===0;details.appendChild(el('summary','','Structured sections aur copy options'));const body=el('div','detail-body');if(gig.error)section(body,'Fetch error',gig.error);section(body,'Search position',fieldLines([['Keyword',search.niche],['Global rank',search.global_position],['Organic rank',search.organic_position],['Sponsored rank',search.sponsored_position],['Page',search.page_number],['Page position',search.page_position],['Placement',search.is_sponsored?'Sponsored':'Organic'],['Card price',search.card_price],['Badges',(search.badges||[]).join(', ')]]));section(body,'Gig overview',fieldLines([['Title',gig.title],['URL',gig.url],['Rating',gig.rating],['Review count',gig.review_count],['Starting price USD',gig.starting_price_usd],['Hourly rate USD',gig.hourly_rate_usd],['Categories',(gig.category_path||[]).join(' > ')],['Gallery items',gig.gallery_count],['Video',gig.has_video?'Yes':'No'],['Fetched at',gig.fetched_at]]));section(body,'Seller details',fieldLines([['Name',gig.seller_name],['Username',gig.seller_username],['Level',gig.seller_level],['Country',gig.seller_country],['Member since',gig.member_since],['Response time',gig.average_response_time],['Last delivery',gig.last_delivery]]));section(body,'Meta description',gig.meta_description);section(body,'About / service description',gig.about_text);section(body,'Structured packages',gig.packages);section(body,'Raw packages text',gig.packages_text);section(body,'FAQs',gig.faqs);section(body,'Raw FAQ text',gig.faq_text);section(body,'Review summary',gig.review_summary);section(body,'Visible reviews',gig.visible_reviews);section(body,'Raw reviews text',gig.reviews_text);section(body,'Related tags',gig.related_tags);section(body,'Media URLs',gig.media_urls);section(body,'Structured JSON-LD',gig.json_ld);section(body,'Raw visible page text',gig.raw_visible_text);details.appendChild(body);card.appendChild(details);return card}
function fmt(v){if(v===undefined||v===null||v==='')return '—';if(typeof v==='number')return Number.isInteger(v)?String(v):v.toFixed(2);if(Array.isArray(v))return v.join(', ');return String(v)}
function analyticsCard(label,value,note=''){const c=el('div','analytics-card');c.appendChild(el('small','',label));c.appendChild(el('strong','',fmt(value)));if(note)c.appendChild(el('span','',note));return c}
function block(parent,title){const b=el('section','panel-block');b.appendChild(el('h3','',title));parent.appendChild(b);return b}
function renderBars(parent,rows,labelKey='label',valueKey='count',limit=15){const data=(rows||[]).slice(0,limit);if(!data.length){parent.appendChild(el('div','empty','No data available'));return}const max=Math.max(...data.map(r=>Number(r[valueKey]||0)),1);const list=el('div','bar-list');for(const row of data){const line=el('div','bar-row');line.appendChild(el('div','bar-label',fmt(row[labelKey])));const track=el('div','bar-track');const fill=el('div','bar-fill');fill.style.width=(100*Number(row[valueKey]||0)/max)+'%';track.appendChild(fill);line.appendChild(track);line.appendChild(el('div','bar-value',fmt(row[valueKey])));list.appendChild(line)}parent.appendChild(list)}
function renderTable(parent,rows,columns,maxRows=200){const source=(rows||[]).slice();if(!source.length){parent.appendChild(el('div','empty','No rows available'));return}const wrap=el('div','table-wrap');const table=el('table','analysis-table');const thead=document.createElement('thead');const headRow=document.createElement('tr');const tbody=document.createElement('tbody');let sortKey=null,sortAsc=true;function draw(){tbody.replaceChildren();const data=source.slice();if(sortKey)data.sort((a,b)=>{const av=a[sortKey],bv=b[sortKey];if(av===bv)return 0;if(av===undefined||av===null)return 1;if(bv===undefined||bv===null)return -1;if(typeof av==='number'&&typeof bv==='number')return sortAsc?av-bv:bv-av;return sortAsc?String(av).localeCompare(String(bv)):String(bv).localeCompare(String(av))});for(const row of data.slice(0,maxRows)){const tr=document.createElement('tr');for(const [key] of columns){const td=document.createElement('td');const value=row[key];if(key==='url'&&value){const a=el('a','', 'Open');a.href=value;a.target='_blank';a.rel='noopener';a.style.color='var(--green2)';td.appendChild(a)}else td.textContent=fmt(value);tr.appendChild(td)}tbody.appendChild(tr)}}for(const [key,label] of columns){const th=el('th','',label);th.onclick=()=>{if(sortKey===key)sortAsc=!sortAsc;else{sortKey=key;sortAsc=true}draw()};headRow.appendChild(th)}thead.appendChild(headRow);table.appendChild(thead);table.appendChild(tbody);wrap.appendChild(table);parent.appendChild(wrap);draw()}
function renderOverview(root){const o=analysisData.overview||{};const g=el('div','analytics-grid');g.appendChild(analyticsCard('Sampled gigs',o.sampled_gigs));g.appendChild(analyticsCard('Available results',o.available_results));g.appendChild(analyticsCard('Unique sellers',o.unique_sellers));g.appendChild(analyticsCard('Sponsored share',(o.sponsored_share_pct||0)+'%'));g.appendChild(analyticsCard('Median price','$'+fmt((o.starting_price||{}).median)));g.appendChild(analyticsCard('Average rating',fmt((o.rating||{}).mean)));g.appendChild(analyticsCard('Median reviews',fmt((o.review_count||{}).median)));g.appendChild(analyticsCard('Video share',(o.video_share_pct||0)+'%'));root.appendChild(g);const levels=block(root,'Seller levels');renderBars(levels,o.seller_levels);const countries=block(root,'Seller countries');renderBars(countries,o.seller_countries);const note=el('div','analysis-note','Public sample coverage: '+fmt(o.detail_coverage_pct)+'%. These are observed marketplace statistics, not private Fiverr analytics.');root.appendChild(note)}
function renderRankings(root){const r=analysisData.rankings||{};const top=block(root,'Observed ranking leaderboard');renderTable(top,r.top_gigs,[['global_position','Rank'],['organic_position','Organic'],['is_sponsored','Sponsored'],['title','Gig'],['seller','Seller'],['seller_level','Level'],['price','Price'],['rating','Rating'],['review_count','Reviews'],['url','Link']],100);const sellers=block(root,'Seller concentration');renderTable(sellers,r.seller_concentration,[['seller','Seller'],['seller_username','Username'],['gig_count','Gigs'],['best_rank','Best rank'],['average_rank','Avg rank'],['sponsored_count','Sponsored']],100)}
function renderMovement(root){const m=analysisData.rank_movement||{};if(!m.available){root.appendChild(el('div','analysis-note',m.reason||'A previous crawl is required.'));return}const g=el('div','analytics-grid');g.appendChild(analyticsCard('Common gigs',m.common_count));g.appendChild(analyticsCard('Gainers',m.gainers));g.appendChild(analyticsCard('Decliners',m.decliners));g.appendChild(analyticsCard('Unchanged',m.unchanged));root.appendChild(g);const b=block(root,'Rank changes');renderTable(b,m.movements,[['title','Gig'],['seller','Seller'],['previous_rank','Previous'],['current_rank','Current'],['change','Change'],['price_change','Price Δ'],['review_change','Reviews Δ'],['url','Link']],200);const n=block(root,'New gigs');renderTable(n,m.new_gigs,[['global_position','Rank'],['title','Gig'],['seller','Seller'],['price','Price'],['url','Link']],100)}
function renderKeywords(root){const k=analysisData.keywords||{};const intro=el('div','analysis-note','Phrases are extracted deterministically from public titles/tags. Click a table header to sort.');root.appendChild(intro);for(const [key,title] of [['bigrams','Two-word phrases'],['trigrams','Three-word phrases'],['title_starts','Title-start patterns'],['unigrams','Single terms'],['related_tags','Related tags']]){const b=block(root,title);renderTable(b,k[key],[['phrase','Phrase'],['gig_count','Gigs'],['share_pct','Share %'],['top_20_count','Top 20'],['average_rank','Avg rank'],['median_price','Median price'],['average_reviews','Avg reviews']],120)}}
function renderClusters(root){const b=block(root,'Deterministic keyword clusters');renderTable(b,analysisData.keyword_clusters,[['cluster','Cluster'],['phrases','Phrases'],['gig_count','Gigs'],['share_pct','Share %'],['average_rank','Avg rank'],['median_price','Median price']],100);root.appendChild(el('div','analysis-note','Cluster labels come from repeated shared tokens and Jaccard overlap—no LLM or semantic model is used.'))}
function renderPricing(root){const p=analysisData.pricing||{};const o=p.overall||{};const g=el('div','analytics-grid');for(const [label,key] of [['Minimum','min'],['Q1','q1'],['Median','median'],['Mean','mean'],['Q3','q3'],['P90','p90'],['Maximum','max'],['Listings','count']])g.appendChild(analyticsCard(label,key==='count'?o[key]:'$'+fmt(o[key])));root.appendChild(g);const hist=block(root,'Starting-price distribution');renderBars(hist,p.histogram,'label','count',30);const tiers=block(root,'Package tier statistics');const tierRows=Object.entries(p.package_tiers||{}).map(([segment,v])=>({segment,...v}));renderTable(tiers,tierRows,[['segment','Tier'],['count','Count'],['min','Min'],['q1','Q1'],['median','Median'],['mean','Mean'],['q3','Q3'],['max','Max']]);const seg=block(root,'Price by seller level');renderTable(seg,p.by_seller_level,[['segment','Level'],['count','Count'],['median','Median'],['mean','Mean'],['q1','Q1'],['q3','Q3'],['max','Max']])}
function renderPackages(root){const p=analysisData.packages||{};const g=el('div','analytics-grid');g.appendChild(analyticsCard('Gigs with packages',p.gigs_with_packages));for(const row of(p.tier_counts||[]))g.appendChild(analyticsCard(row.tier,row.count));root.appendChild(g);const matrix=block(root,'Feature matrix');renderTable(matrix,p.feature_matrix,[['feature','Feature'],['gig_count','Gigs'],['overall_coverage_pct','Coverage %'],['basic_count','Basic'],['standard_count','Standard'],['premium_count','Premium']],150);for(const [tier,rows] of Object.entries(p.delivery_patterns||{})){const b=block(root,tier+' delivery patterns');renderBars(b,rows)}}
function renderCompetitors(root){const controls=el('div','filter-row');const q=document.createElement('input');q.placeholder='Search title or seller';const level=document.createElement('select');for(const v of['All levels',...new Set((analysisData.competitors||[]).map(x=>x.seller_level).filter(Boolean))]){const op=el('option','',v);op.value=v;level.appendChild(op)}const placement=document.createElement('select');for(const v of['All placements','Organic','Sponsored']){const op=el('option','',v);op.value=v;placement.appendChild(op)}controls.append(q,level,placement);root.appendChild(controls);const holder=block(root,'Competitor explorer');function draw(){holder.querySelectorAll('.table-wrap,.empty').forEach(n=>n.remove());const term=q.value.toLowerCase();const rows=(analysisData.competitors||[]).filter(x=>(!term||((x.title||'')+' '+(x.seller||'')).toLowerCase().includes(term))&&(level.value==='All levels'||x.seller_level===level.value)&&(placement.value==='All placements'||(placement.value==='Sponsored')===Boolean(x.is_sponsored)));renderTable(holder,rows,[['global_position','Rank'],['title','Gig'],['seller','Seller'],['seller_level','Level'],['seller_country','Country'],['price','Price'],['rating','Rating'],['review_count','Reviews'],['has_video','Video'],['package_count','Packages'],['url','Link']],300)}q.oninput=draw;level.onchange=draw;placement.onchange=draw;draw()}
function renderReviews(root){const r=analysisData.reviews||{};const g=el('div','analytics-grid');g.appendChild(analyticsCard('Visible reviews',r.visible_reviews_analyzed));g.appendChild(analyticsCard('Average rating',r.average_visible_rating));g.appendChild(analyticsCard('Ongoing share',(r.ongoing_collaboration_share_pct||0)+'%'));g.appendChild(analyticsCard('Work-sample share',(r.work_sample_share_pct||0)+'%'));g.appendChild(analyticsCard('Seller-response share',(r.seller_response_share_pct||0)+'%'));root.appendChild(g);const sentiment=block(root,'Rule-based sentiment');renderBars(sentiment,r.sentiment,'label','count');const praise=block(root,'Most praised terms');renderBars(praise,r.praise_terms,'term','count');const concerns=block(root,'Concern terms');renderBars(concerns,r.concern_terms,'term','count');const phrases=block(root,'Repeated buyer phrases');renderTable(phrases,r.top_phrases,[['phrase','Phrase'],['review_count','Reviews'],['gig_count','Gigs']],100);const countries=block(root,'Buyer countries');renderBars(countries,r.buyer_countries)}
function renderGaps(root){const g=analysisData.market_gaps||{};root.appendChild(el('div','analysis-note',(g.formula||{}).warning||'Scores are public-data proxies.'));const opportunities=block(root,'Keyword opportunities');renderTable(opportunities,g.keyword_opportunities,[['phrase','Phrase'],['opportunity_score','Score'],['demand_proxy','Demand proxy'],['competition_proxy','Competition'],['price_potential','Price potential'],['gig_count','Gigs'],['median_price','Median price'],['evidence','Evidence']],100);const review=block(root,'Review-language gaps');renderTable(review,g.review_language_gaps,[['phrase','Buyer phrase'],['review_gig_count','Review gigs'],['title_gig_count','Title gigs'],['gap_type','Reason']],100);const offers=block(root,'Offer-feature gaps');renderTable(offers,g.offer_feature_gaps,[['feature','Feature'],['top_10_gig_count','Top-10 gigs'],['overall_gig_count','Overall gigs'],['overall_coverage_pct','Coverage %'],['gap_type','Reason']],100)}
function renderAnalysisTab(tab){activeAnalysisTab=tab;document.querySelectorAll('#analysisTabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));$('analysisCsv').href='/api/jobs/'+currentJobId+'/analysis/'+tab+'.csv';const root=$('analysisContent');root.replaceChildren();if(!analysisData){root.appendChild(el('div','empty','Analysis not loaded'));return}const renders={overview:renderOverview,rankings:renderRankings,movement:renderMovement,keywords:renderKeywords,clusters:renderClusters,pricing:renderPricing,packages:renderPackages,competitors:renderCompetitors,reviews:renderReviews,gaps:renderGaps};(renders[tab]||renderOverview)(root)}
async function loadAnalysis(){try{analysisData=await api('/api/jobs/'+currentJobId+'/analysis');$('analysisPanel').classList.add('show');$('analysisMeta').textContent='Generated '+analysisData.generated_at+' · '+(analysisData.methodology.llm_used?'LLM enabled':'No LLM · deterministic analytics');renderAnalysisTab(activeAnalysisTab)}catch(e){$('analysisPanel').classList.add('show');$('analysisContent').replaceChildren(el('div','analysis-note','Analysis unavailable: '+e.message))}}
document.querySelectorAll('#analysisTabs button').forEach(button=>button.onclick=()=>renderAnalysisTab(button.dataset.tab));
function listPanel(root,title,items){const b=block(root,title);if(!items||!items.length){b.appendChild(el('div','empty','No items'));return b}const ul=document.createElement('ul');ul.style.margin='0';ul.style.paddingLeft='20px';for(const item of items){const li=el('li','',typeof item==='string'?item:JSON.stringify(item));li.style.marginBottom='7px';li.style.color='var(--muted)';ul.appendChild(li)}b.appendChild(ul);return b}
async function loadAiConfig(){try{aiConfig=await api('/api/ai/config');$('aiPanel').classList.add('show');$('aiKeyState').textContent=aiConfig.configured?'OpenRouter configured':'Key not configured · Dry run only';$('aiKeyState').style.color=aiConfig.configured?'var(--green2)':'var(--warn)';$('aiMaxGigs').value=String(Math.min(10,aiConfig.max_gigs||10));await loadLatestAiRun()}catch(e){$('aiPanel').classList.add('show');$('aiKeyState').textContent='Configuration error'}}
async function loadLatestAiRun(){if(!currentJobId)return;try{const data=await api('/api/jobs/'+currentJobId+'/ai-runs?limit=1');if(!data.runs.length)return;const run=data.runs[0];currentAiRunId=run.id;renderAiRun(run);if(run.status==='completed'){aiResult=await api(run.result_url);$('aiResults').classList.add('show');renderAiTab(activeAiTab)}else if(['queued','running'].includes(run.status)){if(!aiPollTimer)aiPollTimer=setInterval(pollAiRun,1500)}else if(['failed','interrupted'].includes(run.status)){$('aiProgressText').textContent=run.error||'AI run failed';$('aiProgressText').classList.add('error')}}catch{}}
function renderAiRun(run){$('aiProgress').classList.add('show');const p=Math.max(0,Math.min(100,Number(run.progress_percent||0)));$('aiProgressBar').style.width=p+'%';$('aiProgressText').textContent=(run.stage||run.status)+' · '+p.toFixed(1)+'% · gigs '+(run.processed_gigs||0)+'/'+(run.selected_gigs||run.max_gigs||0)+' · tokens '+(run.total_tokens||0)+' · cost $'+Number(run.actual_cost_usd||0).toFixed(5);$('runAi').disabled=['queued','running'].includes(run.status)}
async function pollAiRun(){if(!currentAiRunId)return;try{const run=await api('/api/ai-runs/'+currentAiRunId);renderAiRun(run);if(['completed','failed','interrupted'].includes(run.status)){clearInterval(aiPollTimer);aiPollTimer=null;$('runAi').disabled=false;if(run.status==='completed'){aiResult=await api(run.result_url);$('aiResults').classList.add('show');renderAiTab(activeAiTab)}else{$('aiProgressText').textContent=run.error||'AI run failed';$('aiProgressText').classList.add('error')}}}catch(e){clearInterval(aiPollTimer);aiPollTimer=null;$('runAi').disabled=false;$('aiProgressText').textContent=e.message}}
function renderAiOverview(root){if(aiResult.dry_run){const g=el('div','score-grid');g.appendChild(analyticsCard('Selected gigs',aiResult.selected_gigs));g.appendChild(analyticsCard('Batches',aiResult.batch_count));g.appendChild(analyticsCard('Est. input',aiResult.estimated_input_tokens+' tokens'));g.appendChild(analyticsCard('Est. output',aiResult.estimated_output_tokens+' tokens'));g.appendChild(analyticsCard('Estimated cost','$'+Number(aiResult.estimated_cost_usd||0).toFixed(4)));g.appendChild(analyticsCard('Cost cap','$'+Number(aiResult.cost_cap_usd||0).toFixed(2)));root.appendChild(g);root.appendChild(el('div','analysis-note',aiResult.note));const m=block(root,'Planned models');for(const [k,v] of Object.entries(aiResult.models||{}))m.appendChild(el('div','model-row',k+': '+v));const s=block(root,'Selected public gigs');renderTable(s,aiResult.selected,[['rank','Rank'],['title','Gig'],['url','Link']],100);return}const s=aiResult.market_synthesis||{};const g=el('div','analytics-grid');g.appendChild(analyticsCard('Audited gigs',(aiResult.gig_analyses||[]).length));g.appendChild(analyticsCard('Embedding pairs',(aiResult.semantic_similarity||{}).pair_count));g.appendChild(analyticsCard('Actual cost','$'+Number((aiResult.usage||{}).actual_cost_usd||0).toFixed(5)));g.appendChild(analyticsCard('Cache hits',(aiResult.usage||{}).cache_hits||0));root.appendChild(g);root.appendChild(el('div','analysis-note',s.market_summary||'No synthesis'));listPanel(root,'Dominant intents',s.dominant_intents);listPanel(root,'High-ticket opportunities',s.high_ticket_opportunities);if((aiResult.warnings||[]).length)listPanel(root,'Warnings',aiResult.warnings)}
function renderAiIntents(root){const rows=(aiResult.gig_analyses||[]).map(x=>({url:x.url,title:x.title,service:x.intent&&x.intent.service,buyer_problem:x.intent&&x.intent.buyer_problem,desired_outcome:x.intent&&x.intent.desired_outcome,target_buyer:x.intent&&x.intent.target_buyer,industry:x.intent&&x.intent.industry,tools:(x.intent&&x.intent.tools||[]).join(', '),positioning:x.positioning_archetype,confidence:x.confidence}));const b=block(root,'Extracted buyer intents');renderTable(b,rows,[['title','Gig'],['service','Service'],['buyer_problem','Buyer problem'],['desired_outcome','Outcome'],['target_buyer','Target buyer'],['industry','Industry'],['tools','Tools'],['positioning','Positioning'],['confidence','Confidence'],['url','Link']],100)}
function renderAiScores(root){const rows=(aiResult.gig_analyses||[]).map(x=>({title:x.title,url:x.url,...(x.scores||{}),confidence:x.confidence}));const b=block(root,'Diagnostic scorecard');renderTable(b,rows,[['title','Gig'],['neo_readiness','Neo readiness'],['intent_clarity','Intent'],['conversion_readiness','Conversion'],['trust_proof','Trust'],['package_consistency','Packages'],['semantic_differentiation','Differentiation'],['high_ticket_readiness','High-ticket'],['compliance_risk','Compliance risk'],['confidence','Confidence'],['url','Link']],100);root.appendChild(el('div','analysis-note','Scores are AI diagnostics over public data, not Fiverr internal metrics. Compliance risk: higher means more potential risk.'))}
function renderAiSimilarity(root){const s=aiResult.semantic_similarity||{};const b=block(root,'Most similar pairs');renderTable(b,s.most_similar_pairs,[['left_title','Gig A'],['right_title','Gig B'],['similarity_pct','Similarity %'],['left_url','Link A'],['right_url','Link B']],100);const own=block(root,'Your gig nearest competitors');renderTable(own,s.own_gig_neighbors,[['title','Competitor'],['similarity_pct','Similarity %'],['url','Link']],20)}
function renderAiSynthesis(root){const s=aiResult.market_synthesis||{};root.appendChild(el('div','analysis-note',s.market_summary||'No synthesis'));const archetypes=block(root,'Positioning archetypes');renderTable(archetypes,s.positioning_archetypes,[['name','Archetype'],['gig_count','Gigs'],['description','Description']],50);const gaps=block(root,'Semantic gaps');renderTable(gaps,s.semantic_gaps,[['name','Gap'],['evidence','Evidence'],['opportunity','Opportunity']],50);const own=s.own_gig_audit||{};if(own.included){listPanel(root,'Own gig strengths',own.strengths);listPanel(root,'Own gig gaps',own.gaps);listPanel(root,'Priority actions',own.priority_actions)}listPanel(root,'Caveats',s.caveats)}
function renderAiEvidence(root){const rows=[];for(const gig of(aiResult.gig_analyses||[])){for(const e of(gig.evidence||[]))rows.push({title:gig.title,url:gig.url,section:e.section,quote:e.quote,reason:e.reason,confidence:gig.confidence})}const b=block(root,'Evidence ledger');renderTable(b,rows,[['title','Gig'],['section','Section'],['quote','Evidence quote'],['reason','Reason'],['confidence','Confidence'],['url','Link']],200)}
function renderAiUsage(root){const u=aiResult.usage||{};const g=el('div','score-grid');for(const [label,key] of [['Prompt tokens','prompt_tokens'],['Completion tokens','completion_tokens'],['Total tokens','total_tokens'],['Actual cost USD','actual_cost_usd'],['API calls','api_calls'],['Cache hits','cache_hits'],['Cost cap','max_cost_usd']])g.appendChild(analyticsCard(label,u[key]));root.appendChild(g);const m=block(root,'Models');for(const [k,v] of Object.entries(aiResult.models||aiResult.models||{}))m.appendChild(el('div','model-row',k+': '+v));root.appendChild(el('div','analysis-note','API key is not included in this result, database, logs or exports.'))}
function renderAiTab(tab){activeAiTab=tab;document.querySelectorAll('#aiTabs button').forEach(b=>b.classList.toggle('active',b.dataset.aiTab===tab));const root=$('aiContent');root.replaceChildren();if(!aiResult){root.appendChild(el('div','empty','No Phase 3 result yet'));return}const map={ai_overview:renderAiOverview,intents:renderAiIntents,scores:renderAiScores,similarity:renderAiSimilarity,synthesis:renderAiSynthesis,evidence:renderAiEvidence,usage:renderAiUsage};(map[tab]||renderAiOverview)(root)}
document.querySelectorAll('#aiTabs button').forEach(b=>b.onclick=()=>renderAiTab(b.dataset.aiTab));
$('runAi').onclick=async()=>{if(!currentJobId){$('aiProgress').classList.add('show');$('aiProgressText').textContent='Complete or select a crawl first.';return}const mode=$('aiMode').value;if(mode!=='dry_run'&&(!aiConfig||!aiConfig.configured)){$('aiProgress').classList.add('show');$('aiProgressText').textContent='Rotate the exposed key and configure a new OPENROUTER_API_KEY first.';return}$('runAi').disabled=true;$('aiProgress').classList.add('show');$('aiProgressText').textContent='Starting '+mode+'…';$('aiResults').classList.remove('show');aiResult=null;try{const run=await api('/api/jobs/'+currentJobId+'/ai-runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,max_gigs:Number($('aiMaxGigs').value),own_gig_url:$('ownGigUrl').value||null})});currentAiRunId=run.id;renderAiRun(run);clearInterval(aiPollTimer);aiPollTimer=setInterval(pollAiRun,1200);await pollAiRun()}catch(e){$('runAi').disabled=false;$('aiProgressText').textContent=e.message;$('aiProgressText').classList.add('error')}};
async function loadBuilderConfig(){try{builderConfig=await api('/api/generation/config');$('builderPanel').classList.add('show');$('builderStatus').textContent=builderConfig.configured?'OpenRouter configured · draft mode':'Key not configured · dry run only';await loadLatestBuilderRun()}catch{$('builderPanel').classList.add('show');$('builderStatus').textContent='Builder configuration error'}}
async function loadLatestBuilderRun(){if(!currentJobId)return;try{const data=await api('/api/jobs/'+currentJobId+'/generation-runs?limit=1');if(!data.runs.length)return;const run=data.runs[0];currentBuilderRunId=run.id;renderBuilderRun(run);if(run.status==='completed'){builderResult=await api(run.result_url);$('builderResults').classList.add('show');$('downloadDraft').href=run.markdown_url;$('downloadDraft').style.display='inline-flex';$('approveDraft').style.display=builderResult.dry_run?'none':'inline-flex';renderBuilderTab(activeBuilderTab)}else if(['queued','running'].includes(run.status)&&!builderPollTimer)builderPollTimer=setInterval(pollBuilderRun,1200);else if(['failed','interrupted'].includes(run.status)){$('builderProgressText').textContent=run.error||'Generation failed';$('builderProgressText').classList.add('error')}}catch{}}
function renderBuilderRun(run){$('builderProgress').classList.add('show');const p=Math.max(0,Math.min(100,Number(run.progress_percent||0)));$('builderProgressBar').style.width=p+'%';$('builderProgressText').textContent=(run.stage||run.status)+' · '+p.toFixed(1)+'% · tokens '+(run.total_tokens||0)+' · cost $'+Number(run.actual_cost_usd||0).toFixed(5);$('builderStatus').textContent='Status: '+run.status+' · approval: '+(run.approval_status||'draft');$('runBuilder').disabled=['queued','running'].includes(run.status)}
async function pollBuilderRun(){if(!currentBuilderRunId)return;try{const run=await api('/api/generation-runs/'+currentBuilderRunId);renderBuilderRun(run);if(['completed','failed','interrupted'].includes(run.status)){clearInterval(builderPollTimer);builderPollTimer=null;$('runBuilder').disabled=false;if(run.status==='completed'){builderResult=await api(run.result_url);$('builderResults').classList.add('show');$('downloadDraft').href=run.markdown_url;$('downloadDraft').style.display='inline-flex';$('approveDraft').style.display=builderResult.dry_run?'none':'inline-flex';renderBuilderTab(activeBuilderTab)}else{$('builderProgressText').textContent=run.error||'Generation failed';$('builderProgressText').classList.add('error')}}}catch(e){clearInterval(builderPollTimer);builderPollTimer=null;$('runBuilder').disabled=false;$('builderProgressText').textContent=e.message}}
function renderBuilderDraft(root){if(builderResult.dry_run){const g=el('div','analytics-grid');g.appendChild(analyticsCard('Estimated input',builderResult.estimated_input_tokens+' tokens'));g.appendChild(analyticsCard('Estimated output',builderResult.estimated_output_tokens+' tokens'));g.appendChild(analyticsCard('Estimated cost','$'+Number(builderResult.estimated_cost_usd||0).toFixed(4)));g.appendChild(analyticsCard('Cost cap','$'+Number(builderResult.cost_cap_usd||0).toFixed(2)));g.appendChild(analyticsCard('Target found',builderResult.target_found?'Yes':'No'));g.appendChild(analyticsCard('Phase 3 context',builderResult.phase3_context_available?'Yes':'No'));root.appendChild(g);root.appendChild(el('div','analysis-note',builderResult.note));listPanel(root,'Planned outputs',builderResult.planned_outputs);return}const final=builderResult.final||{},gig=final.recommended_gig||{};root.appendChild(el('div','analysis-note',final.strategy_summary||''));if((builderResult.warnings||[]).length)listPanel(root,'Routing warnings',builderResult.warnings);const positions=block(root,'Positioning options');renderTable(positions,final.positioning_options,[['name','Positioning'],['target_buyer','Target buyer'],['value_proposition','Value proposition'],['differentiator','Differentiator']],10);section(root,'Title',gig.title);section(root,'Five tags',gig.tags);section(root,'Category / service',fieldLines([['Category',gig.category],['Subcategory',gig.subcategory],['Service type',gig.service_type]]));section(root,'Description',gig.description);section(root,'CTA',gig.cta)}
function renderBuilderPackages(root){const gig=((builderResult.final||{}).recommended_gig)||{};const b=block(root,'Basic / Standard / Premium');renderTable(b,gig.packages,[['name','Package'],['price_usd','Price'],['description','Description'],['delivery_days','Days'],['revisions','Revisions'],['ideal_for','Ideal for'],['deliverables','Deliverables'],['features','Features']],10)}
function renderBuilderFaq(root){const gig=((builderResult.final||{}).recommended_gig)||{};const f=block(root,'FAQs');renderTable(f,gig.faqs,[['question','Question'],['answer','Answer']],30);section(root,'Buyer requirements',gig.buyer_requirements);section(root,'Scope exclusions',gig.scope_exclusions)}
function renderBuilderVisuals(root){const v=(builderResult.final||{}).visual_system||{};section(root,'Thumbnail headline',v.thumbnail_headline);section(root,'Thumbnail subheadline',v.thumbnail_subheadline);const g=block(root,'Gallery image briefs');renderTable(g,v.gallery_briefs,[['image_number','#'],['purpose','Purpose'],['headline','Headline'],['content','Content'],['visual_direction','Visual direction']],10);section(root,'Video script',v.video_script)}
function renderBuilderCompliance(root){const v=builderResult.validation||{};const g=el('div','analytics-grid');g.appendChild(analyticsCard('Passed',v.passed?'Yes':'No'));g.appendChild(analyticsCard('Risk level',v.risk_level));g.appendChild(analyticsCard('Title chars',(v.character_counts||{}).title));g.appendChild(analyticsCard('Description chars',(v.character_counts||{}).description));root.appendChild(g);section(root,'Blocking issues',v.issues);section(root,'Warnings',v.warnings);const c=block(root,'Deterministic checks');renderTable(c,v.checks,[['check','Check'],['passed','Passed'],['note','Note']],50);section(root,'Model compliance check',(builderResult.final||{}).model_compliance_check)}
function renderBuilderEvidence(root){const f=builderResult.final||{};section(root,'Evidence basis',f.evidence_basis);section(root,'Methodology',builderResult.methodology);if(builderResult.draft)section(root,'Original draft before deep refinement',builderResult.draft)}
function renderBuilderComparison(root){section(root,'Before / after',builderResult.before_after)}
function renderBuilderUsage(root){const u=builderResult.usage||{};const g=el('div','analytics-grid');for(const [label,key] of [['Prompt tokens','prompt_tokens'],['Completion tokens','completion_tokens'],['Total tokens','total_tokens'],['Actual cost USD','actual_cost_usd'],['API calls','api_calls'],['Cache hits','cache_hits'],['Cost cap','max_cost_usd']])g.appendChild(analyticsCard(label,u[key]));root.appendChild(g);section(root,'Models',builderResult.models);root.appendChild(el('div','analysis-note','The API key is never stored in this result or export.'))}
function renderBuilderTab(tab){activeBuilderTab=tab;document.querySelectorAll('#builderTabs button').forEach(b=>b.classList.toggle('active',b.dataset.builderTab===tab));const root=$('builderContent');root.replaceChildren();if(!builderResult){root.appendChild(el('div','empty','No generated draft yet'));return}const map={draft:renderBuilderDraft,packages:renderBuilderPackages,faq:renderBuilderFaq,visuals:renderBuilderVisuals,compliance:renderBuilderCompliance,evidence:renderBuilderEvidence,comparison:renderBuilderComparison,builder_usage:renderBuilderUsage};(map[tab]||renderBuilderDraft)(root)}
document.querySelectorAll('#builderTabs button').forEach(b=>b.onclick=()=>renderBuilderTab(b.dataset.builderTab));
$('runBuilder').onclick=async()=>{if(!currentJobId){$('builderProgress').classList.add('show');$('builderProgressText').textContent='Complete or select a crawl first.';return}const mode=$('builderMode').value;if(mode!=='dry_run'&&(!builderConfig||!builderConfig.configured)){$('builderProgress').classList.add('show');$('builderProgressText').textContent='Rotate the exposed key and configure a new OPENROUTER_API_KEY first.';return}$('runBuilder').disabled=true;$('builderProgress').classList.add('show');$('builderResults').classList.remove('show');$('downloadDraft').style.display='none';$('approveDraft').style.display='none';builderResult=null;try{const run=await api('/api/jobs/'+currentJobId+'/generation-runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,target_gig_url:$('builderTargetUrl').value||null,target_buyer:$('builderBuyer').value,positioning_goal:$('builderPositioning').value,tone:$('builderTone').value,output_language:'English',pricing_preference:$('builderPricing').value})});currentBuilderRunId=run.id;renderBuilderRun(run);clearInterval(builderPollTimer);builderPollTimer=setInterval(pollBuilderRun,1200);await pollBuilderRun()}catch(e){$('runBuilder').disabled=false;$('builderProgressText').textContent=e.message;$('builderProgressText').classList.add('error')}};
$('approveDraft').onclick=async()=>{if(!currentBuilderRunId)return;try{const run=await api('/api/generation-runs/'+currentBuilderRunId+'/approval',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'approved'})});$('builderStatus').textContent='Status: '+run.status+' · approval: '+run.approval_status;$('approveDraft').style.display='none'}catch(e){$('builderProgressText').textContent=e.message}};
function renderJob(job){$('jobPanel').classList.add('show');$('jobTitle').textContent=job.niche+' crawl';$('jobId').textContent=job.id;$('stage').textContent=job.stage||job.status;const p=Math.max(0,Math.min(100,Number(job.progress_percent||0)));$('progressBar').style.width=p+'%';$('mProgress').textContent=p.toFixed(1)+'%';$('mPages').textContent=job.pages_scanned||0;$('mDiscovered').textContent=job.discovered_count||0;$('mProcessed').textContent=job.processed_count||0;$('mSuccess').textContent=job.success_count||0;$('mFailed').textContent=job.failed_count||0;$('cancel').style.display=['queued','running','cancelling'].includes(job.status)?'inline-flex':'none';const available=job.available_results?' · Fiverr showed '+job.available_results+' total results':'';$('jobMessage').textContent=(job.discovery_source||'Waiting for discovery')+available;if(job.error){$('jobMessage').textContent=job.error;$('jobMessage').classList.add('error')}else $('jobMessage').classList.remove('error');$('warnings').replaceChildren();for(const w of(job.warnings||[]))$('warnings').appendChild(el('div','warning',w))}
async function pollJob(){if(!currentJobId)return;try{const job=await api('/api/jobs/'+currentJobId);renderJob(job);if(['completed','cancelled','failed','interrupted'].includes(job.status)){clearInterval(pollTimer);pollTimer=null;$('submit').disabled=false;$('submit').textContent='Start background job';if(job.status==='completed'||job.status==='cancelled'){showSummary(job);await loadAnalysis();await loadAiConfig();await loadBuilderConfig();await loadResults(0);switchWorkspace('intelligence')}localStorage.removeItem('fiverr-current-job')}}catch(e){clearInterval(pollTimer);pollTimer=null;localStorage.removeItem('fiverr-current-job');$('submit').disabled=false;$('submit').textContent='Start background job';$('jobMessage').textContent=e.message;$('jobMessage').classList.add('error')}}
function showSummary(job){enableResearchWorkspaces(true);$('summary').classList.add('show');$('summaryTitle').textContent=job.niche+' results';$('summaryMeta').textContent=(job.success_count||0)+' successful · '+(job.failed_count||0)+' failed · '+(job.discovered_count||0)+' discovered';$('downloads').replaceChildren();for(const[label,href]of Object.entries(job.downloads||{})){const a=el('a','button',label.toUpperCase()+' download');a.href=href;$('downloads').appendChild(a)}}
async function loadResults(offset){if(!currentJobId)return;const data=await api('/api/jobs/'+currentJobId+'/results?offset='+offset+'&limit='+PAGE_SIZE);currentOffset=data.offset;currentTotal=data.total;$('results').replaceChildren();data.results.forEach((gig,i)=>$('results').appendChild(renderGig(gig,i)));$('pagerWrap').classList.toggle('show',data.total>0);const from=data.total?data.offset+1:0,to=Math.min(data.offset+data.results.length,data.total);$('pagerInfo').textContent='Showing '+from+'–'+to+' of '+data.total;$('prev').disabled=data.offset<=0;$('next').disabled=!data.has_more}
$('prev').onclick=()=>loadResults(Math.max(0,currentOffset-PAGE_SIZE));$('next').onclick=()=>loadResults(currentOffset+PAGE_SIZE);
$('cancel').onclick=async()=>{if(!currentJobId)return;$('cancel').disabled=true;try{const job=await api('/api/jobs/'+currentJobId+'/cancel',{method:'POST'});renderJob(job)}catch(e){$('jobMessage').textContent=e.message}finally{$('cancel').disabled=false}};
$('form').addEventListener('submit',async e=>{e.preventDefault();switchWorkspace('crawl');enableResearchWorkspaces(false);$('submit').disabled=true;$('submit').textContent='Starting…';$('results').replaceChildren();$('summary').classList.remove('show');$('pagerWrap').classList.remove('show');$('analysisPanel').classList.remove('show');$('aiPanel').classList.remove('show');$('builderPanel').classList.remove('show');analysisData=null;aiResult=null;builderResult=null;try{const job=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({niche:$('niche').value,limit:Number($('limit').value)})});currentJobId=job.id;localStorage.setItem('fiverr-current-job',currentJobId);renderJob(job);clearInterval(pollTimer);pollTimer=setInterval(pollJob,1500);await pollJob()}catch(e){$('jobPanel').classList.add('show');$('jobMessage').textContent=e.message;$('jobMessage').classList.add('error');$('submit').disabled=false;$('submit').textContent='Start background job'}});
async function openExistingJob(job){currentJobId=job.id;renderJob(job);if(['completed','cancelled'].includes(job.status)){showSummary(job);await loadAnalysis();await loadAiConfig();await loadBuilderConfig();await loadResults(0);switchWorkspace('intelligence',false)}else if(['queued','running','cancelling'].includes(job.status)){localStorage.setItem('fiverr-current-job',currentJobId);$('submit').disabled=true;$('submit').textContent='Job running…';if(!pollTimer)pollTimer=setInterval(pollJob,1500)}}
(async()=>{const saved=localStorage.getItem('fiverr-current-job');if(saved){currentJobId=saved;$('submit').disabled=true;$('submit').textContent='Job running…';await pollJob();if($('submit').disabled&&!pollTimer)pollTimer=setInterval(pollJob,1500);return}try{const recent=await api('/api/jobs?limit=1');if(recent.jobs&&recent.jobs.length)await openExistingJob(recent.jobs[0])}catch{}})();
</script></body></html>"""
