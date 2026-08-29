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
from fastapi.staticfiles import StaticFiles
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
    title="GigCraft",
    version="6.0.0",
    description="Premium local studio for Fiverr market research and human-approved gig drafts.",
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
        "health", "health_summary", "health_levels", "health_countries",
        "health_delivery", "health_reasons",
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


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GigCraft Lab</title>
  <meta name="theme-color" content="#f4f3ee">
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,480;8..60,560&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/app.css">
  <link rel="stylesheet" href="/static/lab.css">
</head>
<body data-workspace="crawl">
<div class="scrim" id="scrim"></div>
<div class="app-shell">
  <aside class="sidebar">
    <a class="brand" href="/">
      <span class="mark">G</span>
      <div><strong class="brand-name">GigCraft</strong><small class="brand-sub">Lab</small></div>
    </a>
    <nav class="nav" id="sideNav">
      <a href="/"><span class="ico">✦</span>Studio</a>
      <button type="button" data-workspace="crawl" class="active"><span class="ico">01</span>Crawl</button>
      <button type="button" data-workspace="intelligence" disabled><span class="ico">02</span>Intelligence</button>
      <button type="button" data-workspace="ai" disabled><span class="ico">03</span>Audit</button>
      <button type="button" data-workspace="builder" disabled><span class="ico">04</span>Builder</button>
      <button type="button" data-workspace="raw" disabled><span class="ico">05</span>Source</button>
    </nav>
    <div class="side-foot">
      <div class="status-row"><span class="dot on"></span><span>Private workspace</span></div>
    </div>
  </aside>
  <div class="stage">
    <header class="top">
      <button class="menu-btn" id="menuBtn" type="button" aria-label="Open menu">☰</button>
      <div class="top-title">Market intelligence</div>
    </header>
    <main class="canvas wide wrap">
      <div class="page-kicker">Research workspace</div>
      <h1 class="page-title">See the market, then write the gig.</h1>
      <p class="lead">Crawl public listings, read the patterns, optionally audit with AI, and generate a draft that still needs your approval.</p>

      <form id="form" class="search-card composer workspace-crawl">
        <div><label for="niche">Niche</label><input id="niche" value="Looker Studio" minlength="2" maxlength="100" required></div>
        <div><label for="limit">Gigs</label><select id="limit"><option>3</option><option selected>5</option><option>10</option><option>25</option><option>50</option><option>100</option><option>250</option><option>500</option></select></div>
        <button id="submit" type="submit">Start crawl</button>
      </form>
      <p class="fine workspace-crawl">AI stays off until you ask. Dry run is the default and costs nothing. Drafts are never published to Fiverr.</p>

      <nav id="workspaceNav" class="workspace-nav" aria-label="Workspace modules">
        <button type="button" data-workspace="crawl" class="active"><span>01</span>Crawl</button>
        <button type="button" data-workspace="intelligence" disabled><span>02</span>Intelligence</button>
        <button type="button" data-workspace="ai" disabled><span>03</span>Audit</button>
        <button type="button" data-workspace="builder" disabled><span>04</span>Builder</button>
        <button type="button" data-workspace="raw" disabled><span>05</span>Source</button>
      </nav>

      <section id="jobPanel" class="job-panel workspace-crawl">
        <div class="job-top"><div><h2 id="jobTitle">Crawl</h2><div id="jobId" class="job-id"></div><span id="stage" class="stage">queued</span></div><button id="cancel" class="danger" type="button">Cancel</button></div>
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
        <div class="analysis-head"><div><h2>Market intelligence</h2><p id="analysisMeta">Deterministic analytics · No LLM</p></div><a id="analysisCsv" class="button secondary" href="#">Download CSV</a></div>
        <div id="analysisTabs" class="tabs">
          <button type="button" data-tab="overview" class="active">Overview</button>
          <button type="button" data-tab="health" class="active" style="background:var(--green);color:white">Health ★</button>
          <button type="button" data-tab="rankings">Rankings</button>
          <button type="button" data-tab="movement">Movement</button>
          <button type="button" data-tab="keywords">Keywords</button>
          <button type="button" data-tab="clusters">Clusters</button>
          <button type="button" data-tab="pricing">Pricing</button>
          <button type="button" data-tab="packages">Packages</button>
          <button type="button" data-tab="competitors">Competitors</button>
          <button type="button" data-tab="reviews">Reviews</button>
          <button type="button" data-tab="gaps">Gaps</button>
        </div>
        <div id="analysisContent" class="analysis-content"></div>
      </section>

      <section id="aiPanel" class="ai-panel workspace-ai">
        <div class="ai-head"><div><h2>Semantic audit</h2><p>Structured, evidence-first, cached</p></div><span id="aiKeyState" class="ai-state">Checking configuration…</span></div>
        <div class="ai-controls">
          <div><label for="aiMode">Mode</label><select id="aiMode"><option value="dry_run" selected>Dry run — $0</option><option value="test">Tiny live test</option><option value="standard">Standard audit</option><option value="deep">Deep audit</option></select></div>
          <div><label for="aiMaxGigs">Max gigs</label><select id="aiMaxGigs"><option>1</option><option>5</option><option selected>10</option><option>15</option><option>25</option></select></div>
          <div><label for="ownGigUrl">Your gig URL — optional</label><input id="ownGigUrl" placeholder="https://www.fiverr.com/user/your-gig"></div>
          <button id="runAi" type="button">Run audit</button>
        </div>
        <div class="security-note">Start with dry run. Live modes need a rotated <code>OPENROUTER_API_KEY</code>. The key is never stored or returned.</div>
        <div id="aiProgress" class="ai-progress"><div class="progress-track"><div id="aiProgressBar" class="progress-bar"></div></div><p id="aiProgressText" class="job-message"></p></div>
        <div id="aiResults" class="ai-results">
          <div id="aiTabs" class="tabs"><button type="button" data-ai-tab="ai_overview" class="active">Overview</button><button type="button" data-ai-tab="intents">Intent</button><button type="button" data-ai-tab="scores">Scores</button><button type="button" data-ai-tab="similarity">Similarity</button><button type="button" data-ai-tab="synthesis">Synthesis</button><button type="button" data-ai-tab="evidence">Evidence</button><button type="button" data-ai-tab="usage">Usage</button></div>
          <div id="aiContent" class="analysis-content"></div>
        </div>
      </section>

      <section id="builderPanel" class="builder-panel workspace-builder">
        <div class="builder-head"><div><h2>Gig builder</h2><p>Evidence-led draft · human approval required</p></div><div class="approval"><span id="builderStatus">Dry run available</span><button id="approveDraft" class="secondary" type="button" style="display:none">Approve draft</button></div></div>
        <div class="builder-controls">
          <div><label for="builderMode">Mode</label><select id="builderMode"><option value="dry_run" selected>Dry run — $0</option><option value="test">Tiny live draft</option><option value="standard">Standard draft</option><option value="deep">Deep refine</option></select></div>
          <div><label for="builderTargetUrl">Existing gig URL — optional</label><input id="builderTargetUrl" placeholder="https://www.fiverr.com/user/gig"></div>
          <div><label for="builderBuyer">Target buyer</label><input id="builderBuyer" placeholder="e.g. ecommerce marketing teams"></div>
          <div><label for="builderPositioning">Positioning goal</label><input id="builderPositioning" placeholder="e.g. premium GA4 + dashboard specialist"></div>
          <div><label for="builderTone">Tone</label><select id="builderTone"><option>professional</option><option>consultative</option><option>technical</option><option>friendly</option><option>premium</option></select></div>
          <div><label for="builderPricing">Pricing</label><select id="builderPricing"><option value="market_aligned">Market aligned</option><option value="budget">Budget entry</option><option value="premium">Premium</option></select></div>
        </div>
        <div class="builder-actions"><button id="runBuilder" type="button">Build draft</button><a id="downloadDraft" class="button secondary" href="#" style="display:none">Download Markdown</a></div>
        <div class="security-note">Generated assets remain drafts and are never posted automatically.</div>
        <div id="builderProgress" class="ai-progress"><div class="progress-track"><div id="builderProgressBar" class="progress-bar"></div></div><p id="builderProgressText" class="job-message"></p></div>
        <div id="builderResults" class="ai-results"><div id="builderTabs" class="tabs"><button type="button" data-builder-tab="draft" class="active">Final gig</button><button type="button" data-builder-tab="packages">Packages</button><button type="button" data-builder-tab="faq">FAQ</button><button type="button" data-builder-tab="visuals">Visuals</button><button type="button" data-builder-tab="compliance">Compliance</button><button type="button" data-builder-tab="evidence">Evidence</button><button type="button" data-builder-tab="comparison">Before/After</button><button type="button" data-builder-tab="builder_usage">Usage</button></div><div id="builderContent" class="analysis-content"></div></div>
      </section>

      <div class="raw-header workspace-raw"><div><span class="section-kicker">Source records</span><h2>Raw gig data</h2></div><p>Every extracted section, kept for inspection and export.</p></div>
      <div id="pagerWrap" class="pager-wrap workspace-raw"><span id="pagerInfo"></span><div class="pager"><button id="prev" class="secondary" type="button">Previous</button><button id="next" class="secondary" type="button">Next</button></div></div>
      <section id="results" class="results workspace-raw"></section>
      <footer class="lab-foot">Outputs are drafts for human review. GigCraft never auto-publishes, copies competitor text, or claims access to Fiverr private metrics.</footer>
    </main>
  </div>
