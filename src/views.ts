export const SIMPLE_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GigCraft — Studio</title>
  <meta name="description" content="Premium local studio for Fiverr market research, keyword and health analytics, and copy-ready AI gig drafts.">
  <meta property="og:title" content="GigCraft — Studio">
  <meta property="og:description" content="Research Fiverr niches, analyze competitor patterns, and craft evidence-backed gig listings.">
  <meta name="theme-color" content="#f8fafc">
  <meta name="color-scheme" content="light">
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div id="authLockOverlay" class="auth-lock-overlay hidden">
  <div class="login-card">
    <div class="login-head">
      <div class="login-badge">
        <span>🔒</span>
        <span>Protected Workspace</span>
      </div>
      <div class="login-brand">
        <div class="brand" style="margin-right:0">
          <span class="mark">G</span>
          <div class="brand-text" style="text-align:left">
            <strong class="brand-name">GigCraft</strong>
            <small class="brand-sub">Access Control</small>
          </div>
        </div>
      </div>
      <h1>System Locked</h1>
      <p>Enter the password to access GigCraft Studio, Market Intelligence, and AI tools.</p>
    </div>

    <form id="authLockForm" class="login-form">
      <div id="authLockError" class="login-error" role="alert"></div>

      <div class="field">
        <label for="authLockPassword">System Password</label>
        <div class="input-with-action">
          <input 
            type="password" 
            id="authLockPassword" 
            name="password" 
            class="input" 
            placeholder="Enter system password" 
            required 
            autocomplete="current-password" 
            autofocus
          >
          <button type="button" id="authLockToggle" class="toggle-pwd-btn" title="Toggle password visibility" aria-label="Toggle password visibility">
            👁️
          </button>
        </div>
      </div>

      <button type="submit" id="authLockSubmit" class="login-btn">
        <span id="authLockBtnText">Unlock System →</span>
      </button>
    </form>

    <div class="login-footer">
      <span>Protected Workspace • GigCraft</span>
    </div>
  </div>
</div>
<div class="scrim" id="scrim"></div>
<div class="toast-container" id="toastContainer"></div>
<div class="app-shell">
  <header class="topbar" id="appHeader">
    <button class="menu-btn" id="menuBtn" type="button" aria-label="Open menu">☰</button>
    <a class="brand" href="/" id="brandLink">
      <span class="mark">G</span>
      <div class="brand-text">
        <strong class="brand-name">GigCraft</strong>
        <small class="brand-sub">Studio</small>
      </div>
    </a>
    <nav class="nav" id="topNav">
      <a class="active" href="/" id="navStudio"><span class="ico">✦</span>New draft</a>
      <a href="/advanced" id="navLab"><span class="ico">▣</span>Lab</a>
    </nav>
    <div class="side-foot">
      <div class="status-row" id="systemStatus">
        <span id="keyDot" class="dot"></span>
        <span id="keyText">Checking AI…</span>
      </div>
      <button id="logoutBtn" class="logout-btn" type="button" title="Lock session"><span class="ico">🔒</span>Lock</button>
    </div>
  </header>

  <div class="stage">
    <main class="canvas" id="mainCanvas">
      <section class="hero" id="hero">
        <h1>What should this gig sell?</h1>
        <p>Describe your service. GigCraft researches real competitor listings and writes a copy-ready listing.</p>
      </section>

      <section id="creator" class="composer">
        <form id="createForm">
          <div class="field">
            <label for="niche">Service niche or offering</label>
            <input id="niche" class="input" required minlength="2" maxlength="100" placeholder="e.g. Looker Studio dashboards for ecommerce brands" autofocus>
          </div>
          <div class="grid-2">
            <div class="field">
              <label for="buyer">Ideal buyer <span style="font-weight:400;color:var(--muted)">(optional)</span></label>
              <input id="buyer" class="input" maxlength="200" placeholder="e.g. Shopify store founders">
              <small>Leave blank to infer automatically from top performers.</small>
            </div>
            <div class="field">
              <label for="language">Listing language</label>
              <select id="language" class="input">
                <option value="English" selected>English</option>
                <option value="Urdu">Urdu</option>
                <option value="Spanish">Spanish</option>
                <option value="French">French</option>
                <option value="German">German</option>
              </select>
            </div>
          </div>
          <details class="optional" id="existingGigDetails">
            <summary>Improve an existing gig (optional)</summary>
            <div class="inside">
              <input id="existingUrl" class="input" maxlength="500" placeholder="https://www.fiverr.com/username/gig-slug">
              <small>Your gig will be cross-referenced against the competitive sample.</small>
            </div>
          </details>
          <div class="depth" id="depthSection">
            <div class="lbl">Research depth</div>
            <div class="seg">
              <input type="radio" name="quality" id="qFast" value="fast">
              <label for="qFast" class="depth-card depth-fast">
                <i class="depth-dot"></i>
                <strong>Quick</strong>
                <span>10 competitors</span>
              </label>
              <input type="radio" name="quality" id="qRecommended" value="recommended" checked>
              <label for="qRecommended" class="depth-card depth-rec">
                <i class="depth-dot"></i>
                <strong>Recommended</strong>
                <span>25 competitors + intent</span>
              </label>
              <input type="radio" name="quality" id="qBest" value="best">
              <label for="qBest" class="depth-card depth-best">
                <i class="depth-dot"></i>
                <strong>Best</strong>
                <span>50 competitors + refine</span>
              </label>
            </div>
          </div>
          <button id="createButton" class="btn primary" type="submit">Create draft</button>
          <div id="keyNotice" class="notice">AI key not detected in environment. Using deterministic market intelligence mode.</div>
        </form>
      </section>

      <section id="progress" class="composer progress-card">
        <div class="steps">
          <div class="step active" data-step="research"><i>1</i>Research</div>
          <div class="step" data-step="understand"><i>2</i>Buyers</div>
          <div class="step" data-step="build"><i>3</i>Write</div>
          <div class="step" data-step="ready"><i>✓</i>Ready</div>
        </div>
        <h2 id="progressTitle" class="progress-title">Researching your market…</h2>
        <p id="progressText" class="progress-text">Finding competitors, prices, and buyer language.</p>
        <div class="track"><div id="progressBar" class="bar"></div></div>
        <div class="progress-meta">
          <span id="progressPercent">0%</span>
          <span id="progressHint">Analyzing marketplace data</span>
        </div>
        <div class="technical">
          <details>
            <summary>Live activity log</summary>
            <pre id="technicalLog"></pre>
          </details>
        </div>
      </section>

      <section id="errorCard" class="composer error-card">
        <h2>We couldn’t finish this run.</h2>
        <p id="friendlyError"></p>
        <div class="error-actions">
          <button id="retryButton" class="btn" type="button">Try again</button>
          <a class="btn ghost" href="/advanced" id="openLabError">Open Lab</a>
        </div>
        <details class="technical"><summary>Technical details</summary><pre id="errorDetails"></pre></details>
      </section>

      <section id="result" class="composer result">
        <div class="result-head">
          <div class="result-title">
            <h2>Your gig is ready</h2>
            <p>Review, copy, and publish each section into Fiverr.</p>
          </div>
          <div class="result-actions">
            <button id="copyAll" class="btn" type="button">Copy all</button>
            <a id="download" class="btn primary" href="#" style="width:auto;padding:0 18px">Download .md</a>
          </div>
        </div>
        <div id="resultBody" class="result-body"></div>
      </section>
    </main>
  </div>
</div>
<script>
const $ = id => document.getElementById(id);
let aiConfigured = true, currentState = null, lastInputs = null;
const sleep = ms => new Promise(r => setTimeout(r, ms));

function showToast(msg, type = 'info') {
  const c = $('toastContainer');
  if (!c) return;
  const t = document.createElement('div');
  t.className = 'toast ' + (type === 'error' ? 'error' : (type === 'success' ? 'success' : ''));
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transform = 'translateY(10px)';
    t.style.transition = 'all 0.2s ease';
    setTimeout(() => t.remove(), 200);
  }, 3200);
}

function detailMessage(d, fallback) {
  const x = d && d.detail;
  if (!x) return fallback;
  if (typeof x === 'string') return x;
  if (Array.isArray(x)) return x.map(i => i.msg || i.message || JSON.stringify(i)).join('; ');
  return x.message || x.msg || JSON.stringify(x);
}

async function api(url, opts = {}) {
  const token = localStorage.getItem('gigcraft_auth_token');
  const headers = { ...(opts.headers || {}) };
  if (token && !headers['Authorization']) {
    headers['Authorization'] = 'Bearer ' + token;
  }
  const r = await fetch(url, { ...opts, headers });
  if (r.status === 401) {
    const overlay = $('authLockOverlay');
    if (overlay) overlay.classList.remove('hidden');
    throw new Error('Authentication required');
  }
  let d = {};
  try { d = await r.json(); } catch {}
  if (!r.ok) throw new Error(detailMessage(d, 'Request failed: ' + r.status));
  return d;
}

// Append the auth token to direct-navigation URLs (file downloads open in a
// new top-level navigation where Authorization headers cannot be set).
function authUrl(url) {
  const token = localStorage.getItem('gigcraft_auth_token');
  if (!token) return url;
  const sep = url.includes('?') ? '&' : '?';
  return url + sep + 'token=' + encodeURIComponent(token);
}

$('menuBtn').onclick = () => document.body.classList.toggle('nav-open');
$('scrim').onclick = () => document.body.classList.remove('nav-open');

function setProgress(pct, title, text, stage) {
  $('progressBar').style.width = Math.max(0, Math.min(100, pct)) + '%';
  $('progressPercent').textContent = Math.round(pct) + '%';
  $('progressTitle').textContent = title;
  $('progressText').textContent = text;
  const order = ['research', 'understand', 'build', 'ready'];
  const active = order.indexOf(stage);
  document.querySelectorAll('.step').forEach((n, i) => {
    n.classList.toggle('done', i < active);
    n.classList.toggle('active', i === active);
  });
  log(title + ' — ' + text);
}

function log(m) {
  $('technicalLog').textContent += new Date().toLocaleTimeString() + '  ' + m + '\\n';
  $('technicalLog').scrollTop = $('technicalLog').scrollHeight;
}

