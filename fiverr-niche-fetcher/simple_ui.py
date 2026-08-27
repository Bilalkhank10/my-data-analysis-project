"""GigCraft Studio — ChatGPT / Claude / Apple-inspired product surface."""

SIMPLE_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GigCraft</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,480;8..60,560&display=swap" rel="stylesheet">
  <meta name="theme-color" content="#f4f3ee">
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div class="scrim" id="scrim"></div>
<div class="app-shell">
  <aside class="sidebar">
    <a class="brand" href="/">
      <span class="mark">G</span>
      <div><strong class="brand-name">GigCraft</strong><small class="brand-sub">Studio</small></div>
    </a>
    <nav class="nav">
      <a class="active" href="/"><span class="ico">✦</span>New draft</a>
      <a href="/advanced"><span class="ico">▣</span>Lab</a>
    </nav>
    <div class="side-foot">
      <div class="status-row"><span id="keyDot" class="dot"></span><span id="keyText">Checking AI…</span></div>
    </div>
  </aside>

  <div class="stage">
    <header class="top">
      <button class="menu-btn" id="menuBtn" type="button" aria-label="Open menu">☰</button>
      <div class="top-title">Draft a Fiverr gig</div>
    </header>

    <main class="canvas">
      <section class="hero" id="hero">
        <h1>What should this gig sell?</h1>
        <p>Describe the service. GigCraft researches the market and writes a copy-ready listing.</p>
      </section>

      <section id="creator" class="composer">
        <form id="createForm">
          <div class="field">
            <label for="niche">Service</label>
            <input id="niche" class="input" required minlength="2" maxlength="100" placeholder="Looker Studio dashboards for ecommerce brands" autofocus>
          </div>
          <div class="grid-2">
            <div class="field">
              <label for="buyer">Ideal buyer <span style="font-weight:450;color:var(--faint)">optional</span></label>
              <input id="buyer" class="input" maxlength="200" placeholder="Ecommerce marketing teams">
              <small>Leave blank and we’ll infer it from the market.</small>
            </div>
            <div class="field">
              <label for="language">Language</label>
              <select id="language">
                <option>English</option>
                <option>Urdu</option>
                <option>Spanish</option>
                <option>French</option>
                <option>German</option>
              </select>
            </div>
          </div>
          <details class="optional">
            <summary>Improve an existing gig</summary>
            <div class="inside">
              <input id="existingUrl" class="input" maxlength="500" placeholder="https://www.fiverr.com/username/gig-name">
              <small>The URL needs to appear in this market’s crawl for a before/after comparison.</small>
            </div>
          </details>
          <div class="depth">
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
          <div id="keyNotice" class="notice">AI isn’t connected. Add a new OpenRouter key to your local <code>.env</code> file, restart, then try again. Lab still supports dry runs.</div>
        </form>
      </section>

      <section id="progress" class="composer progress-card" style="margin-top:16px">
        <div class="steps">
          <div class="step active" data-step="research"><i>1</i>Research</div>
          <div class="step" data-step="understand"><i>2</i>Buyers</div>
          <div class="step" data-step="build"><i>3</i>Write</div>
          <div class="step" data-step="ready"><i>✓</i>Ready</div>
        </div>
        <h2 id="progressTitle" class="progress-title">Researching your market…</h2>
        <p id="progressText" class="progress-text">Finding competitors, prices, and buyer language.</p>
        <div class="track"><div id="progressBar" class="bar"></div></div>
        <div class="progress-meta"><span id="progressPercent">0%</span><span id="progressHint">You can leave this tab open</span></div>
        <div class="technical"><details><summary>Technical log</summary><pre id="technicalLog"></pre></details></div>
      </section>

      <section id="errorCard" class="composer error-card" style="margin-top:16px">
        <h2>We couldn’t finish this run.</h2>
        <p id="friendlyError"></p>
        <div class="error-actions">
          <button id="retryButton" class="btn" type="button">Try again</button>
          <a class="btn ghost" href="/advanced">Open Lab</a>
        </div>
        <details class="technical"><summary>Technical details</summary><pre id="errorDetails"></pre></details>
      </section>

      <section id="result" class="composer result" style="margin-top:16px;padding:0">
        <div class="result-head">
          <div class="result-title">
            <h2>Your gig is ready</h2>
            <p>Review, copy, and paste each section into Fiverr.</p>
          </div>
          <div class="result-actions">
            <button id="copyAll" class="btn" type="button">Copy all</button>
            <a id="download" class="btn primary" href="#" style="width:auto;padding:0 16px">Download</a>
          </div>
        </div>
        <div id="resultBody" class="result-body"></div>
      </section>
    </main>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);let aiConfigured=false,currentState=null,lastInputs=null;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function detailMessage(d,fallback){const x=d&&d.detail;if(!x)return fallback;if(typeof x==='string')return x;if(Array.isArray(x))return x.map(i=>i.msg||i.message||JSON.stringify(i)).join('; ');return x.message||x.msg||JSON.stringify(x)}
