"""Premium dark-luxury frontend. The advanced dashboard remains at /advanced."""

SIMPLE_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GigCraft — Premium Fiverr Gig Studio</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,700;1,500&family=Instrument+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{box-sizing:border-box}
    :root{
      --bg:#080b14;
      --surface:#111624;
      --surface2:#1a1f31;
      --border:rgba(212,168,83,.12);
      --border-hover:rgba(212,168,83,.28);
      --gold:#d4a853;
      --gold-soft:#e8c97a;
      --gold-dim:rgba(212,168,83,.08);
      --gold-glow:rgba(212,168,83,.15);
      --text:#f0ede8;
      --text-dim:#8f8d97;
      --text-muted:#6b6977;
      --danger:#e74c4c;
      --danger-bg:rgba(231,76,76,.08);
      --success:#5ccc7a;
      --overlay:rgba(0,0,0,.48);
      --font-display:'Playfair Display',Georgia,serif;
      --font-sans:'Instrument Sans',system-ui,-apple-system,sans-serif;
      --radius-sm:8px;
      --radius-md:14px;
      --radius-lg:20px;
      --radius-xl:28px;
      --shadow-card:0 25px 60px -12px rgba(0,0,0,.6),0 0 0 1px rgba(212,168,83,.06);
      --shadow-glow:0 0 40px rgba(212,168,83,.06);
    }
    html{scroll-behavior:smooth}
    body{
      margin:0;min-height:100vh;overflow-x:hidden;
      background:var(--bg);
      background-image:
        radial-gradient(ellipse 80% 50% at 50% -10%,rgba(212,168,83,.04),transparent),
        radial-gradient(ellipse 60% 40% at 20% 100%,rgba(212,168,83,.03),transparent),
        repeating-linear-gradient(0deg,transparent,transparent 60px,rgba(255,255,255,.012) 60px,rgba(255,255,255,.012) 61px);
      color:var(--text);
      font-family:var(--font-sans);
      -webkit-font-smoothing:antialiased;
    }
    .noise{
      position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.018;
      background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
      background-size:256px 256px;
    }
    .shell{position:relative;z-index:1;width:min(1080px,calc(100% - 40px));margin:0 auto;padding:18px 0 70px}

    /* ── Topbar ── */
    .topbar{
      display:flex;align-items:center;justify-content:space-between;
      padding:14px 22px;margin-bottom:6px;
      border:1px solid var(--border);border-radius:var(--radius-lg);
      background:rgba(17,22,36,.72);
      backdrop-filter:blur(14px);
      -webkit-backdrop-filter:blur(14px);
      box-shadow:var(--shadow-glow);
    }
    .brand{display:flex;align-items:center;gap:12px}
    .logo{
      width:36px;height:36px;display:grid;place-items:center;
      border-radius:10px;
      background:linear-gradient(145deg,#d4a853,#b8892f);
      color:#080b14;font-family:var(--font-display);font-size:15px;font-weight:700;
      box-shadow:0 6px 16px rgba(212,168,83,.28);
    }
    .brand-text{line-height:1.2}
    .brand-text strong{display:block;font-size:15px;font-weight:700;letter-spacing:-.02em}
    .brand-text small{display:block;color:var(--text-muted);font-size:9px;letter-spacing:.12em;text-transform:uppercase}
    .status-pill{
      display:flex;align-items:center;gap:8px;padding:7px 14px 7px 10px;
      border:1px solid var(--border);border-radius:999px;
      background:rgba(17,22,36,.5);font-size:11px;color:var(--text-muted);font-weight:500;
    }
    .dot{width:6px;height:6px;border-radius:50%;background:var(--text-muted);transition:.4s}
    .dot.on{background:var(--success);box-shadow:0 0 0 4px rgba(92,204,122,.15)}

    /* ── Hero ── */
    .hero{padding:80px 0 44px;text-align:center;animation:fadeUp .8s ease-out}
    @keyframes fadeUp{from{opacity:0;transform:translateY(28px)}to{opacity:1;transform:translateY(0)}}
    .eyebrow{
      display:inline-block;padding:6px 16px;margin-bottom:14px;
      border:1px solid var(--border);border-radius:999px;
      font-size:10px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
      color:var(--gold);background:var(--gold-dim);
    }
    .hero h1{
      max-width:820px;margin:0 auto 16px;
      font-family:var(--font-display);font-size:clamp(44px,7vw,76px);font-weight:500;
      line-height:1.04;letter-spacing:-.03em;color:var(--text);
    }
    .hero h1 em{font-style:italic;color:var(--gold)}
    .hero p{
      max-width:600px;margin:0 auto;
      color:var(--text-dim);font-size:16px;line-height:1.7;font-weight:400;
    }
    .trust{
      display:flex;justify-content:center;gap:22px;flex-wrap:wrap;margin-top:22px;
    }
    .trust span{
      display:flex;align-items:center;gap:7px;
      color:var(--text-muted);font-size:11px;letter-spacing:.02em;
    }
    .trust span::before{
      content:'';display:inline-block;width:4px;height:4px;border-radius:50%;background:var(--gold);
      box-shadow:0 0 6px var(--gold-glow);
    }

    /* ── Card Base ── */
    .card{
      position:relative;overflow:hidden;
      border:1px solid var(--border);border-radius:var(--radius-xl);
      background:linear-gradient(165deg,rgba(17,22,36,.82),rgba(12,16,28,.76));
      backdrop-filter:blur(12px);
      -webkit-backdrop-filter:blur(12px);
      box-shadow:var(--shadow-card);
    }
    .card::before{
      content:'';position:absolute;inset:0;pointer-events:none;
      background:linear-gradient(140deg,transparent 55%,rgba(212,168,83,.03) 100%);
      border-radius:inherit;
    }
    .card-glow{
      position:absolute;top:-40%;right:-20%;width:300px;height:300px;
      background:radial-gradient(circle,rgba(212,168,83,.04),transparent 70%);
      pointer-events:none;
    }

    /* ── Creator Form ── */
    .creator{padding:30px 32px 28px}
    .section-title{margin:0 0 5px;font-family:var(--font-display);font-size:24px;font-weight:500;letter-spacing:-.02em}
    .section-sub{margin:0 0 24px;color:var(--text-dim);font-size:13px}
    .field{margin-bottom:20px}
    .field label{display:block;margin:0 0 7px;font-size:12px;font-weight:600;color:var(--text-dim);letter-spacing:.01em}
    .field small{display:block;margin-top:6px;color:var(--text-muted);font-size:10px}
    .input,select{
      width:100%;height:52px;padding:0 16px;
      border:1px solid var(--border);border-radius:var(--radius-sm);
      background:rgba(8,11,20,.6);color:var(--text);
      font-family:var(--font-sans);font-size:14px;outline:none;transition:.25s;
    }
    .input::placeholder{color:var(--text-muted)}
    .input:focus,select:focus{border-color:var(--gold);box-shadow:0 0 0 3px var(--gold-dim)}
    .two{display:grid;grid-template-columns:1fr 1fr;gap:16px}

    .optional{
      margin:6px 0 22px;
      border:1px solid var(--border);border-radius:var(--radius-md);
      background:rgba(8,11,20,.35);overflow:hidden;transition:.25s;
    }
    .optional:hover{border-color:var(--border-hover)}
    .optional summary{padding:14px 16px;cursor:pointer;color:var(--text-muted);font-size:12px;font-weight:600;letter-spacing:.02em}
    .optional .inside{padding:0 16px 16px}

    .quality-label{margin:4px 0 12px;font-size:12px;font-weight:600;color:var(--text-dim)}
    .quality{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:26px}
    .quality input{position:absolute;opacity:0}
    .quality label{
      position:relative;display:block;min-height:110px;padding:16px 14px;
      border:1px solid var(--border);border-radius:var(--radius-md);
      cursor:pointer;background:rgba(8,11,20,.4);transition:.25s;overflow:hidden;
    }
    .quality label::before{
      content:'';position:absolute;inset:0;background:linear-gradient(140deg,transparent 50%,rgba(212,168,83,.02) 100%);
      opacity:0;transition:.3s;
    }
    .quality label:hover{border-color:var(--border-hover);transform:translateY(-1px)}
    .quality input:checked+label{
      border-color:var(--gold);box-shadow:0 0 0 1px var(--gold),0 8px 24px rgba(212,168,83,.08);
    }
    .quality input:checked+label::before{opacity:1}
    .quality strong{position:relative;display:block;font-size:14px;font-weight:600;color:var(--text)}
    .quality span{position:relative;display:block;margin-top:6px;color:var(--text-muted);font-size:10px;line-height:1.5}
    .quality em{
      position:relative;display:block;margin-top:10px;
      color:var(--gold);font-size:9px;font-style:normal;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
    }

    .primary{
      position:relative;width:100%;height:56px;overflow:hidden;
      border:0;border-radius:var(--radius-md);
      background:linear-gradient(135deg,#d4a853,#bf9530);
      color:#080b14;font-family:var(--font-sans);font-size:15px;font-weight:700;letter-spacing:-.01em;
      cursor:pointer;transition:.25s;
    }
    .primary:hover{transform:translateY(-2px);box-shadow:0 16px 36px rgba(212,168,83,.24)}
    .primary:active{transform:translateY(0)}
    .primary:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}

    .notice{
      display:none;margin-top:14px;padding:14px 16px;
      border:1px solid rgba(212,168,83,.15);border-radius:var(--radius-md);
      background:rgba(212,168,83,.06);color:var(--gold-soft);font-size:12px;line-height:1.6;
    }
    .notice code{color:var(--gold);font-size:11px}
    .notice.show{display:block}

    /* ── Progress ── */
    .progress-card{display:none;padding:32px 34px}
    .progress-card.show{display:block;animation:fadeUp .5s ease-out}

    .steps{
      display:grid;grid-template-columns:repeat(4,1fr);gap:0;margin-bottom:32px;
      counter-reset:step;
    }
    .step{position:relative;text-align:center;color:var(--text-muted);font-size:10px;font-weight:500}
    .step:not(:last-child)::after{
      content:'';position:absolute;left:58%;right:-42%;top:14px;height:1px;
      background:var(--border);transition:.6s;
    }
    .step i{
      position:relative;z-index:1;display:grid;place-items:center;
      width:29px;height:29px;margin:0 auto 8px;
      border:1px solid var(--border);border-radius:50%;
      background:var(--surface);font-style:normal;font-size:11px;transition:.5s;
    }
    .step.active,.step.done{color:var(--text)}
    .step.active i{border-color:var(--gold);color:var(--gold)}
    .step.done i{border-color:var(--gold);background:var(--gold);color:#080b14}
    .step.done:not(:last-child)::after{background:var(--gold);opacity:.5}

    .progress-title{text-align:center;margin:0 0 6px;font-family:var(--font-display);font-size:24px;font-weight:500}
    .progress-text{text-align:center;margin:0;color:var(--text-dim);font-size:13px}

    .track{height:6px;margin:28px 0 10px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.04)}
    .bar{
      height:100%;width:0;border-radius:999px;transition:width .5s cubic-bezier(.22,1,.36,1);
      background:linear-gradient(90deg,#bf9530,#d4a853,#e8c97a);
      box-shadow:0 0 12px rgba(212,168,83,.15);
    }
    .progress-meta{display:flex;justify-content:space-between;color:var(--text-muted);font-size:10px}

    .technical{margin-top:20px;text-align:center}
    .technical details summary{cursor:pointer;color:var(--text-muted);font-size:10px}
    .technical pre{
      max-height:130px;overflow:auto;text-align:left;white-space:pre-wrap;
      color:var(--text-muted);font:10px/1.5 ui-monospace,monospace;padding-top:8px;
    }

    /* ── Error ── */
    .error-card{display:none;padding:28px 32px;border-color:rgba(231,76,76,.2);background:var(--danger-bg)}
    .error-card.show{display:block;animation:fadeUp .4s ease-out}
    .error-card h2{margin:0 0 7px;color:var(--danger);font-size:20px;font-family:var(--font-display);font-weight:500}
    .error-card p{margin:0;color:rgba(255,255,255,.5);font-size:12px;line-height:1.6}
    .error-actions{display:flex;gap:10px;margin-top:18px}
    .secondary{
      height:42px;padding:0 18px;
      border:1px solid var(--border);border-radius:var(--radius-sm);
      background:transparent;color:var(--text);font-family:var(--font-sans);font-size:12px;font-weight:600;
      cursor:pointer;transition:.2s;text-decoration:none;display:inline-flex;align-items:center;
    }
    .secondary:hover{background:rgba(255,255,255,.04);border-color:var(--border-hover)}

    /* ── Result ── */
    .result{display:none}
    .result.show{display:block;animation:fadeUp .5s ease-out}
    .result-head{
      padding:28px 32px;display:flex;align-items:flex-start;justify-content:space-between;gap:20px;
      border-bottom:1px solid var(--border);
    }
    .success-mark{
      width:40px;height:40px;display:grid;place-items:center;flex-shrink:0;
      border-radius:50%;background:rgba(92,204,122,.12);color:var(--success);font-size:18px;font-weight:700;
    }
    .result-title{display:flex;gap:14px}
    .result-title h2{margin:0 0 4px;font-family:var(--font-display);font-size:24px;font-weight:500}
    .result-title p{margin:0;color:var(--text-dim);font-size:11px}
    .result-actions{display:flex;gap:8px;flex-shrink:0}
    .download{
      height:40px;display:inline-flex;align-items:center;gap:6px;padding:0 16px;
      border-radius:var(--radius-sm);background:linear-gradient(135deg,#d4a853,#bf9530);
      color:#080b14;text-decoration:none;font-size:11px;font-weight:700;transition:.2s;
    }
    .download:hover{transform:translateY(-1px);box-shadow:0 8px 20px rgba(212,168,83,.2)}

    .result-body{padding:22px}
    .output{margin-bottom:14px;border:1px solid var(--border);border-radius:var(--radius-md);overflow:hidden}
    .output-head{
      min-height:46px;padding:10px 12px 10px 18px;
      display:flex;align-items:center;justify-content:space-between;
      border-bottom:1px solid var(--border);background:rgba(255,255,255,.015);
    }
    .output-head h3{margin:0;font-size:12px;font-weight:600;color:var(--text-dim);letter-spacing:.02em}
    .copy{
      height:30px;padding:0 12px;
      border:1px solid var(--border);border-radius:6px;
      background:rgba(255,255,255,.03);color:var(--text-muted);font-size:10px;font-weight:600;
      cursor:pointer;transition:.2s;
    }
    .copy:hover{border-color:var(--border-hover);color:var(--text)}
    .copy.copied{border-color:var(--gold);background:var(--gold-dim);color:var(--gold)}
    .output-content{
      padding:16px 18px;
      color:var(--text);font-size:13px;line-height:1.7;white-space:pre-wrap;
    }
    .tags{display:flex;gap:6px;flex-wrap:wrap}
    .tag{
      padding:6px 12px;border-radius:999px;
      background:var(--gold-dim);color:var(--gold-soft);font-size:11px;font-weight:600;
      border:1px solid rgba(212,168,83,.08);
    }

    .packages{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
    .package{
      padding:18px;border:1px solid var(--border);border-radius:var(--radius-md);
      background:rgba(8,11,20,.35);transition:.25s;
    }
    .package:hover{border-color:var(--border-hover);transform:translateY(-2px)}
    .package.premium{
      border-color:rgba(212,168,83,.2);background:rgba(212,168,83,.04);
    }
    .package-name{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
    .package-name strong{font-size:14px;font-weight:600}
    .package-name span{font-size:20px;font-weight:700;color:var(--gold)}
    .package p{min-height:30px;color:var(--text-dim);font-size:11px;line-height:1.5;margin:0 0 10px}
    .package ul{padding-left:18px;margin:0;color:var(--text-muted);font-size:10px;line-height:1.7}

    .faq details{border-bottom:1px solid rgba(255,255,255,.04)}
    .faq details:last-child{border:0}
    .faq summary{padding:13px 0;cursor:pointer;font-size:13px;font-weight:600;color:var(--text);transition:.2s}
    .faq summary:hover{color:var(--gold-soft)}
    .faq p{margin:0 0 14px;color:var(--text-dim);font-size:12px;line-height:1.6}

    .review-box{
      padding:16px 18px;border:1px solid var(--border);border-radius:var(--radius-md);
      background:rgba(8,11,20,.35);
    }
    .review-box.good{border-color:rgba(92,204,122,.15);background:rgba(92,204,122,.04)}
    .review-box h4{margin:0 0 8px;font-size:13px;font-weight:600}
    .review-box ul{margin:0;padding-left:20px;color:var(--text-dim);font-size:12px;line-height:1.7}

    .disclaimer{margin-top:16px;color:var(--text-muted);font-size:10px;line-height:1.6}
    .start-over{
      margin-top:16px;width:100%;height:48px;
      border:1px solid var(--border);border-radius:var(--radius-md);
      background:transparent;color:var(--text);font-family:var(--font-sans);font-size:13px;font-weight:600;
      cursor:pointer;transition:.2s;
    }
    .start-over:hover{background:rgba(255,255,255,.03);border-color:var(--border-hover)}

    /* ── Footer ── */
    footer{
      padding:40px 0 20px;display:flex;align-items:center;justify-content:space-between;
      color:var(--text-muted);font-size:10px;
    }
    .advanced-link{color:var(--gold);text-decoration:none;font-size:11px;font-weight:600;transition:.2s}
    .advanced-link:hover{color:var(--gold-soft);text-decoration:underline}

    /* ── Responsive ── */
    @media(max-width:760px){
      .shell{width:min(100% - 24px,1080px);padding-top:8px}
      .topbar{padding:12px 16px}
      .hero{padding:48px 0 28px}
      .hero h1{font-size:38px}
      .hero p{font-size:13px}
      .creator,.progress-card{padding:20px}
      .two,.quality,.packages{grid-template-columns:1fr}
      .result-head{flex-direction:column}
      .result-actions{width:100%}
      .download{flex:1;justify-content:center}
      footer{flex-direction:column;gap:12px;text-align:center}
      .quality label{min-height:94px}
      .steps{font-size:8px}
    }
  </style>
</head>
<body>
<div class="noise"></div>
<main class="shell">
  <header class="topbar" style="animation:fadeUp .7s .1s both">
    <div class="brand">
      <span class="logo">GC</span>
      <div class="brand-text"><strong>GigCraft</strong><small>Fiverr gig studio</small></div>
    </div>
    <div class="status-pill"><span id="keyDot" class="dot"></span><span id="keyText">Checking AI…</span></div>
  </header>

  <section class="hero">
    <div class="eyebrow">Research-backed Fiverr gig creator</div>
    <h1>Your Fiverr gig,<br><em>crafted with precision.</em></h1>
    <p>Tell us what service you sell. We research the market, decode buyer intent, and deliver a polished, copy-ready gig that stands out.</p>
    <div class="trust"><span>Real competitor research</span><span>Copy-ready content</span><span>Human review before publishing</span></div>
  </section>

  <section id="creator" class="card creator" style="animation:fadeUp .7s .25s both">
    <div class="card-glow"></div>
    <h2 class="section-title">What service are you selling?</h2>
    <p class="section-sub">Be specific. For example: &ldquo;Looker Studio dashboards for ecommerce brands.&rdquo;</p>
    <form id="createForm">
      <div class="field">
        <label for="niche">Your service or niche</label>
        <input id="niche" class="input" required minlength="2" maxlength="100" placeholder="e.g. Looker Studio dashboard">
      </div>
      <div class="two">
        <div class="field"><label for="buyer">Ideal customer <span style="font-weight:400;color:var(--text-muted)">— optional</span></label><input id="buyer" class="input" maxlength="200" placeholder="e.g. ecommerce marketing teams"><small>Leave blank and we will infer it.</small></div>
        <div class="field"><label for="language">Gig language</label><select id="language"><option>English</option><option>Urdu</option><option>Spanish</option><option>French</option><option>German</option></select></div>
      </div>
      <details class="optional"><summary>Already have a gig? Add it for improvement</summary><div class="inside"><input id="existingUrl" class="input" maxlength="500" placeholder="https://www.fiverr.com/username/gig-name"><small>The URL should appear in this market's crawl to enable a direct before/after comparison.</small></div></details>
      <div class="quality-label">How much research should we do?</div>
      <div class="quality">
        <div><input type="radio" name="quality" id="qFast" value="fast"><label for="qFast"><strong>Quick</strong><span>10 competitors. Good for a fast first draft.</span><em>Fastest</em></label></div>
        <div><input type="radio" name="quality" id="qRecommended" value="recommended" checked><label for="qRecommended"><strong>Recommended</strong><span>25 competitors plus buyer-intent analysis.</span><em>Best balance</em></label></div>
        <div><input type="radio" name="quality" id="qBest" value="best"><label for="qBest"><strong>Best quality</strong><span>50 competitors and deeper AI refinement.</span><em>Most detailed</em></label></div>
      </div>
      <button id="createButton" class="primary" type="submit">Create My Fiverr Gig</button>
      <div id="keyNotice" class="notice">AI is not connected yet. Add a new OpenRouter key to your local <code>.env</code> file, restart the app, then try again. Dry-run tools remain available in the Advanced dashboard.</div>
    </form>
  </section>

  <section id="progress" class="card progress-card">
    <div class="card-glow"></div>
    <div class="steps">
      <div class="step active" data-step="research"><i>1</i>Research</div>
      <div class="step" data-step="understand"><i>2</i>Buyer needs</div>
      <div class="step" data-step="build"><i>3</i>Build gig</div>
      <div class="step" data-step="ready"><i>✓</i>Ready</div>
    </div>
    <h2 id="progressTitle" class="progress-title">Researching your market&hellip;</h2>
    <p id="progressText" class="progress-text">Finding relevant competitors and pricing patterns.</p>
    <div class="track"><div id="progressBar" class="bar"></div></div>
    <div class="progress-meta"><span id="progressPercent">0%</span><span id="progressHint">You can leave this tab open</span></div>
    <div class="technical"><details><summary>Technical progress</summary><pre id="technicalLog"></pre></details></div>
  </section>

  <section id="errorCard" class="card error-card">
    <h2>We couldn&rsquo;t finish this run.</h2><p id="friendlyError"></p>
    <div class="error-actions"><button id="retryButton" class="secondary" type="button">Try again</button><a class="secondary" href="/advanced">Open diagnostics</a></div>
    <details class="technical"><summary>Technical details</summary><pre id="errorDetails"></pre></details>
  </section>

  <section id="result" class="card result">
    <div class="result-head">
      <div class="result-title"><span class="success-mark">✓</span><div><h2>Your Fiverr gig is ready</h2><p>Review, copy, and paste each section into Fiverr.</p></div></div>
      <div class="result-actions"><button id="copyAll" class="secondary" type="button">Copy everything</button><a id="download" class="download" href="#">Download draft</a></div>
    </div>
    <div id="resultBody" class="result-body"></div>
  </section>

  <footer><span>GigCraft improves your research and presentation — it cannot guarantee Fiverr rankings or orders.</span><a class="advanced-link" href="/advanced">Advanced dashboard &rarr;</a></footer>
</main>
<script>
const $=id=>document.getElementById(id);let aiConfigured=false,currentState=null,lastInputs=null;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function api(url,opts={}){const r=await fetch(url,opts);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.detail||'Request failed: '+r.status);return d}

function setProgress(pct,title,text,stage){
  $('progressBar').style.width=Math.max(0,Math.min(100,pct))+'%';
  $('progressPercent').textContent=Math.round(pct)+'%';
  $('progressTitle').textContent=title;$('progressText').textContent=text;
  const order=['research','understand','build','ready'],active=order.indexOf(stage);
  document.querySelectorAll('.step').forEach((n,i)=>{n.classList.toggle('done',i<active);n.classList.toggle('active',i===active)});
  log(title+' — '+text)
}
function log(m){$('technicalLog').textContent+=new Date().toLocaleTimeString()+'  '+m+'\n';$('technicalLog').scrollTop=$('technicalLog').scrollHeight}
function saveState(){if(currentState)localStorage.setItem('gigcraft-workflow',JSON.stringify(currentState));else localStorage.removeItem('gigcraft-workflow')}

function friendly(m){
  const t=String(m||'');
  if(/API_KEY|not configured/i.test(t))return 'AI is not connected. Add a new OpenRouter key to the local .env file and restart the app.';
  if(/No endpoints found/i.test(t))return 'The selected AI provider is temporarily unavailable. Please retry in a moment.';
  if(/JSON|truncated|parse/i.test(t))return 'The AI response was incomplete. Retry once, preferably with Recommended quality.';
  if(/budget|cost cap/i.test(t))return 'Your safety spending limit stopped this request. Increase the local cost cap only if you intend to.';
  if(/Reader|Jina|network|timeout/i.test(t))return 'Public market data could not be reached. Check your internet connection and retry.';
  if(/429|rate limit|too many requests|retried \d+ times/i.test(t))return 'The AI provider is temporarily overloaded. The app automatically retried but it still failed — try again in 30 seconds.';
  return 'Something interrupted the process. Your saved research may still be available in the Advanced dashboard.'
}
function showError(e){
  $('progress').classList.remove('show');$('errorCard').classList.add('show');
  $('friendlyError').textContent=friendly(e.message);$('errorDetails').textContent=e.stack||e.message;
  $('createButton').disabled=false;$('createButton').textContent='Create My Fiverr Gig';log('ERROR: '+e.message)
}
async function runWorkflow(inputs,resume){
  lastInputs=inputs;$('creator').style.display='none';$('errorCard').classList.remove('show');
  $('result').classList.remove('show');$('progress').classList.add('show');$('technicalLog').textContent='';
  try{
    let wid=resume&&resume.workflowId;
    if(!wid){
      setProgress(2,'Starting your project…','Preparing the research workflow.','research');
      const w=await api('/api/simple-workflows',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        niche:inputs.niche,quality:inputs.quality,buyer:inputs.buyer||'',language:inputs.language,existing_url:inputs.existingUrl||null
      })});wid=w.id;currentState={inputs,workflowId:wid};saveState()
    }
    const started=Date.now();let lastSig='';
    while(1){
      const s=await api('/api/simple-workflows/'+wid),stage=s.stage||'research',pct=Number(s.progress_percent||0);
      let title='Researching your market…',text=s.message||'Finding relevant competitors and pricing patterns.',vs='research';
      if(stage==='understand'){title='Understanding what buyers want…';vs='understand'}
      else if(stage==='build'){title='Building your gig…';vs='build'}
      else if(stage==='ready'||s.status==='completed'){title='Your gig is ready';text='Review and copy each section into Fiverr.';vs='ready'}
      setProgress(pct,title,text,vs);
      const sig=[s.status,stage,Math.round(pct),s.message].join('|');
      if(sig!==lastSig){log(sig);lastSig=sig}
      if(s.status==='completed'){
        const g=await api('/api/simple-workflows/'+wid+'/result');
        setProgress(100,'Your gig is ready','Review and copy each section into Fiverr.','ready');
        await sleep(350);renderResult(g,{markdown_url:s.markdown_url});
        currentState=null;saveState();$('progress').classList.remove('show');$('result').classList.add('show');
        window.scrollTo({top:$('result').offsetTop-20,behavior:'smooth'});return
      }
      if(['failed','interrupted','cancelled'].includes(s.status))throw new Error(s.error||s.message||'The workflow did not complete.');
      if(Date.now()-started>120*60000)throw new Error('This project is taking longer than expected. Open diagnostics for details.');
      await sleep(1400)
    }
  }catch(e){showError(e)}
}
function copyBtn(text){const b=document.createElement('button');b.className='copy';b.type='button';b.textContent='Copy';b.onclick=()=>copy(text,b);return b}
async function copy(text,b){
  try{if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(text);else{const a=document.createElement('textarea');a.value=text;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}if(b){b.textContent='Copied ✓';b.classList.add('copied');setTimeout(()=>{b.textContent='Copy';b.classList.remove('copied')},1300)}}catch{if(b)b.textContent='Select manually'}
}
function out(title,content){const box=document.createElement('section');box.className='output';const h=document.createElement('div');h.className='output-head';const t=document.createElement('h3');t.textContent=title;h.append(t,copyBtn(content));const b=document.createElement('div');b.className='output-content';b.textContent=content;box.append(h,b);return box}
function renderResult(result,run){
  const root=$('resultBody');root.replaceChildren();
  if(result.dry_run){root.append(out('Dry run plan',JSON.stringify(result,null,2)));return}
  const f=result.final||{},gig=f.recommended_gig||{},visual=f.visual_system||{};
  root.append(out('Gig title',gig.title||''));
  const tb=document.createElement('section');tb.className='output';
  const th=document.createElement('div');th.className='output-head';
  const tt=document.createElement('h3');tt.textContent='Search tags';
  th.append(tt,copyBtn((gig.tags||[]).join(', ')));
  const tags=document.createElement('div');tags.className='output-content tags';
  for(const tag of gig.tags||[]){const n=document.createElement('span');n.className='tag';n.textContent=tag;tags.appendChild(n)}
  tb.append(th,tags);root.appendChild(tb);
  root.append(out('Gig description',gig.description||''));
  const pb=document.createElement('section');pb.className='output';
  const ph=document.createElement('div');ph.className='output-head';
  const pt=document.createElement('h3');pt.textContent='Packages';
  ph.append(pt,copyBtn(ptext(gig.packages||[])));
  const cards=document.createElement('div');cards.className='output-content packages';
  for(const pkg of gig.packages||[]){
    const c=document.createElement('div');c.className='package'+(pkg.name==='Premium'?' premium':'');
    const nm=document.createElement('div');nm.className='package-name';
    const s=document.createElement('strong');s.textContent=pkg.name;
    const pr=document.createElement('span');pr.textContent='$'+pkg.price_usd;
    nm.append(s,pr);const d=document.createElement('p');d.textContent=pkg.description;
    const ul=document.createElement('ul');
    for(const item of pkg.deliverables||[]){const li=document.createElement('li');li.textContent=item;ul.appendChild(li)}
    c.append(nm,d,ul);cards.appendChild(c)
  }
  pb.append(ph,cards);root.appendChild(pb);
  const fb=document.createElement('section');fb.className='output';
  const fh=document.createElement('div');fh.className='output-head';
  const ft=document.createElement('h3');ft.textContent='Frequently asked questions';
  fh.append(ft,copyBtn(ftext(gig.faqs||[])));
  const faq=document.createElement('div');faq.className='output-content faq';
  for(const item of gig.faqs||[]){
    const d=document.createElement('details');const s=document.createElement('summary');s.textContent=item.question;
    const p=document.createElement('p');p.textContent=item.answer;d.append(s,p);faq.appendChild(d)
  }
  fb.append(fh,faq);root.appendChild(fb);
  root.append(out('Buyer requirements',(gig.buyer_requirements||[]).map((x,i)=>(i+1)+'. '+x).join('\n')));
  root.append(out('Scope exclusions',(gig.scope_exclusions||[]).map(x=>'\u2022 '+x).join('\n')));
  root.append(out('Call to action',gig.cta||''));
  root.append(out('Thumbnail text',[visual.thumbnail_headline,visual.thumbnail_subheadline].filter(Boolean).join('\n')));
  root.append(out('Video script',vtext(visual.video_script||{})));
  const v=result.validation||{},rb=document.createElement('div');rb.className='review-box'+(v.passed?' good':'');
  const rh=document.createElement('h4');rh.textContent=v.passed?'Ready for your review':'Please review these items';
  const ul=document.createElement('ul');const items=[...(result.warnings||[]),...(v.issues||[]),...(v.warnings||[])];
  if(!items.length)items.push('No blocking issue was detected. Always check Fiverr\u2019s latest policies before publishing.');
  for(const item of items){const li=document.createElement('li');li.textContent=item;ul.appendChild(li)}
  rb.append(rh,ul);root.appendChild(rb);
  const note=document.createElement('p');note.className='disclaimer';
  note.textContent='This draft is based on public market research and AI assistance. It cannot guarantee ranking, impressions, clicks, or orders. Edit claims and prices to match what you can genuinely deliver.';
  root.appendChild(note);
  const rst=document.createElement('button');rst.className='start-over';rst.textContent='Create another gig';rst.onclick=reset;root.appendChild(rst);
  $('download').href=run.markdown_url;$('copyAll').onclick=()=>copy(ftxt(gig,visual))
}
function ptext(pkgs){return pkgs.map(p=>`${p.name} \u2014 $${p.price_usd}\n${p.description}\nDelivery: ${p.delivery_days} days | Revisions: ${p.revisions}\n${(p.deliverables||[]).map(x=>'\u2022 '+x).join('\n')}`).join('\n\n')}
function ftext(faqs){return faqs.map(x=>x.question+'\n'+x.answer).join('\n\n')}
function vtext(v){return['Hook: '+(v.hook||''),'Problem: '+(v.problem||''),'Solution: '+(v.solution||''),'Proof: '+(v.proof||''),'CTA: '+(v.cta||'')].join('\n\n')}
function ftxt(gig,visual){return['TITLE\n'+(gig.title||''),'TAGS\n'+(gig.tags||[]).join(', '),'DESCRIPTION\n'+(gig.description||''),'PACKAGES\n'+ptext(gig.packages||[]),'FAQS\n'+ftext(gig.faqs||[]),'BUYER REQUIREMENTS\n'+(gig.buyer_requirements||[]).join('\n'),'SCOPE EXCLUSIONS\n'+(gig.scope_exclusions||[]).join('\n'),'CTA\n'+(gig.cta||''),'THUMBNAIL\n'+[visual.thumbnail_headline,visual.thumbnail_subheadline].filter(Boolean).join('\n'),'VIDEO SCRIPT\n'+vtext(visual.video_script||{})].join('\n\n')}
function reset(){$('result').classList.remove('show');$('errorCard').classList.remove('show');$('creator').style.display='block';$('createButton').disabled=false;$('createButton').textContent='Create My Fiverr Gig';currentState=null;saveState();window.scrollTo({top:$('creator').offsetTop-20,behavior:'smooth'})}
$('createForm').addEventListener('submit',async e=>{e.preventDefault();if(!aiConfigured){$('keyNotice').classList.add('show');return}$('keyNotice').classList.remove('show');const inputs={niche:$('niche').value.trim(),buyer:$('buyer').value.trim(),language:$('language').value,existingUrl:$('existingUrl').value.trim(),quality:document.querySelector('input[name=quality]:checked').value};lastInputs=inputs;$('createButton').disabled=true;$('createButton').textContent='Starting\u2026';await runWorkflow(inputs)});
$('retryButton').onclick=()=>{if(lastInputs){$('errorCard').classList.remove('show');runWorkflow(lastInputs)}else reset()};
(async()=>{try{const config=await api('/api/ai/config');aiConfigured=Boolean(config.configured);$('keyDot').classList.toggle('on',aiConfigured);$('keyText').textContent=aiConfigured?'AI connected':'AI setup needed'}catch{$('keyText').textContent='Offline'}const saved=localStorage.getItem('gigcraft-workflow');if(saved){try{const state=JSON.parse(saved);currentState=state;lastInputs=state.inputs;await runWorkflow(state.inputs,state)}catch(error){localStorage.removeItem('gigcraft-workflow');showError(error)}}})();
</script>
</body>
</html>"""