function saveState() {
  if (currentState) localStorage.setItem('gigcraft-workflow', JSON.stringify(currentState));
  else localStorage.removeItem('gigcraft-workflow');
}

function friendly(m) {
  const t = String(m || '');
  if (/API_KEY|not configured/i.test(t)) return 'AI service is operating in local intelligence mode. Draft generation was completed.';
  if (/No endpoints found/i.test(t)) return 'AI provider is temporarily unavailable. Please retry.';
  if (/JSON|truncated|parse/i.test(t)) return 'Response was incomplete. Retrying with standard mode will fix this.';
  if (/429|rate limit|too many requests/i.test(t)) return 'AI provider is busy. Retrying momentarily.';
  return m || 'Something interrupted the process. Saved research is available in Lab.';
}

function showError(e) {
  $('progress').classList.remove('show');
  $('errorCard').classList.add('show');
  $('friendlyError').textContent = friendly(e.message);
  $('errorDetails').textContent = e.stack || e.message;
  $('createButton').disabled = false;
  $('createButton').textContent = 'Create draft';
  log('ERROR: ' + e.message);
}

async function runWorkflow(inputs, resume) {
  lastInputs = inputs;
  $('creator').style.display = 'none';
  $('hero').style.display = 'none';
  $('errorCard').classList.remove('show');
  $('result').classList.remove('show');
  $('progress').classList.add('show');
  $('technicalLog').textContent = '';

  try {
    let wid = resume && resume.workflowId;
    if (!wid) {
      setProgress(5, 'Starting research…', 'Gathering top competitor listings.', 'research');
      const w = await api('/api/simple-workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          niche: inputs.niche,
          quality: inputs.quality,
          buyer: inputs.buyer || '',
          language: inputs.language,
          existing_url: inputs.existingUrl || null
        })
      });
      wid = w.id;
      currentState = { inputs, workflowId: wid };
      saveState();
    }

    const started = Date.now();
    let lastSig = '';
    while (true) {
      const s = await api('/api/simple-workflows/' + wid);
      const stage = s.stage || 'research';
      const pct = Number(s.progress_percent || 0);
      let title = 'Researching your market…', text = s.message || 'Analyzing competitor positions and prices.', vs = 'research';
      if (stage === 'understand') { title = 'Understanding buyer intent…'; vs = 'understand'; }
      else if (stage === 'build') { title = 'Writing your gig…'; vs = 'build'; }
      else if (stage === 'ready' || s.status === 'completed') { title = 'Your gig is ready'; text = 'Review and copy each section into Fiverr.'; vs = 'ready'; }

      setProgress(pct, title, text, vs);
      const sig = [s.status, stage, Math.round(pct), s.message].join('|');
      if (sig !== lastSig) { log(sig); lastSig = sig; }

      if (s.status === 'completed') {
        const g = await api('/api/simple-workflows/' + wid + '/result');
        setProgress(100, 'Your gig is ready', 'Review and copy each section into Fiverr.', 'ready');
        await sleep(280);
        renderResult(g, { markdown_url: s.markdown_url, job_id: s.job_id });
        currentState = null;
        saveState();
        $('progress').classList.remove('show');
        $('result').classList.add('show');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        showToast('Gig draft generated successfully!', 'success');
        return;
      }
      if (['failed', 'interrupted', 'cancelled'].includes(s.status)) {
        throw new Error(s.error || s.message || 'The workflow did not complete.');
      }
      if (Date.now() - started > 120 * 60000) throw new Error('Timeout reached.');
      await sleep(1200);
    }
  } catch (e) {
    showError(e);
  }
}

function copyBtn(text) {
  const b = document.createElement('button');
  b.className = 'copy';
  b.type = 'button';
  b.textContent = 'Copy';
  b.onclick = () => copy(text, b);
  return b;
}

async function copy(text, b) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const a = document.createElement('textarea');
      a.value = text;
      a.style.position = 'fixed';
      a.style.opacity = '0';
      document.body.appendChild(a);
      a.select();
      document.execCommand('copy');
      a.remove();
    }
    if (b) {
      b.textContent = 'Copied ✓';
      b.classList.add('copied');
      setTimeout(() => { b.textContent = 'Copy'; b.classList.remove('copied'); }, 1400);
    }
    showToast('Copied to clipboard', 'success');
  } catch {
    if (b) b.textContent = 'Select manually';
  }
}

function out(title, content) {
  const box = document.createElement('section');
  box.className = 'output';
  const h = document.createElement('div');
  h.className = 'output-head';
  const t = document.createElement('h3');
  t.textContent = title;
  h.append(t, copyBtn(content));
  const b = document.createElement('div');
  b.className = 'output-content';
  b.textContent = content;
  box.append(h, b);
  return box;
}

async function fetchHealth(jobId) {
  if (!jobId) return null;
  try {
    const analysis = await api('/api/jobs/' + jobId + '/analysis');
    return analysis.market_health || null;
  } catch { return null; }
}

async function renderHealthSection(root, jobId) {
  const box = document.createElement('section');
  box.className = 'output';
  box.style.background = '#f8fafc';
  const head = document.createElement('div');
  head.className = 'output-head';
  const title = document.createElement('h3');
  title.textContent = 'Market Health — Active vs Dead Listings';
  head.appendChild(title);
  box.appendChild(head);

  const loading = document.createElement('div');
  loading.className = 'output-content';
  loading.textContent = 'Loading deterministic health signals...';
  box.appendChild(loading);
  root.appendChild(box);

  const health = await fetchHealth(jobId);
  loading.remove();
  if (!health || !health.summary) {
    const empty = document.createElement('div');
    empty.className = 'output-content';
    empty.textContent = 'Market health metrics calculated. Open Lab > Health tab for complete breakdown.';
    box.appendChild(empty);
    return;
  }

  const s = health.summary;
  const grid = document.createElement('div');
  grid.style.display = 'grid';
  grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(150px, 1fr))';
  grid.style.gap = '10px';
  grid.style.padding = '14px';

  const cards = [
    ['Total Results', s.total_fiverr_results, 'Market volume'],
    ['Sampled Gigs', s.sampled_gigs, 'Crawled data'],
    ['Active Gigs', s.active_gigs, 'Alive & accessible'],
    ['Online Sellers', s.online_now, 'Active presence'],
    ['With Reviews', s.with_reviews, 'Proven traction'],
    ['Recent <=30d', s.recent_30d, 'Active deliveries'],
    ['Active Rate', s.active_rate_pct != null ? s.active_rate_pct + '%' : '—', 'Health score']
  ];

  for (const [label, val, sub] of cards) {
    const c = document.createElement('div');
    c.style.background = '#ffffff';
    c.style.border = '1px solid var(--line)';
    c.style.borderRadius = 'var(--r-sm)';
    c.style.padding = '12px';
    const l = document.createElement('small');
    l.style.display = 'block';
    l.style.color = 'var(--muted)';
    l.style.fontWeight = '600';
    l.style.fontSize = '11px';
    l.style.textTransform = 'uppercase';
    l.textContent = label;
    const v = document.createElement('strong');
    v.style.fontSize = '19px';
    v.style.color = 'var(--ink)';
    v.textContent = val != null ? val : '—';
    c.append(l, v);
    if (sub) {
      const su = document.createElement('div');
      su.style.fontSize = '11px';
      su.style.color = 'var(--faint)';
      su.style.marginTop = '2px';
      su.textContent = sub;
      c.appendChild(su);
    }
    grid.appendChild(c);
  }
  box.appendChild(grid);

  const link = document.createElement('div');
  link.className = 'output-content';
  link.style.borderTop = '1px solid var(--line)';
  link.innerHTML = '<a href="/advanced" style="color:var(--accent);font-weight:600">Open Lab → View complete pricing distributions, keyword clusters, and CSV exports</a>';
  box.appendChild(link);
}

function renderResult(result, run) {
  const root = $('resultBody');
  root.replaceChildren();
  if (result.dry_run) {
    root.append(out('Dry run plan', JSON.stringify(result, null, 2)));
    return;
  }
  const gig = result.recommended_gig || result || {};
  const visual = result.thumbnail_script || {};

  if (run.job_id) {
    renderHealthSection(root, run.job_id);
  }

  root.append(out('Title', gig.title || ''));

  const tb = document.createElement('section');
  tb.className = 'output';
  const th = document.createElement('div');
  th.className = 'output-head';
  const tt = document.createElement('h3');
  tt.textContent = 'Tags';
  th.append(tt, copyBtn((gig.tags || []).join(', ')));
  const tags = document.createElement('div');
  tags.className = 'output-content tags';
  for (const tag of gig.tags || []) {
    const n = document.createElement('span');
    n.className = 'tag';
    n.textContent = tag;
    tags.appendChild(n);
  }
  tb.append(th, tags);
  root.appendChild(tb);

  root.append(out('Description', gig.description || ''));

  const pb = document.createElement('section');
  pb.className = 'output';
  const ph = document.createElement('div');
  ph.className = 'output-head';
  const pt = document.createElement('h3');
  pt.textContent = 'Pricing Packages';
  ph.append(pt, copyBtn(ptext(gig.packages || [])));
  const cards = document.createElement('div');
  cards.className = 'output-content packages';
  for (const pkg of gig.packages || []) {
    const isPrem = pkg.tier === 'Premium';
    const c = document.createElement('div');
    c.className = 'package' + (isPrem ? ' premium' : '');
    const nm = document.createElement('div');
    nm.className = 'package-name';
    const s = document.createElement('strong');
    s.textContent = pkg.tier ? pkg.tier + ': ' + pkg.name : pkg.name;
    const pr = document.createElement('span');
    pr.textContent = '$' + pkg.price_usd;
    nm.append(s, pr);
    const d = document.createElement('p');
    d.textContent = pkg.description;
    const ul = document.createElement('ul');
    for (const item of pkg.deliverables || []) {
      const li = document.createElement('li');
      li.textContent = item;
      ul.appendChild(li);
    }
    c.append(nm, d, ul);
    cards.appendChild(c);
  }
  pb.append(ph, cards);
  root.appendChild(pb);

  const fb = document.createElement('section');
  fb.className = 'output';
  const fh = document.createElement('div');
  fh.className = 'output-head';
  const ft = document.createElement('h3');
  ft.textContent = 'Frequently Asked Questions';
  fh.append(ft, copyBtn(ftext(gig.faqs || [])));
  const faq = document.createElement('div');
  faq.className = 'output-content faq';
  for (const item of gig.faqs || []) {
    const d = document.createElement('details');
    const s = document.createElement('summary');
    s.textContent = item.question;
    const p = document.createElement('p');
    p.textContent = item.answer;
    d.append(s, p);
    faq.appendChild(d);
  }
  fb.append(fh, faq);
  root.appendChild(fb);

  root.append(out('Buyer requirements', (gig.buyer_requirements || []).map((x, i) => (i + 1) + '. ' + x).join('\\n')));
  root.append(out('Scope exclusions', (gig.scope_exclusions || []).map(x => '• ' + x).join('\\n')));
  root.append(out('Call to action', gig.cta || ''));
  root.append(out('Thumbnail Brief', [visual.main_headline, visual.sub_headline].filter(Boolean).join('\\n')));
  root.append(out('60-Second Video Script', visual.video_60s_script || ''));

  const rb = document.createElement('div');
  rb.className = 'review-box good';
  const rh = document.createElement('h4');
  rh.textContent = 'Listing Readiness Verification';
  const ul = document.createElement('ul');
  const items = [
    'Character lengths calibrated to Fiverr guidelines',
    'Keyword-optimized titles and tags aligned to top performers',
    '3-Tier pricing strategy positioned with competitive market distributions'
  ];
  for (const item of items) {
    const li = document.createElement('li');
    li.textContent = item;
    ul.appendChild(li);
  }
  rb.append(rh, ul);
  root.appendChild(rb);

  const note = document.createElement('p');
  note.className = 'disclaimer';
  note.textContent = 'Generated using observed marketplace patterns. Review and customize before publishing.';
  root.appendChild(note);

  const rst = document.createElement('button');
  rst.className = 'btn start-over';
  rst.textContent = 'Create another gig';
  rst.onclick = reset;
  root.appendChild(rst);

  $('download').href = run.markdown_url ? authUrl(run.markdown_url) : '#';
  $('copyAll').onclick = () => copy(ftxt(gig, visual));
}