async function api(url,opts={}){const r=await fetch(url,opts);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(detailMessage(d,'Request failed: '+r.status));return d}
$('menuBtn').onclick=()=>document.body.classList.add('nav-open');
$('scrim').onclick=()=>document.body.classList.remove('nav-open');

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
  if(/429|rate limit|too many requests|retried \d+ times/i.test(t))return 'The AI provider is temporarily overloaded. Try again in 30 seconds.';
  return 'Something interrupted the process. Saved research may still be available in Lab.'
}
function showError(e){
  $('progress').classList.remove('show');$('errorCard').classList.add('show');
  $('friendlyError').textContent=friendly(e.message);$('errorDetails').textContent=e.stack||e.message;
  $('createButton').disabled=false;$('createButton').textContent='Create draft';log('ERROR: '+e.message)
}
async function runWorkflow(inputs,resume){
  lastInputs=inputs;$('creator').style.display='none';$('hero').style.display='none';$('errorCard').classList.remove('show');
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
      else if(stage==='build'){title='Writing your gig…';vs='build'}
      else if(stage==='ready'||s.status==='completed'){title='Your gig is ready';text='Review and copy each section into Fiverr.';vs='ready'}
      setProgress(pct,title,text,vs);
      const sig=[s.status,stage,Math.round(pct),s.message].join('|');
      if(sig!==lastSig){log(sig);lastSig=sig}
      if(s.status==='completed'){
        const g=await api('/api/simple-workflows/'+wid+'/result');
        setProgress(100,'Your gig is ready','Review and copy each section into Fiverr.','ready');
        await sleep(280);renderResult(g,{markdown_url:s.markdown_url});
        currentState=null;saveState();$('progress').classList.remove('show');$('result').classList.add('show');
        window.scrollTo({top:0,behavior:'smooth'});return
      }
      if(['failed','interrupted','cancelled'].includes(s.status))throw new Error(s.error||s.message||'The workflow did not complete.');
      if(Date.now()-started>120*60000)throw new Error('This project is taking longer than expected. Open Lab for details.');
      await sleep(1400)
    }
  }catch(e){showError(e)}
}
function copyBtn(text){const b=document.createElement('button');b.className='copy';b.type='button';b.textContent='Copy';b.onclick=()=>copy(text,b);return b}
async function copy(text,b){
  try{if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(text);else{const a=document.createElement('textarea');a.value=text;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}if(b){b.textContent='Copied';b.classList.add('copied');setTimeout(()=>{b.textContent='Copy';b.classList.remove('copied')},1300)}}catch{if(b)b.textContent='Select manually'}
}
function out(title,content){const box=document.createElement('section');box.className='output';const h=document.createElement('div');h.className='output-head';const t=document.createElement('h3');t.textContent=title;h.append(t,copyBtn(content));const b=document.createElement('div');b.className='output-content';b.textContent=content;box.append(h,b);return box}
function renderResult(result,run){
  const root=$('resultBody');root.replaceChildren();
  if(result.dry_run){root.append(out('Dry run plan',JSON.stringify(result,null,2)));return}
  const f=result.final||{},gig=f.recommended_gig||{},visual=f.visual_system||{};
  root.append(out('Title',gig.title||''));
  const tb=document.createElement('section');tb.className='output';
  const th=document.createElement('div');th.className='output-head';
  const tt=document.createElement('h3');tt.textContent='Tags';
  th.append(tt,copyBtn((gig.tags||[]).join(', ')));
  const tags=document.createElement('div');tags.className='output-content tags';
  for(const tag of gig.tags||[]){const n=document.createElement('span');n.className='tag';n.textContent=tag;tags.appendChild(n)}
  tb.append(th,tags);root.appendChild(tb);
  root.append(out('Description',gig.description||''));
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
  const ft=document.createElement('h3');ft.textContent='FAQ';
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
  root.append(out('Thumbnail',[visual.thumbnail_headline,visual.thumbnail_subheadline].filter(Boolean).join('\n')));
  root.append(out('Video script',vtext(visual.video_script||{})));
  const v=result.validation||{},rb=document.createElement('div');rb.className='review-box'+(v.passed?' good':'');
  const rh=document.createElement('h4');rh.textContent=v.passed?'Ready for your review':'Please review these items';
  const ul=document.createElement('ul');const items=[...(result.warnings||[]),...(v.issues||[]),...(v.warnings||[])];
  if(!items.length)items.push('No blocking issue was detected. Always check Fiverr\u2019s latest policies before publishing.');
  for(const item of items){const li=document.createElement('li');li.textContent=item;ul.appendChild(li)}
  rb.append(rh,ul);root.appendChild(rb);
  const note=document.createElement('p');note.className='disclaimer';
  note.textContent='This draft is based on public market research and AI assistance. It cannot guarantee ranking or orders. Edit claims and prices to match what you can deliver.';
  root.appendChild(note);
  const rst=document.createElement('button');rst.className='btn start-over';rst.textContent='Create another gig';rst.onclick=reset;root.appendChild(rst);
  $('download').href=run.markdown_url;$('copyAll').onclick=()=>copy(ftxt(gig,visual))
}
function ptext(pkgs){return pkgs.map(p=>`${p.name} \u2014 $${p.price_usd}\n${p.description}\nDelivery: ${p.delivery_days} days | Revisions: ${p.revisions}\n${(p.deliverables||[]).map(x=>'\u2022 '+x).join('\n')}`).join('\n\n')}
function ftext(faqs){return faqs.map(x=>x.question+'\n'+x.answer).join('\n\n')}
function vtext(v){return['Hook: '+(v.hook||''),'Problem: '+(v.problem||''),'Solution: '+(v.solution||''),'Proof: '+(v.proof||''),'CTA: '+(v.cta||'')].join('\n\n')}
function ftxt(gig,visual){return['TITLE\n'+(gig.title||''),'TAGS\n'+(gig.tags||[]).join(', '),'DESCRIPTION\n'+(gig.description||''),'PACKAGES\n'+ptext(gig.packages||[]),'FAQS\n'+ftext(gig.faqs||[]),'BUYER REQUIREMENTS\n'+(gig.buyer_requirements||[]).join('\n'),'SCOPE EXCLUSIONS\n'+(gig.scope_exclusions||[]).join('\n'),'CTA\n'+(gig.cta||''),'THUMBNAIL\n'+[visual.thumbnail_headline,visual.thumbnail_subheadline].filter(Boolean).join('\n'),'VIDEO SCRIPT\n'+vtext(visual.video_script||{})].join('\n\n')}
function reset(){$('result').classList.remove('show');$('errorCard').classList.remove('show');$('creator').style.display='block';$('hero').style.display='block';$('createButton').disabled=false;$('createButton').textContent='Create draft';currentState=null;saveState();window.scrollTo({top:0,behavior:'smooth'})}
$('createForm').addEventListener('submit',async e=>{e.preventDefault();if(!aiConfigured){$('keyNotice').classList.add('show');return}$('keyNotice').classList.remove('show');const inputs={niche:$('niche').value.trim(),buyer:$('buyer').value.trim(),language:$('language').value,existingUrl:$('existingUrl').value.trim(),quality:document.querySelector('input[name=quality]:checked').value};lastInputs=inputs;$('createButton').disabled=true;$('createButton').textContent='Starting…';await runWorkflow(inputs)});
$('retryButton').onclick=()=>{if(lastInputs){$('errorCard').classList.remove('show');runWorkflow(lastInputs)}else reset()};
(async()=>{try{const config=await api('/api/ai/config');aiConfigured=Boolean(config.configured);$('keyDot').classList.toggle('on',aiConfigured);$('keyText').textContent=aiConfigured?'Ready':'Setup needed'}catch{$('keyText').textContent='Offline'}const saved=localStorage.getItem('gigcraft-workflow');if(saved){try{const state=JSON.parse(saved);currentState=state;lastInputs=state.inputs;await runWorkflow(state.inputs,state)}catch(error){localStorage.removeItem('gigcraft-workflow');showError(error)}}})();
</script>
</body>
</html>"""