</div>
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
function renderHealth(root){
  const h=analysisData.market_health||{}; const s=h.summary||{};
  const intro=el('div','analysis-note','Active vs Dead analysis for keyword \"'+(analysisData.niche||'')+'\". Active = fetch success. Dead = fetch failed OR no reviews + offline + old delivery. Data from sampled gigs + estimated total from Fiverr total results.');
  root.appendChild(intro);
  const g=el('div','analytics-grid');
  g.appendChild(analyticsCard('Total Fiverr Results',s.total_fiverr_results,'Fiverr shows this number'));
  g.appendChild(analyticsCard('Sampled Gigs',s.sampled_gigs,'We crawled this many'));
  g.appendChild(analyticsCard('Active Gigs (Success)',s.active_gigs,'Fetch success = alive'));
  g.appendChild(analyticsCard('Dead Fetch Failed',s.dead_fetch_failed,'404 / paused / deleted'));
  g.appendChild(analyticsCard('Online Now',s.online_now,'Seller online badge'));
  g.appendChild(analyticsCard('Offline',s.offline));
  g.appendChild(analyticsCard('With Reviews',s.with_reviews));
  g.appendChild(analyticsCard('No Reviews (Dead Risk)',s.no_reviews));
  g.appendChild(analyticsCard('Fully Active',s.fully_active,'Online + Recent <=30d'));
  g.appendChild(analyticsCard('No Activity Dead',s.no_activity_dead,'No reviews + offline + old'));
  g.appendChild(analyticsCard('Recent 7d',s.recent_7d,'Last delivery <=7 days'));
  g.appendChild(analyticsCard('Recent 30d',s.recent_30d));
  g.appendChild(analyticsCard('Dormant 90d+',s.dormant_90d_plus,'>90 days'));
  g.appendChild(analyticsCard('Unknown Delivery',s.unknown_delivery));
  g.appendChild(analyticsCard('Active Rate %',s.active_rate_pct!=null?s.active_rate_pct+'%':'—'));
  g.appendChild(analyticsCard('Online Rate %',s.online_rate_pct!=null?s.online_rate_pct+'%':'—'));
  g.appendChild(analyticsCard('Est. Total Active',s.estimated_total_active,'total_fiverr * active_rate'));
  g.appendChild(analyticsCard('Est. Total Dead',s.estimated_total_dead_no_activity));
  root.appendChild(g);

  const comp=block(root,'Price Comparison: Active vs Dead');
  const pc=h.price_comparison||{};
  renderTable(comp,[
    {segment:'Active gigs',...pc.active},
    {segment:'Dead / No Activity',...pc.dead_no_activity},
    {segment:'Online Now',...pc.online},
    {segment:'No Reviews',...pc.no_reviews}
  ],[['segment','Segment'],['count','Count'],['min','Min'],['median','Median'],['mean','Mean'],['max','Max']]);

  const del=block(root,'Last Delivery Buckets'); renderBars(del,h.delivery_buckets,'label','count');
  const reasons=block(root,'Dead Reasons'); renderTable(reasons,h.dead_reasons,[['reason','Reason'],['count','Count'],['share_pct','Share %']],50);
  const byLevel=block(root,'Active/Dead by Seller Level'); renderTable(byLevel,h.by_level,[['level','Level'],['total','Total'],['active','Active'],['online','Online'],['no_reviews','No Reviews'],['no_activity_dead','Dead No Activity'],['fully_active','Fully Active'],['recent_30d','Recent 30d'],['median_price','Median $'],['share_pct','Share %']],50);
  const byCountry=block(root,'By Country'); renderTable(byCountry,h.by_country,[['country','Country'],['total','Total'],['active','Active'],['online','Online'],['no_reviews','No Reviews'],['recent_30d','Recent 30d'],['median_price','Median $'],['share_pct','Share %']],50);
  const details=block(root,'Gig Health Details - Full List'); renderTable(details,h.details,[['global_position','Rank'],['title','Gig'],['seller_level','Level'],['price','Price'],['review_count','Reviews'],['seller_online','Online'],['last_delivery_raw','Last Delivery'],['last_delivery_days','Days'],['health_status','Health'],['dead_reason','Dead Reason'],['url','Link']],200);
}
function renderAnalysisTab(tab){activeAnalysisTab=tab;document.querySelectorAll('#analysisTabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));$('analysisCsv').href='/api/jobs/'+currentJobId+'/analysis/'+tab+'.csv';const root=$('analysisContent');root.replaceChildren();if(!analysisData){root.appendChild(el('div','empty','Analysis not loaded'));return}const renders={overview:renderOverview,health:renderHealth,rankings:renderRankings,movement:renderMovement,keywords:renderKeywords,clusters:renderClusters,pricing:renderPricing,packages:renderPackages,competitors:renderCompetitors,reviews:renderReviews,gaps:renderGaps};(renders[tab]||renderOverview)(root)}
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
function renderAiUsage(root){const u=aiResult.usage||{};const g=el('div','score-grid');for(const [label,key] of [['Prompt tokens','prompt_tokens'],['Completion tokens','completion_tokens'],['Total tokens','total_tokens'],['Actual cost USD','actual_cost_usd'],['API calls','api_calls'],['Cache hits','cache_hits'],['Cost cap','max_cost_usd']])g.appendChild(analyticsCard(label,u[key]));root.appendChild(g);const m=block(root,'Models');for(const [k,v] of Object.entries(aiResult.models||{}))m.appendChild(el('div','model-row',k+': '+v));root.appendChild(el('div','analysis-note','API key is not included in this result, database, logs or exports.'))}

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
</script>
<script>
document.getElementById('menuBtn').onclick=()=>document.body.classList.add('nav-open');
document.getElementById('scrim').onclick=()=>document.body.classList.remove('nav-open');
document.querySelectorAll('#sideNav button[data-workspace]').forEach(button=>{
  button.onclick=()=>{if(!button.disabled){const target=document.querySelector('#workspaceNav button[data-workspace="'+button.dataset.workspace+'"]');if(target&&!target.disabled)target.click();document.body.classList.remove('nav-open')}}
});
const _switch=switchWorkspace;
switchWorkspace=function(name,scroll=true){
  _switch(name,scroll);
  document.querySelectorAll('#sideNav button[data-workspace]').forEach(b=>b.classList.toggle('active',b.dataset.workspace===name));
};
const _enable=enableResearchWorkspaces;
enableResearchWorkspaces=function(enabled=true){
  _enable(enabled);
  document.querySelectorAll('#sideNav button[data-workspace]').forEach(button=>{if(button.dataset.workspace!=='crawl')button.disabled=!enabled});
};
</script>
</body></html>"""