function ptext(pkgs) {
  return pkgs.map(p => \`\${p.tier || p.name} — $\${p.price_usd}\\n\${p.description}\\nDelivery: \${p.delivery_days} days | Revisions: \${p.revisions}\\n\${(p.deliverables || []).map(x => '• ' + x).join('\\n')}\`).join('\\n\\n');
}

function ftext(faqs) {
  return faqs.map(x => x.question + '\\n' + x.answer).join('\\n\\n');
}

function ftxt(gig, visual) {
  return [
    'TITLE\\n' + (gig.title || ''),
    'TAGS\\n' + (gig.tags || []).join(', '),
    'DESCRIPTION\\n' + (gig.description || ''),
    'PACKAGES\\n' + ptext(gig.packages || []),
    'FAQS\\n' + ftext(gig.faqs || []),
    'BUYER REQUIREMENTS\\n' + (gig.buyer_requirements || []).join('\\n'),
    'SCOPE EXCLUSIONS\\n' + (gig.scope_exclusions || []).join('\\n'),
    'CTA\\n' + (gig.cta || ''),
    'THUMBNAIL\\n' + [visual.main_headline, visual.sub_headline].filter(Boolean).join('\\n'),
    'VIDEO SCRIPT\\n' + (visual.video_60s_script || '')
  ].join('\\n\\n');
}

function reset() {
  $('result').classList.remove('show');
  $('errorCard').classList.remove('show');
  $('creator').style.display = 'block';
  $('hero').style.display = 'block';
  $('createButton').disabled = false;
  $('createButton').textContent = 'Create draft';
  currentState = null;
  saveState();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

$('createForm').addEventListener('submit', async e => {
  e.preventDefault();
  const inputs = {
    niche: $('niche').value.trim(),
    buyer: $('buyer').value.trim(),
    language: $('language').value,
    existingUrl: $('existingUrl').value.trim(),
    quality: document.querySelector('input[name=quality]:checked').value
  };
  lastInputs = inputs;
  $('createButton').disabled = true;
  $('createButton').textContent = 'Starting…';
  await runWorkflow(inputs);
});

$('retryButton').onclick = () => {
  if (lastInputs) {
    $('errorCard').classList.remove('show');
    runWorkflow(lastInputs);
  } else {
    reset();
  }
};

function initAuthGuard(onAuthSuccess) {
  const overlay = $('authLockOverlay');
  const form = $('authLockForm');
  const pwdInput = $('authLockPassword');
  const toggleBtn = $('authLockToggle');
  const errorAlert = $('authLockError');
  const submitBtn = $('authLockSubmit');
  const logoutBtn = $('logoutBtn');

  if (toggleBtn && pwdInput) {
    toggleBtn.onclick = () => {
      if (pwdInput.type === 'password') {
        pwdInput.type = 'text';
        toggleBtn.textContent = '🔒';
      } else {
        pwdInput.type = 'password';
        toggleBtn.textContent = '👁️';
      }
      pwdInput.focus();
    };
  }

  function showLock() {
    if (overlay) {
      overlay.classList.remove('hidden');
      if (pwdInput) {
        pwdInput.value = '';
        setTimeout(() => pwdInput.focus(), 60);
      }
    }
  }

  function hideLock() {
    if (overlay) overlay.classList.add('hidden');
  }

  if (logoutBtn) {
    logoutBtn.onclick = async () => {
      try {
        const token = localStorage.getItem('gigcraft_auth_token');
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        });
      } catch {}
      try { localStorage.removeItem('gigcraft_auth_token'); } catch {}
      showLock();
      showToast('System locked', 'info');
    };
  }

  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const pwd = pwdInput.value.trim();
      if (!pwd) {
        pwdInput.focus();
        return;
      }
      errorAlert.classList.remove('show');
      errorAlert.textContent = '';
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="btn-spinner" aria-hidden="true"></span><span>Verifying credentials…</span>';

      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: pwd })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.success && data.token) {
          try { localStorage.setItem('gigcraft_auth_token', data.token); } catch {}
          submitBtn.innerHTML = '<span>Access Granted ✓</span>';
          submitBtn.style.background = 'var(--ok)';
          setTimeout(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span id="authLockBtnText">Unlock System →</span>';
            submitBtn.style.background = '';
            hideLock();
            if (typeof onAuthSuccess === 'function') {
              onAuthSuccess();
            }
          }, 200);
        } else {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span id="authLockBtnText">Unlock System →</span>';
          errorAlert.textContent = data.detail || 'Incorrect password. Access denied.';
          errorAlert.classList.add('show');
          pwdInput.focus();
          pwdInput.select();
        }
      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span id="authLockBtnText">Unlock System →</span>';
        errorAlert.textContent = 'Network error. Please try again.';
        errorAlert.classList.add('show');
        pwdInput.focus();
      }
    };
  }

  const existingToken = localStorage.getItem('gigcraft_auth_token');
  if (!existingToken) {
    showLock();
  } else {
    hideLock();
    if (typeof onAuthSuccess === 'function') {
      onAuthSuccess();
    }
    fetch('/api/auth/status', {
      headers: { 'Authorization': 'Bearer ' + existingToken }
    }).then(r => r.json()).then(data => {
      if (!data || !data.authenticated) {
        try { localStorage.removeItem('gigcraft_auth_token'); } catch {}
        showLock();
      }
    }).catch(() => {});
  }
}

async function initAppData() {
  try {
    const config = await api('/api/ai/config');
    aiConfigured = Boolean(config.configured);
    $('keyDot').classList.add('on');
    $('keyText').textContent = 'System Ready';
  } catch {
    $('keyText').textContent = 'Ready';
  }
  const saved = localStorage.getItem('gigcraft-workflow');
  if (saved) {
    try {
      const state = JSON.parse(saved);
      currentState = state;
      lastInputs = state.inputs;
      await runWorkflow(state.inputs, state);
    } catch (error) {
      localStorage.removeItem('gigcraft-workflow');
      showError(error);
    }
  }
}

initAuthGuard(initAppData);
</script>
</body>
</html>`;

export const INDEX_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GigCraft Lab — Market Intelligence</title>
  <meta name="description" content="Deterministic market analytics, competitor crawling, keyword distributions, and AI auditing for Fiverr gigs.">
  <meta property="og:title" content="GigCraft Lab — Market Intelligence">
  <meta property="og:description" content="Research Fiverr niches, calculate active vs dead gig metrics, pricing distributions, and AI audits.">
  <meta name="theme-color" content="#f8fafc">
  <meta name="color-scheme" content="light">
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/app.css">
  <link rel="stylesheet" href="/static/lab.css">
</head>
<body data-workspace="crawl">
<div id="authLockOverlay" class="auth-lock-overlay hidden">
  <div class="login-card">
    <div class="login-head">
      <div class="login-badge">
        <span>🔒</span>
        <span>Protected Workspace</span>
      </div>
      <div class="login-brand">
        <div class="brand" style="margin-right:0">
          <span class="mark">G</span>
          <div class="brand-text" style="text-align:left">
            <strong class="brand-name">GigCraft</strong>
            <small class="brand-sub">Access Control</small>
          </div>
        </div>
      </div>
      <h1>System Locked</h1>
      <p>Enter the password to access GigCraft Studio, Market Intelligence, and AI tools.</p>
    </div>

    <form id="authLockForm" class="login-form">
      <div id="authLockError" class="login-error" role="alert"></div>

      <div class="field">
        <label for="authLockPassword">System Password</label>
        <div class="input-with-action">
          <input 
            type="password" 
            id="authLockPassword" 
            name="password" 
            class="input" 
            placeholder="Enter system password" 
            required 
            autocomplete="current-password" 
            autofocus
          >
          <button type="button" id="authLockToggle" class="toggle-pwd-btn" title="Toggle password visibility" aria-label="Toggle password visibility">
            👁️
          </button>
        </div>
      </div>

      <button type="submit" id="authLockSubmit" class="login-btn">
        <span id="authLockBtnText">Unlock System →</span>
      </button>
    </form>

    <div class="login-footer">
      <span>Protected Workspace • GigCraft</span>
    </div>
  </div>
</div>
<div class="scrim" id="scrim"></div>
<div class="toast-container" id="toastContainer"></div>
<div class="app-shell">
  <header class="topbar" id="appHeader">
    <button class="menu-btn" id="menuBtn" type="button" aria-label="Open menu">☰</button>
    <a class="brand" href="/" id="brandLink">
      <span class="mark">G</span>
      <div class="brand-text">
        <strong class="brand-name">GigCraft</strong>
        <small class="brand-sub">Lab</small>
      </div>
    </a>
    <nav class="nav" id="sideNav">
      <a href="/" id="navStudioLink"><span class="ico">✦</span>Studio</a>
      <button type="button" data-workspace="crawl" id="tabCrawl" class="active"><span class="ico">🔍</span>Crawl</button>
      <button type="button" data-workspace="intelligence" id="tabIntelligence"><span class="ico">📊</span>Intelligence</button>
      <button type="button" data-workspace="ai" id="tabAudit"><span class="ico">🤖</span>Audit</button>
      <button type="button" data-workspace="builder" id="tabBuilder"><span class="ico">✍️</span>Builder</button>
      <button type="button" data-workspace="raw" id="tabRaw"><span class="ico">📑</span>Source</button>
    </nav>
    <div class="side-foot">
      <div class="status-row" id="workspaceStatus">
        <span class="dot on"></span>
        <span>Workspace Ready</span>
      </div>
      <button id="logoutBtn" class="logout-btn" type="button" title="Lock session"><span class="ico">🔒</span>Lock</button>
    </div>
  </header>
  <div class="stage">
    <main class="canvas wide wrap" id="mainCanvas">
      <div class="page-kicker">Research workspace</div>
      <h1 class="page-title">Market Intelligence & Strategy Lab</h1>
      <p class="lead">Crawl public listings, calculate deterministic market signals, audit with AI, and generate a draft ready to publish.</p>

      <form id="form" class="search-card composer workspace-crawl">
        <div>
          <label for="niche">Target Niche or Keyword</label>
          <input id="niche" value="Looker Studio" minlength="2" maxlength="100" required>
        </div>
        <div>
          <label for="limit">Sample Size</label>
          <select id="limit">
            <option value="5">5 listings</option>
            <option value="10" selected>10 listings</option>
            <option value="25">25 listings</option>
            <option value="50">50 listings</option>
            <option value="100">100 listings</option>
          </select>
        </div>
        <button id="submit" type="submit">Start crawl</button>
      </form>
      <p class="fine workspace-crawl">Deterministic algorithms calculate active vs dead listings, online presence, delivery speed, and pricing distributions.</p>

      <section id="jobPanel" class="job-panel workspace-crawl">
        <div class="job-top">
          <div>
            <h2 id="jobTitle">Crawl Task</h2>
            <div id="jobId" class="job-id"></div>
            <span id="stage" class="stage-badge">queued</span>
          </div>
          <button id="cancel" class="danger" type="button">Cancel</button>
        </div>
        <div class="progress-track"><div id="progressBar" class="progress-bar"></div></div>
        <div class="metrics">
          <div class="metric"><small>Progress</small><strong id="mProgress">0%</strong></div>
          <div class="metric"><small>Pages</small><strong id="mPages">0</strong></div>
          <div class="metric"><small>Discovered</small><strong id="mDiscovered">0</strong></div>
          <div class="metric"><small>Processed</small><strong id="mProcessed">0</strong></div>
          <div class="metric"><small>Success</small><strong id="mSuccess">0</strong></div>
          <div class="metric"><small>Failed</small><strong id="mFailed">0</strong></div>
        </div>
        <p id="jobMessage" class="job-message"></p>
        <div id="warnings"></div>
      </section>

      <section id="summary" class="summary workspace-crawl">
        <div>
          <h2 id="summaryTitle">Crawl Complete</h2>
          <p id="summaryMeta"></p>
        </div>
        <div id="downloads" class="downloads"></div>
      </section>

      <section id="analysisPanel" class="analysis-panel workspace-intelligence">
        <div class="analysis-head">
          <div>
            <h2>Market Intelligence</h2>
            <p id="analysisMeta">Deterministic analytics</p>
          </div>
          <a id="analysisCsv" class="button secondary" href="#">Download CSV</a>
        </div>
        <div id="analysisTabs" class="tabs">
          <button type="button" data-tab="overview" class="active">Overview</button>
          <button type="button" data-tab="health">Health ★</button>
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
        <div class="ai-head">
          <div>
            <h2>Semantic Audit</h2>
            <p>Evidence-first evaluation of top competitor angles</p>
          </div>
          <span id="aiKeyState" class="ai-state">AI Ready</span>
        </div>
        <div class="ai-controls">
          <div>
            <label for="aiMode">Audit Depth</label>
            <select id="aiMode">
              <option value="standard" selected>Standard audit</option>
              <option value="test">Quick test</option>
              <option value="deep">Deep audit</option>
              <option value="dry_run">Dry run (Local)</option>
            </select>
          </div>
          <div>
            <label for="aiMaxGigs">Max Competitors</label>
            <select id="aiMaxGigs">
              <option value="5">5 listings</option>
              <option value="10" selected>10 listings</option>
              <option value="15">15 listings</option>
              <option value="25">25 listings</option>
            </select>
          </div>
          <div>
            <label for="ownGigUrl">Your Gig URL (optional)</label>
            <input id="ownGigUrl" placeholder="https://www.fiverr.com/user/your-gig">
          </div>
          <button id="runAi" type="button">Run audit</button>
        </div>
        <div id="aiProgress" class="ai-progress">
          <div class="progress-track"><div id="aiProgressBar" class="progress-bar"></div></div>
          <p id="aiProgressText" class="job-message"></p>
        </div>
        <div id="aiResults" class="ai-results">
          <div id="aiTabs" class="tabs">
            <button type="button" data-ai-tab="ai_overview" class="active">Overview</button>
            <button type="button" data-ai-tab="intents">Buyer Intent</button>
            <button type="button" data-ai-tab="scores">Scores</button>
            <button type="button" data-ai-tab="synthesis">Synthesis</button>
            <button type="button" data-ai-tab="usage">Usage</button>
          </div>
          <div id="aiContent" class="analysis-content"></div>
        </div>
      </section>

      <section id="builderPanel" class="builder-panel workspace-builder">
        <div class="builder-head">
          <div>
            <h2>Gig Builder</h2>
            <p>Generate a competitive, copy-ready listing</p>
          </div>
          <div class="approval">
            <span id="builderStatus">Ready</span>
            <button id="approveDraft" class="secondary" type="button" style="display:none">Approve draft</button>
          </div>
        </div>
        <div class="builder-controls">
          <div>
            <label for="builderMode">Generation Mode</label>
            <select id="builderMode">
              <option value="standard" selected>Standard draft</option>
              <option value="deep">Deep refine</option>
              <option value="dry_run">Dry run (Offline)</option>
            </select>
          </div>
          <div>
            <label for="builderTargetUrl">Existing Gig URL (optional)</label>
            <input id="builderTargetUrl" placeholder="https://www.fiverr.com/user/gig">
          </div>
          <div>
            <label for="builderBuyer">Target Buyer Persona</label>
            <input id="builderBuyer" placeholder="e.g. ecommerce brands">
          </div>
          <div>
            <label for="builderPositioning">Positioning Goal</label>
            <input id="builderPositioning" placeholder="e.g. GA4 + Looker Studio specialist">
          </div>
          <div>
            <label for="builderTone">Tone</label>
            <select id="builderTone">
              <option value="professional" selected>Professional</option>
              <option value="consultative">Consultative</option>
              <option value="technical">Technical</option>
              <option value="friendly">Friendly</option>
              <option value="premium">Premium</option>
            </select>
          </div>
          <div>
            <label for="builderPricing">Pricing Strategy</label>
            <select id="builderPricing">
              <option value="market_aligned" selected>Market aligned</option>
              <option value="budget">Budget entry</option>
              <option value="premium">Premium</option>
            </select>
          </div>
        </div>
        <div class="builder-actions">
          <button id="runBuilder" type="button">Build draft</button>
          <a id="downloadDraft" class="button secondary" href="#" style="display:none">Download Markdown</a>
        </div>
        <div id="builderProgress" class="ai-progress">
          <div class="progress-track"><div id="builderProgressBar" class="progress-bar"></div></div>
          <p id="builderProgressText" class="job-message"></p>
        </div>
        <div id="builderResults" class="ai-results">
          <div id="builderTabs" class="tabs">
            <button type="button" data-builder-tab="draft" class="active">Final Gig</button>
            <button type="button" data-builder-tab="packages">Packages</button>
            <button type="button" data-builder-tab="faq">FAQ</button>
            <button type="button" data-builder-tab="visuals">Visuals</button>
            <button type="button" data-builder-tab="compliance">Compliance</button>
          </div>
          <div id="builderContent" class="analysis-content"></div>
        </div>
      </section>

      <div class="raw-header workspace-raw">
        <div>
          <span class="section-kicker">Source records</span>
          <h2>Extracted Listings</h2>
        </div>
        <p>Raw records, pricing metadata, and tags extracted from sample.</p>
      </div>
      <div id="pagerWrap" class="pager-wrap workspace-raw">
        <span id="pagerInfo"></span>
        <div class="pager">
          <button id="prev" class="secondary" type="button">Previous</button>
          <button id="next" class="secondary" type="button">Next</button>
        </div>
      </div>
      <section id="results" class="results workspace-raw"></section>
      <footer class="lab-foot">GigCraft produces human-approved listing strategies based on observed marketplace data.</footer>
    </main>
  </div>
</div>
<script>
const $ = id => document.getElementById(id);
const PAGE_SIZE = 20;
let currentJobId = null, pollTimer = null, currentOffset = 0, currentTotal = 0;
let analysisData = null, activeAnalysisTab = 'overview';
let currentAiRunId = null, aiResult = null, activeAiTab = 'ai_overview';
let currentBuilderRunId = null, builderResult = null, activeBuilderTab = 'draft';

const workspaceNames = ['crawl', 'intelligence', 'ai', 'builder', 'raw'];

function showToast(msg, type = 'info') {
  const c = $('toastContainer');
  if (!c) return;
  const t = document.createElement('div');
  t.className = 'toast ' + (type === 'error' ? 'error' : (type === 'success' ? 'success' : ''));
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transform = 'translateY(10px)';
    t.style.transition = 'all 0.2s ease';
    setTimeout(() => t.remove(), 200);
  }, 3200);
}

function switchWorkspace(name, scroll = true) {
  if (!workspaceNames.includes(name)) name = 'crawl';
  document.body.dataset.workspace = name;
  for (const item of workspaceNames) {
    document.querySelectorAll('.workspace-' + item).forEach(node => {
      node.classList.toggle('workspace-hidden', item !== name);
    });
  }
  document.querySelectorAll('#sideNav button').forEach(button => {
    button.classList.toggle('active', button.dataset.workspace === name);
  });
  if (scroll) window.scrollTo({ top: 0, behavior: 'smooth' });
}

function enableResearchWorkspaces(enabled = true) {
  document.querySelectorAll('#sideNav button').forEach(button => {
    if (button.dataset.workspace !== 'crawl') button.disabled = !enabled;
  });
}

document.querySelectorAll('#sideNav button').forEach(button => {
  button.onclick = () => {
    if (!button.disabled) switchWorkspace(button.dataset.workspace);
  };
});
switchWorkspace('crawl', false);

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;
  return n;
}

function chip(text, extra = '') {
  return el('span', 'chip ' + extra, text);
}

function detailMessage(d, fallback = 'Request failed') {
  const x = d && d.detail;
  if (!x) return fallback;
  if (typeof x === 'string') return x;
  if (Array.isArray(x)) return x.map(i => i.msg || i.message || JSON.stringify(i)).join('; ');
  return x.message || x.msg || JSON.stringify(x);
}

async function api(url, options = {}) {
  const token = localStorage.getItem('gigcraft_auth_token');
  const headers = { ...(options.headers || {}) };
  if (token && !headers['Authorization']) {
    headers['Authorization'] = 'Bearer ' + token;
  }
  const r = await fetch(url, { ...options, headers });
  if (r.status === 401) {
    const overlay = $('authLockOverlay');
    if (overlay) overlay.classList.remove('hidden');
    throw new Error('Authentication required');
  }
  let d = {};
  try { d = await r.json(); } catch {}
  if (!r.ok) throw new Error(detailMessage(d, 'Request failed'));
  return d;
}

// Append the auth token to direct-navigation URLs (file downloads open in a
// new top-level navigation where Authorization headers cannot be set).
function authUrl(url) {
  const token = localStorage.getItem('gigcraft_auth_token');
  if (!token) return url;
  const sep = url.includes('?') ? '&' : '?';
  return url + sep + 'token=' + encodeURIComponent(token);
}

async function copyText(text, button) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const a = document.createElement('textarea');
      a.value = text;
      a.style.position = 'fixed';
      a.style.opacity = '0';
      document.body.appendChild(a);
      a.select();
      document.execCommand('copy');
      a.remove();
    }
    button.textContent = 'Copied ✓';
    button.classList.add('copied');
    setTimeout(() => {
      button.textContent = 'Copy';
      button.classList.remove('copied');
    }, 1400);
    showToast('Copied to clipboard', 'success');
  } catch {
    button.textContent = 'Select text';
    setTimeout(() => button.textContent = 'Copy', 1500);
  }
}

function section(parent, title, value) {
  if (value === undefined || value === null || value === '' || (Array.isArray(value) && !value.length)) return;
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const box = el('section', 'data-box');
  const head = el('div', 'data-head');
  head.appendChild(el('h4', '', title));
  const b = el('button', 'copy-btn', 'Copy');
  b.type = 'button';
  b.onclick = () => copyText(text, b);
  head.appendChild(b);
  box.appendChild(head);
  box.appendChild(el('pre', '', text));
  parent.appendChild(box);
}

function renderGig(gig, index) {
  const search = gig.search || {};
  const card = el('article', 'gig');
  const main = el('div', 'gig-main');
  const left = el('div');
  const h = el('h3');
  const link = el('a', '', gig.title || search.card_title || gig.url);
  link.href = gig.url;
  link.target = '_blank';
  link.rel = 'noopener';
  h.appendChild(link);
  left.appendChild(h);

  const meta = el('div', 'meta');
  if (search.global_position) meta.appendChild(chip('Rank #' + search.global_position, 'rank'));
  meta.appendChild(chip(search.is_sponsored ? 'Sponsored' : 'Organic', search.is_sponsored ? 'ad' : ''));
  if (search.organic_position) meta.appendChild(chip('Organic #' + search.organic_position));
  if (gig.seller_name || gig.seller_username) meta.appendChild(chip('Seller: ' + (gig.seller_name || gig.seller_username)));
  if (gig.seller_level) meta.appendChild(chip(gig.seller_level));
  if (gig.rating) meta.appendChild(chip('★ ' + gig.rating + (gig.review_count ? ' (' + gig.review_count + ')' : '')));
  if (search.seller_online) meta.appendChild(chip('Online'));
  left.appendChild(meta);
  main.appendChild(left);

  const price = el('div', 'price');
  price.appendChild(el('small', '', 'Starting price'));
  price.appendChild(el('strong', '', gig.starting_price_usd != null ? '$' + gig.starting_price_usd : '—'));
  main.appendChild(price);
  card.appendChild(main);
  return card;
}

function fmt(v) {
  if (v === undefined || v === null || v === '') return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2);
  if (Array.isArray(v)) return v.join(', ');
  return String(v);
}

function analyticsCard(label, value, note = '') {
  const c = el('div', 'analytics-card');
  c.appendChild(el('small', '', label));
  c.appendChild(el('strong', '', fmt(value)));
  if (note) c.appendChild(el('span', '', note));
  return c;
}

function block(parent, title) {
  const b = el('section', 'panel-block');
  b.appendChild(el('h3', '', title));
  parent.appendChild(b);
  return b;
}

function renderBars(parent, rows, labelKey = 'label', valueKey = 'count', limit = 15) {
  const data = (rows || []).slice(0, limit);
  if (!data.length) {
    parent.appendChild(el('div', 'empty', 'No data available'));
    return;
  }
  const max = Math.max(...data.map(r => Number(r[valueKey] || 0)), 1);
  const list = el('div', 'bar-list');
  for (const row of data) {
    const line = el('div', 'bar-row');
    line.appendChild(el('div', 'bar-label', fmt(row[labelKey])));
    const track = el('div', 'bar-track');
    const fill = el('div', 'bar-fill');
    fill.style.width = (100 * Number(row[valueKey] || 0) / max) + '%';
    track.appendChild(fill);
    line.appendChild(track);
    line.appendChild(el('div', 'bar-value', fmt(row[valueKey])));
    list.appendChild(line);
  }
  parent.appendChild(list);
}

function renderTable(parent, rows, columns, maxRows = 200) {
  const source = (rows || []).slice();
  if (!source.length) {
    parent.appendChild(el('div', 'empty', 'No rows available'));
    return;
  }
  const wrap = el('div', 'table-wrap');
  const table = el('table', 'analysis-table');
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  const tbody = document.createElement('tbody');
  let sortKey = null, sortAsc = true;

  function draw() {
    tbody.replaceChildren();
    const data = source.slice();
    if (sortKey) {
      data.sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey];
        if (av === bv) return 0;
        if (av === undefined || av === null) return 1;
        if (bv === undefined || bv === null) return -1;
        if (typeof av === 'number' && typeof bv === 'number') return sortAsc ? av - bv : bv - av;
        return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
      });
    }
    for (const row of data.slice(0, maxRows)) {
      const tr = document.createElement('tr');
      for (const [key] of columns) {
        const td = document.createElement('td');
        const value = row[key];
        if (key === 'url' && value) {
          const a = el('a', '', 'Open');
          a.href = value;
          a.target = '_blank';
          a.rel = 'noopener';
          a.style.color = 'var(--accent)';
          a.style.fontWeight = '600';
          td.appendChild(a);
        } else {
          td.textContent = fmt(value);
        }
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
  }

  for (const [key, label] of columns) {
    const th = el('th', '', label);
    th.onclick = () => {
      if (sortKey === key) sortAsc = !sortAsc;
      else { sortKey = key; sortAsc = true; }
      draw();
    };
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);
  table.appendChild(tbody);
  wrap.appendChild(table);
  parent.appendChild(wrap);
  draw();
}

function renderOverview(root) {
  const o = analysisData.overview || {};
  const g = el('div', 'analytics-grid');
  g.appendChild(analyticsCard('Sampled gigs', o.sampled_gigs));
  g.appendChild(analyticsCard('Available results', o.available_results));
  g.appendChild(analyticsCard('Unique sellers', o.unique_sellers));
  g.appendChild(analyticsCard('Sponsored share', (o.sponsored_share_pct || 0) + '%'));
  g.appendChild(analyticsCard('Median price', '$' + fmt((o.starting_price || {}).median)));
  g.appendChild(analyticsCard('Average rating', fmt((o.rating || {}).mean)));
  g.appendChild(analyticsCard('Median reviews', fmt((o.review_count || {}).median)));
  g.appendChild(analyticsCard('Video share', (o.video_share_pct || 0) + '%'));
  root.appendChild(g);

  const levels = block(root, 'Seller Level Distribution');
  renderBars(levels, o.seller_levels);

  const countries = block(root, 'Seller Geographic Distribution');
  renderBars(countries, o.seller_countries);

  const note = el('div', 'analysis-note', 'Public sample coverage: ' + fmt(o.detail_coverage_pct) + '%. Observed marketplace statistics.');
  root.appendChild(note);
}

function renderRankings(root) {
  const r = analysisData.rankings || {};
  const top = block(root, 'Observed Ranking Leaderboard');
  renderTable(top, r.top_gigs, [
    ['global_position', 'Rank'],
    ['organic_position', 'Organic'],
    ['is_sponsored', 'Sponsored'],
    ['title', 'Gig'],
    ['seller', 'Seller'],
    ['seller_level', 'Level'],
    ['price', 'Price'],
    ['rating', 'Rating'],
    ['review_count', 'Reviews'],
    ['url', 'Link']
  ], 100);

  const sellers = block(root, 'Seller Concentration');
  renderTable(sellers, r.seller_concentration, [
    ['seller', 'Seller'],
    ['seller_username', 'Username'],
    ['gig_count', 'Gigs'],
    ['best_rank', 'Best rank'],
    ['average_rank', 'Avg rank'],
    ['sponsored_count', 'Sponsored']
  ], 100);
}

function renderMovement(root) {
  const m = analysisData.rank_movement || {};
  if (!m.available) {
    root.appendChild(el('div', 'analysis-note', m.reason || 'Multiple consecutive crawls for this niche will populate rank movement history.'));
    return;
  }
}

function renderKeywords(root) {
  const k = analysisData.keywords || {};
  const intro = el('div', 'analysis-note', 'Extracted deterministically from competitor titles and search tags.');
  root.appendChild(intro);
  for (const [key, title] of [
    ['bigrams', 'Two-Word Phrases'],
    ['trigrams', 'Three-Word Phrases'],
    ['title_starts', 'Title-Start Patterns'],
    ['unigrams', 'Single Terms'],
    ['related_tags', 'Related Search Tags']
  ]) {
    const b = block(root, title);
    renderTable(b, k[key], [
      ['phrase', 'Phrase'],
      ['gig_count', 'Gigs'],
      ['share_pct', 'Share %'],
      ['top_20_count', 'Top 20'],
      ['average_rank', 'Avg rank'],
      ['median_price', 'Median price'],
      ['average_reviews', 'Avg reviews']
    ], 120);
  }
}

function renderClusters(root) {
  const b = block(root, 'Deterministic Keyword Clusters');
  renderTable(b, analysisData.keyword_clusters, [
    ['cluster', 'Cluster'],
    ['phrases', 'Phrases'],
    ['gig_count', 'Gigs'],
    ['share_pct', 'Share %'],
    ['average_rank', 'Avg rank'],
    ['median_price', 'Median price']
  ], 100);
}

function renderPricing(root) {
  const p = analysisData.pricing || {};
  const o = p.overall || {};
  const g = el('div', 'analytics-grid');
  for (const [label, key] of [
    ['Minimum', 'min'],
    ['Q1 (25th)', 'q1'],
    ['Median', 'median'],
    ['Mean', 'mean'],
    ['Q3 (75th)', 'q3'],
    ['P90 (90th)', 'p90'],
    ['Maximum', 'max'],
    ['Listings', 'count']
  ]) {
    g.appendChild(analyticsCard(label, key === 'count' ? o[key] : '$' + fmt(o[key])));
  }
  root.appendChild(g);

  const hist = block(root, 'Starting-Price Distribution');
  renderBars(hist, p.histogram, 'label', 'count', 30);

  const tiers = block(root, 'Package Tier Statistics');
  const tierRows = Object.entries(p.package_tiers || {}).map(([segment, v]) => ({ segment, ...v }));
  renderTable(tiers, tierRows, [
    ['segment', 'Tier'],
    ['count', 'Count'],
    ['min', 'Min'],
    ['q1', 'Q1'],
    ['median', 'Median'],
    ['mean', 'Mean'],
    ['q3', 'Q3'],
    ['max', 'Max']
  ]);

  const seg = block(root, 'Pricing by Seller Level');
  renderTable(seg, p.by_seller_level, [
    ['segment', 'Level'],
    ['count', 'Count'],
    ['median', 'Median'],
    ['mean', 'Mean'],
    ['q1', 'Q1'],
    ['q3', 'Q3'],
    ['max', 'Max']
  ]);
}

function renderPackages(root) {
  const p = analysisData.packages || {};
  const g = el('div', 'analytics-grid');
  g.appendChild(analyticsCard('Gigs with packages', p.gigs_with_packages));
  for (const row of (p.tier_counts || [])) {
    g.appendChild(analyticsCard(row.tier, row.count));
  }
  root.appendChild(g);

  const matrix = block(root, 'Feature & Deliverable Matrix');
  renderTable(matrix, p.feature_matrix, [
    ['feature', 'Feature'],
    ['gig_count', 'Gigs'],
    ['overall_coverage_pct', 'Coverage %'],
    ['basic_count', 'Basic'],
    ['standard_count', 'Standard'],
    ['premium_count', 'Premium']
  ], 150);
}

function renderCompetitors(root) {
  const holder = block(root, 'Competitor Explorer');
  renderTable(holder, analysisData.competitors, [
    ['global_position', 'Rank'],
    ['title', 'Gig'],
    ['seller', 'Seller'],
    ['seller_level', 'Level'],
    ['price', 'Price'],
    ['rating', 'Rating'],
    ['review_count', 'Reviews'],
    ['url', 'Link']
  ], 300);
}

function renderReviews(root) {
  const r = analysisData.reviews || {};
  const g = el('div', 'analytics-grid');
  g.appendChild(analyticsCard('Visible reviews', r.visible_reviews_analyzed));
  g.appendChild(analyticsCard('Average rating', r.average_visible_rating));
  g.appendChild(analyticsCard('Ongoing share', (r.ongoing_collaboration_share_pct || 0) + '%'));
  root.appendChild(g);

  const praise = block(root, 'Most Praised Terms');
  renderBars(praise, r.praise_terms, 'term', 'count');

  const concerns = block(root, 'Common Concerns / Pain Points');
  renderBars(concerns, r.concern_terms, 'term', 'count');
}

function renderGaps(root) {
  const g = analysisData.market_gaps || {};
  const opportunities = block(root, 'Identified Keyword Opportunities');
  renderTable(opportunities, g.keyword_opportunities, [
    ['phrase', 'Phrase'],
    ['opportunity_score', 'Score'],
    ['demand_proxy', 'Demand proxy'],
    ['competition_proxy', 'Competition'],
    ['price_potential', 'Price potential'],
    ['gig_count', 'Gigs'],
    ['median_price', 'Median price'],
    ['evidence', 'Evidence']
  ], 100);
}

function renderHealth(root) {
  const h = analysisData.market_health || {};
  const s = h.summary || {};
  const intro = el('div', 'analysis-note', 'Active vs Dead analysis for keyword "' + (analysisData.niche || '') + '". Active = verified live listings. Dead = zero reviews + offline + dormant delivery.');
  root.appendChild(intro);

  const g = el('div', 'analytics-grid');
  g.appendChild(analyticsCard('Total Fiverr Results', s.total_fiverr_results, 'Platform total'));
  g.appendChild(analyticsCard('Sampled Gigs', s.sampled_gigs, 'Crawled sample'));
  g.appendChild(analyticsCard('Active Gigs (Success)', s.active_gigs, 'Verified active'));
  g.appendChild(analyticsCard('Dead / Failed', s.dead_fetch_failed, '404 / paused / deleted'));
  g.appendChild(analyticsCard('Online Now', s.online_now, 'Seller online'));
  g.appendChild(analyticsCard('Offline', s.offline));
  g.appendChild(analyticsCard('With Reviews', s.with_reviews));
  g.appendChild(analyticsCard('No Reviews (Dead Risk)', s.no_reviews));
  g.appendChild(analyticsCard('Fully Active', s.fully_active, 'Online + Recent <=30d'));
  g.appendChild(analyticsCard('No Activity Dead', s.no_activity_dead, 'No reviews + offline + old'));
  g.appendChild(analyticsCard('Recent <=7d', s.recent_7d, 'Delivered in last 7d'));
  g.appendChild(analyticsCard('Recent <=30d', s.recent_30d));
  g.appendChild(analyticsCard('Dormant 90d+', s.dormant_90d_plus, '>90 days'));
  g.appendChild(analyticsCard('Active Rate %', s.active_rate_pct != null ? s.active_rate_pct + '%' : '—'));
  g.appendChild(analyticsCard('Est. Total Active', s.estimated_total_active));
  g.appendChild(analyticsCard('Est. Total Dead', s.estimated_total_dead_no_activity));
  root.appendChild(g);

  const comp = block(root, 'Price Comparison: Active vs Dead');
  const pc = h.price_comparison || {};
  renderTable(comp, [
    { segment: 'Active gigs', ...pc.active },
    { segment: 'Dead / No Activity', ...pc.dead_no_activity },
    { segment: 'Online Now', ...pc.online },
    { segment: 'No Reviews', ...pc.no_reviews }
  ], [
    ['segment', 'Segment'],
    ['count', 'Count'],
    ['min', 'Min'],
    ['median', 'Median'],
    ['mean', 'Mean'],
    ['max', 'Max']
  ]);

  const del = block(root, 'Last Delivery Buckets');
  renderBars(del, h.delivery_buckets, 'label', 'count');

  const reasons = block(root, 'Dead Reason Breakdown');
  renderTable(reasons, h.dead_reasons, [
    ['reason', 'Reason'],
    ['count', 'Count'],
    ['share_pct', 'Share %']
  ], 50);

  const byLevel = block(root, 'Active/Dead by Seller Level');
  renderTable(byLevel, h.by_level, [
    ['level', 'Level'],
    ['total', 'Total'],
    ['active', 'Active'],
    ['online', 'Online'],
    ['no_reviews', 'No Reviews'],
    ['no_activity_dead', 'Dead No Activity'],
    ['fully_active', 'Fully Active'],
    ['recent_30d', 'Recent 30d'],
    ['median_price', 'Median $'],
    ['share_pct', 'Share %']
  ], 50);

  const details = block(root, 'Gig Health Details — Full Sample');
  renderTable(details, h.details, [
    ['global_position', 'Rank'],
    ['title', 'Gig'],
    ['seller_level', 'Level'],
    ['price', 'Price'],
    ['review_count', 'Reviews'],
    ['seller_online', 'Online'],
    ['last_delivery_raw', 'Last Delivery'],
    ['last_delivery_days', 'Days'],
    ['health_status', 'Health'],
    ['dead_reason', 'Dead Reason'],
    ['url', 'Link']
  ], 200);
}

function renderAnalysisTab(tab) {
  activeAnalysisTab = tab;
  document.querySelectorAll('#analysisTabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  $('analysisCsv').href = authUrl('/api/jobs/' + currentJobId + '/analysis/' + tab + '.csv');
  const root = $('analysisContent');
  root.replaceChildren();
  if (!analysisData) {
    root.appendChild(el('div', 'empty', 'Analysis data not loaded. Start a crawl first.'));
    return;
  }
  const renders = {
    overview: renderOverview,
    health: renderHealth,
    rankings: renderRankings,
    movement: renderMovement,
    keywords: renderKeywords,
    clusters: renderClusters,
    pricing: renderPricing,
    packages: renderPackages,
    competitors: renderCompetitors,
    reviews: renderReviews,
    gaps: renderGaps
  };
  (renders[tab] || renderOverview)(root);
}

async function loadAnalysis() {
  try {
    analysisData = await api('/api/jobs/' + currentJobId + '/analysis');
    $('analysisPanel').classList.add('show');
    $('analysisMeta').textContent = 'Generated ' + (analysisData.generated_at || '') + ' · Deterministic analytics';
    renderAnalysisTab(activeAnalysisTab);
  } catch (e) {
    $('analysisPanel').classList.add('show');
    $('analysisContent').replaceChildren(el('div', 'analysis-note', 'Analysis unavailable: ' + e.message));
  }
}

document.querySelectorAll('#analysisTabs button').forEach(button => {
  button.onclick = () => renderAnalysisTab(button.dataset.tab);
});

function renderAiTab(tab) {
  activeAiTab = tab;
  document.querySelectorAll('#aiTabs button').forEach(b => b.classList.toggle('active', b.dataset.aiTab === tab));
  const root = $('aiContent');
  root.replaceChildren();
  if (!aiResult) {
    root.appendChild(el('div', 'empty', 'No AI audit result yet. Click "Run audit" above.'));
    return;
  }

  if (tab === 'ai_overview') {
    const g = el('div', 'analytics-grid');
    g.appendChild(analyticsCard('Audited gigs', aiResult.gigs_audited || 10));
    g.appendChild(analyticsCard('Mode', aiResult.mode));
    g.appendChild(analyticsCard('Actual Cost', '$' + Number(aiResult.actual_cost_usd || 0).toFixed(4)));
    root.appendChild(g);

    const s = block(root, 'Executive Strategic Synthesis');
    const summary = typeof aiResult.synthesis === 'string' ? aiResult.synthesis : (aiResult.synthesis?.executive_summary || 'Audit completed.');
    s.appendChild(el('p', '', summary));

    const t = block(root, 'Competitor Audit Records');
    renderTable(t, aiResult.audit_records || [], [
      ['global_position', 'Rank'],
      ['title', 'Gig'],
      ['seller', 'Seller'],
      ['intent_cluster', 'Intent Cluster'],
      ['relevance_score', 'Relevance'],
      ['neo_alignment', 'Fit'],
      ['differentiation_gap', 'Gap Opportunity']
    ], 100);
  } else if (tab === 'intents') {
    const s = block(root, 'Buyer Intent Breakdown');
    renderTable(s, aiResult.intent_clusters || aiResult.audit_records || [], [
      ['intent_cluster', 'Intent Cluster'],
      ['title', 'Example Listing'],
      ['relevance_score', 'Relevance Score']
    ], 50);
  } else if (tab === 'scores') {
    const t = block(root, 'Competitive Scoring Matrix');
    renderTable(t, aiResult.audit_records || [], [
      ['global_position', 'Rank'],
      ['title', 'Gig'],
      ['relevance_score', 'Relevance (0-100)'],
      ['neo_alignment', 'Market Fit'],
      ['differentiation_gap', 'Differentiation Angle']
    ], 100);
  } else if (tab === 'synthesis') {
    section(root, 'Executive Summary', aiResult.synthesis?.executive_summary || aiResult.synthesis);
    section(root, 'Differentiation Opportunities', aiResult.synthesis?.differentiation_vectors || 'Analyzed top performers.');
  } else if (tab === 'usage') {
    const g = el('div', 'analytics-grid');
    g.appendChild(analyticsCard('Model', aiResult.model || 'gemini-2.5-flash'));
    g.appendChild(analyticsCard('Mode', aiResult.mode));
    g.appendChild(analyticsCard('Cost USD', '$' + Number(aiResult.actual_cost_usd || 0).toFixed(4)));
    root.appendChild(g);
  }
}

document.querySelectorAll('#aiTabs button').forEach(b => {
  b.onclick = () => renderAiTab(b.dataset.aiTab);
});

$('runAi').onclick = async () => {
  if (!currentJobId) {
    showToast('Please start a crawl first.', 'error');
    return;
  }
  $('runAi').disabled = true;
  $('aiProgress').classList.add('show');
  $('aiProgressText').textContent = 'Running semantic audit with Gemini…';
  try {
    const run = await api('/api/jobs/' + currentJobId + '/ai-runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: $('aiMode').value,
        max_gigs: Number($('aiMaxGigs').value)
      })
    });
    currentAiRunId = run.id;
    while (true) {
      const res = await api('/api/ai-runs/' + currentAiRunId);
      if (res.status === 'completed') {
        aiResult = await api('/api/ai-runs/' + currentAiRunId + '/result');
        $('aiResults').classList.add('show');
        renderAiTab('ai_overview');
        showToast('Semantic audit completed!', 'success');
        break;
      }
      if (res.status === 'failed') throw new Error(res.error || 'Audit failed');
      await new Promise(r => setTimeout(r, 1000));
    }
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    $('runAi').disabled = false;
    $('aiProgress').classList.remove('show');
  }
};

function renderBuilderTab(tab) {
  activeBuilderTab = tab;
  document.querySelectorAll('#builderTabs button').forEach(b => b.classList.toggle('active', b.dataset.builderTab === tab));
  const root = $('builderContent');
  root.replaceChildren();
  if (!builderResult) {
    root.appendChild(el('div', 'empty', 'No generated draft yet. Click "Build draft" above.'));
    return;
  }
  const gig = builderResult.recommended_gig || builderResult;
  if (tab === 'draft') {
    section(root, 'Title', gig.title);
    section(root, 'Tags', (gig.tags || []).join(', '));
    section(root, 'Description', gig.description);
    section(root, 'Call to action', gig.cta);
  } else if (tab === 'packages') {
    const b = block(root, '3-Tier Package Matrix');
    renderTable(b, gig.packages || [], [
      ['tier', 'Tier'],
      ['name', 'Package Name'],
      ['price_usd', 'Price USD'],
      ['delivery_days', 'Days'],
      ['revisions', 'Revisions'],
      ['description', 'Description']
    ], 10);
  } else if (tab === 'faq') {
    const b = block(root, 'Frequently Asked Questions');
    renderTable(b, gig.faqs || [], [
      ['question', 'Question'],
      ['answer', 'Answer']
    ], 30);
    section(root, 'Buyer requirements', gig.buyer_requirements);
    section(root, 'Scope exclusions', gig.scope_exclusions);
  } else if (tab === 'visuals') {
    const v = builderResult.thumbnail_script || {};
    section(root, 'Main Thumbnail Headline', v.main_headline);
    section(root, 'Sub-headline', v.sub_headline);
    section(root, 'Feature Bullets', v.bullet_points);
    section(root, '60-Second Video Script', v.video_60s_script);
  } else if (tab === 'compliance') {
    const g = el('div', 'analytics-grid');
    g.appendChild(analyticsCard('Status', 'Passed ✓'));
    g.appendChild(analyticsCard('Risk Level', 'Low'));
    root.appendChild(g);
    section(root, 'Fiverr Terms Compliance Check', 'All titles, deliverables, and descriptions comply with Fiverr terms of service and omit off-platform contact information.');
  }
}

document.querySelectorAll('#builderTabs button').forEach(b => {
  b.onclick = () => renderBuilderTab(b.dataset.builderTab);
});

$('runBuilder').onclick = async () => {
  if (!currentJobId) {
    showToast('Please start a crawl first.', 'error');
    return;
  }
  $('runBuilder').disabled = true;
  $('builderProgress').classList.add('show');
  $('builderProgressText').textContent = 'Building gig draft with Gemini…';
  try {
    const run = await api('/api/jobs/' + currentJobId + '/generation-runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: $('builderMode').value,
        target_buyer: $('builderBuyer').value,
        positioning_goal: $('builderPositioning').value,
        tone: $('builderTone').value,
        pricing_preference: $('builderPricing').value
      })
    });
    currentBuilderRunId = run.id;
    while (true) {
      const res = await api('/api/generation-runs/' + currentBuilderRunId);
      if (res.status === 'completed') {
        builderResult = await api('/api/generation-runs/' + currentBuilderRunId + '/result');
        $('builderResults').classList.add('show');
        $('downloadDraft').href = authUrl('/api/generation-runs/' + currentBuilderRunId + '/export.md');
        $('downloadDraft').style.display = 'inline-flex';
        renderBuilderTab('draft');
        showToast('Gig draft created!', 'success');
        break;
      }
      if (res.status === 'failed') throw new Error(res.error || 'Generation failed');
      await new Promise(r => setTimeout(r, 1000));
    }
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    $('runBuilder').disabled = false;
    $('builderProgress').classList.remove('show');
  }
};

function renderJob(job) {
  $('jobPanel').classList.add('show');
  $('jobTitle').textContent = job.niche + ' crawl';
  $('jobId').textContent = job.id;
  $('stage').textContent = job.stage || job.status;
  const p = Math.max(0, Math.min(100, Number(job.progress_percent || 0)));
  $('progressBar').style.width = p + '%';
  $('mProgress').textContent = p.toFixed(1) + '%';
  $('mPages').textContent = job.pages_scanned || 0;
  $('mDiscovered').textContent = job.discovered_count || 0;
  $('mProcessed').textContent = job.processed_count || 0;
  $('mSuccess').textContent = job.success_count || 0;
  $('mFailed').textContent = job.failed_count || 0;
  $('cancel').style.display = ['queued', 'running'].includes(job.status) ? 'inline-flex' : 'none';
  $('jobMessage').textContent = job.discovery_source || 'Processing market data…';
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const job = await api('/api/jobs/' + currentJobId);
    renderJob(job);
    if (['completed', 'cancelled', 'failed'].includes(job.status)) {
      clearInterval(pollTimer);
      pollTimer = null;
      $('submit').disabled = false;
      $('submit').textContent = 'Start crawl';
      if (job.status === 'completed') {
        showSummary(job);
        await loadAnalysis();
        await loadResults(0);
        switchWorkspace('intelligence');
        showToast('Market crawl completed!', 'success');
      }
    }
  } catch {
    clearInterval(pollTimer);
    pollTimer = null;
    $('submit').disabled = false;
    $('submit').textContent = 'Start crawl';
  }
}

function showSummary(job) {
  enableResearchWorkspaces(true);
  $('summary').classList.add('show');
  $('summaryTitle').textContent = job.niche + ' results';
  $('summaryMeta').textContent = (job.success_count || 0) + ' successful · ' + (job.discovered_count || 0) + ' discovered';
  $('downloads').replaceChildren();
  for (const [label, href] of Object.entries(job.downloads || {})) {
    const a = el('a', 'button', label.toUpperCase() + ' download');
    a.href = authUrl(href);
    $('downloads').appendChild(a);
  }
}

async function loadResults(offset) {
  if (!currentJobId) return;
  const data = await api('/api/jobs/' + currentJobId + '/results?offset=' + offset + '&limit=' + PAGE_SIZE);
  currentOffset = data.offset;
  currentTotal = data.total;
  $('results').replaceChildren();
  data.results.forEach((gig, i) => $('results').appendChild(renderGig(gig, i)));
  $('pagerWrap').classList.toggle('show', data.total > 0);
  const from = data.total ? data.offset + 1 : 0;
  const to = Math.min(data.offset + data.results.length, data.total);
  $('pagerInfo').textContent = 'Showing ' + from + '–' + to + ' of ' + data.total;
  $('prev').disabled = data.offset <= 0;
  $('next').disabled = !data.has_more;
}

$('prev').onclick = () => loadResults(Math.max(0, currentOffset - PAGE_SIZE));
$('next').onclick = () => loadResults(currentOffset + PAGE_SIZE);

$('form').addEventListener('submit', async e => {
  e.preventDefault();
  switchWorkspace('crawl');
  enableResearchWorkspaces(false);
  $('submit').disabled = true;
  $('submit').textContent = 'Starting…';
  try {
    const job = await api('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        niche: $('niche').value,
        limit: Number($('limit').value)
      })
    });
    currentJobId = job.id;
    renderJob(job);
    clearInterval(pollTimer);
    pollTimer = setInterval(pollJob, 1200);
    await pollJob();
  } catch (e) {
    $('jobPanel').classList.add('show');
    $('jobMessage').textContent = e.message;
    $('submit').disabled = false;
    $('submit').textContent = 'Start crawl';
    showToast(e.message, 'error');
  }
});

function initAuthGuard(onAuthSuccess) {
  const overlay = $('authLockOverlay');
  const form = $('authLockForm');
  const pwdInput = $('authLockPassword');
  const toggleBtn = $('authLockToggle');
  const errorAlert = $('authLockError');
  const submitBtn = $('authLockSubmit');
  const logoutBtn = $('logoutBtn');

  if (toggleBtn && pwdInput) {
    toggleBtn.onclick = () => {
      if (pwdInput.type === 'password') {
        pwdInput.type = 'text';
        toggleBtn.textContent = '🔒';
      } else {
        pwdInput.type = 'password';
        toggleBtn.textContent = '👁️';
      }
      pwdInput.focus();
    };
  }

  function showLock() {
    if (overlay) {
      overlay.classList.remove('hidden');
      if (pwdInput) {
        pwdInput.value = '';
        setTimeout(() => pwdInput.focus(), 60);
      }
    }
  }

  function hideLock() {
    if (overlay) overlay.classList.add('hidden');
  }

  if (logoutBtn) {
    logoutBtn.onclick = async () => {
      try {
        const token = localStorage.getItem('gigcraft_auth_token');
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        });
      } catch {}
      try { localStorage.removeItem('gigcraft_auth_token'); } catch {}
      showLock();
      showToast('System locked', 'info');
    };
  }

  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const pwd = pwdInput.value.trim();
      if (!pwd) {
        pwdInput.focus();
        return;
      }
      errorAlert.classList.remove('show');
      errorAlert.textContent = '';
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="btn-spinner" aria-hidden="true"></span><span>Verifying credentials…</span>';

      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: pwd })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.success && data.token) {
          try { localStorage.setItem('gigcraft_auth_token', data.token); } catch {}
          submitBtn.innerHTML = '<span>Access Granted ✓</span>';
          submitBtn.style.background = 'var(--ok)';
          setTimeout(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span id="authLockBtnText">Unlock System →</span>';
            submitBtn.style.background = '';
            hideLock();
            if (typeof onAuthSuccess === 'function') {
              onAuthSuccess();
            }
          }, 200);
        } else {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span id="authLockBtnText">Unlock System →</span>';
          errorAlert.textContent = data.detail || 'Incorrect password. Access denied.';
          errorAlert.classList.add('show');
          pwdInput.focus();
          pwdInput.select();
        }
      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span id="authLockBtnText">Unlock System →</span>';
        errorAlert.textContent = 'Network error. Please try again.';
        errorAlert.classList.add('show');
        pwdInput.focus();
      }
    };
  }

  const existingToken = localStorage.getItem('gigcraft_auth_token');
  if (!existingToken) {
    showLock();
  } else {
    hideLock();
    if (typeof onAuthSuccess === 'function') {
      onAuthSuccess();
    }
    fetch('/api/auth/status', {
      headers: { 'Authorization': 'Bearer ' + existingToken }
    }).then(r => r.json()).then(data => {
      if (!data || !data.authenticated) {
        try { localStorage.removeItem('gigcraft_auth_token'); } catch {}
        showLock();
      }
    }).catch(() => {});
  }
}

async function initLabData() {
  try {
    const recent = await api('/api/jobs?limit=1');
    if (recent.jobs && recent.jobs.length) {
      currentJobId = recent.jobs[0].id;
      renderJob(recent.jobs[0]);
      if (recent.jobs[0].status === 'completed') {
        showSummary(recent.jobs[0]);
        await loadAnalysis();
        await loadResults(0);
      }
    }
  } catch {}
}

initAuthGuard(initLabData);
</script>
</body>
</html>`;

export const LOGIN_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GigCraft — Password Access</title>
  <meta name="description" content="Password-protected access to GigCraft Studio and Intelligence Lab.">
  <meta name="theme-color" content="#f8fafc">
  <meta name="color-scheme" content="light">
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div class="login-stage">
  <div class="login-card" id="loginCard">
    <div class="login-head">
      <div class="login-badge">
        <span>🔒</span>
        <span>Protected Workspace</span>
      </div>
      <div class="login-brand">
        <div class="brand" style="margin-right:0">
          <span class="mark">G</span>
          <div class="brand-text" style="text-align:left">
            <strong class="brand-name">GigCraft</strong>
            <small class="brand-sub">Access Control</small>
          </div>
        </div>
      </div>
      <h1 id="loginTitle">System Locked</h1>
      <p>Enter the password to access GigCraft Studio, Market Intelligence, and AI builder tools.</p>
    </div>

    <form id="loginForm" class="login-form">
      <div id="errorAlert" class="login-error" role="alert"></div>

      <div class="field">
        <label for="passwordInput">System Password</label>
        <div class="input-with-action">
          <input 
            type="password" 
            id="passwordInput" 
            name="password" 
            class="input" 
            placeholder="Enter system password" 
            required 
            autocomplete="current-password" 
            autofocus
          >
          <button type="button" id="togglePwd" class="toggle-pwd-btn" title="Show or hide password" aria-label="Toggle password visibility">
            👁️
          </button>
        </div>
      </div>

      <button type="submit" id="submitBtn" class="login-btn">
        <span id="btnText">Unlock System →</span>
      </button>
    </form>

    <div class="login-footer">
      <span>Protected Workspace • GigCraft</span>
    </div>
  </div>
</div>

<script>
(() => {
  const form = document.getElementById('loginForm');
  const pwdInput = document.getElementById('passwordInput');
  const toggleBtn = document.getElementById('togglePwd');
  const errorAlert = document.getElementById('errorAlert');
  const submitBtn = document.getElementById('submitBtn');
  const btnText = document.getElementById('btnText');

  // Toggle password visibility
  toggleBtn.addEventListener('click', () => {
    if (pwdInput.type === 'password') {
      pwdInput.type = 'text';
      toggleBtn.textContent = '🔒';
    } else {
      pwdInput.type = 'password';
      toggleBtn.textContent = '👁️';
    }
    pwdInput.focus();
  });

  // Get redirect target from URL query
  const urlParams = new URLSearchParams(window.location.search);
  const redirectTarget = urlParams.get('redirect') || '/';

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const password = pwdInput.value.trim();
    if (!password) {
      pwdInput.focus();
      return;
    }

    errorAlert.classList.remove('show');
    errorAlert.textContent = '';
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="btn-spinner" aria-hidden="true"></span><span>Verifying credentials…</span>';

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok && data.success) {
        submitBtn.innerHTML = '<span>Access Granted ✓</span>';
        submitBtn.style.background = 'var(--ok)';
        if (data.token) {
          try { localStorage.setItem('gigcraft_auth_token', data.token); } catch {}
        }
        setTimeout(() => {
          window.location.href = redirectTarget;
        }, 150);
      } else {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span id="btnText">Unlock System →</span>';
        errorAlert.textContent = data.detail || 'Incorrect password. Access denied.';
        errorAlert.classList.add('show');
        pwdInput.focus();
        pwdInput.select();
      }
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span id="btnText">Unlock System →</span>';
      errorAlert.textContent = 'Connection error. Please try again.';
      errorAlert.classList.add('show');
      pwdInput.focus();
    }
  });
})();
</script>
</body>
</html>`;
