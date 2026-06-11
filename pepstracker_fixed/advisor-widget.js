(function() {
  if (document.getElementById('pt-advisor-fab')) return;
  var STARTERS = ['Cheapest Semaglutide?','What is BPC-157?','Best longevity compound?','Available discount codes?'];
  var msgs = [], loading = false, open = false;

  var sty = document.createElement('style');
  sty.textContent = '@import url(https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap);'
    + '#pt-advisor-fab{position:fixed;bottom:22px;right:22px;z-index:9999;width:54px;height:54px;border-radius:50%;'
    + 'background:linear-gradient(135deg,#3b9eff,#4de87a);border:none;cursor:pointer;'
    + 'box-shadow:0 4px 20px rgba(59,158,255,0.4);display:flex;align-items:center;justify-content:center;'
    + 'transition:transform .2s,box-shadow .2s;font-family:inherit;}'
    + '#pt-advisor-fab:hover{transform:scale(1.09);box-shadow:0 6px 26px rgba(59,158,255,0.5);}'
    + '#pt-advisor-fab:active{transform:scale(0.95);}'
    + '#pt-advisor-fab .ico-chat{transition:all .22s;}'
    + '#pt-advisor-fab.open .ico-chat{transform:scale(0) rotate(90deg);opacity:0;position:absolute;}'
    + '#pt-advisor-fab .ico-close{transform:scale(0) rotate(-90deg);opacity:0;position:absolute;transition:all .22s;}'
    + '#pt-advisor-fab.open .ico-close{transform:scale(1) rotate(0);opacity:1;position:absolute;}'
    + '#pt-panel{position:fixed;bottom:88px;right:22px;z-index:9998;width:334px;height:468px;'
    + 'background:#0d0f14;border-radius:16px;border:1px solid #1e2a3d;'
    + 'display:flex;flex-direction:column;font-family:"Plus Jakarta Sans","Segoe UI",system-ui,sans-serif;'
    + 'box-shadow:0 16px 50px rgba(0,0,0,0.65);opacity:0;pointer-events:none;'
    + 'transform:translateY(14px) scale(0.96);transform-origin:bottom right;'
    + 'transition:opacity .2s ease,transform .2s ease;}'
    + '#pt-panel.open{opacity:1;pointer-events:all;transform:translateY(0) scale(1);}'
    + '@media(max-width:380px){#pt-panel{width:calc(100vw - 12px);right:6px;bottom:76px;}#pt-advisor-fab{bottom:14px;right:14px;}}'
    + '.pt-hdr{padding:11px 13px;border-bottom:1px solid #1e2a3d;display:flex;align-items:center;gap:9px;flex-shrink:0;}'
    + '.pt-av{width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#3b9eff,#4de87a);'
    + 'display:flex;align-items:center;justify-content:center;font-weight:800;font-size:11px;color:#0d0f14;flex-shrink:0;}'
    + '.pt-hn{font-weight:700;font-size:13px;color:#e8edf5;line-height:1.2;}'
    + '.pt-hs{font-size:10px;color:#4de87a;display:flex;align-items:center;gap:3px;}'
    + '.pt-dot{width:5px;height:5px;border-radius:50%;background:#4de87a;}'
    + '.pt-msgs{flex:1;overflow-y:auto;padding:11px 11px 5px;scroll-behavior:smooth;}'
    + '.pt-msgs::-webkit-scrollbar{width:3px;}.pt-msgs::-webkit-scrollbar-thumb{background:#1e2a3d;border-radius:4px;}'
    + '.pt-welcome{text-align:center;padding:14px 6px 16px;animation:ptfu .3s ease;}'
    + '.pt-wav{width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#3b9eff,#4de87a);'
    + 'display:flex;align-items:center;justify-content:center;font-weight:800;font-size:17px;color:#0d0f14;margin:0 auto 9px;}'
    + '.pt-welcome h3{font-size:13.5px;font-weight:800;color:#e8edf5;margin:0 0 4px;}'
    + '.pt-welcome p{font-size:12px;color:#4a5a72;margin:0;line-height:1.5;}'
    + '.pt-chips{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:12px;}'
    + '.pt-chip{background:rgba(59,158,255,.08);border:1px solid rgba(59,158,255,.2);color:#7ab8ff;'
    + 'padding:5px 10px;border-radius:16px;font-size:11px;cursor:pointer;font-family:inherit;transition:all .15s;}'
    + '.pt-chip:hover{background:rgba(59,158,255,.16);color:#9ecfff;}'
    + '.pt-row{display:flex;margin-bottom:8px;animation:ptfu .2s ease;}'
    + '.pt-row.user{justify-content:flex-end;}.pt-row.ai{justify-content:flex-start;}'
    + '.pt-ai-av{width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,#3b9eff,#4de87a);'
    + 'display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:800;color:#0d0f14;'
    + 'margin-right:5px;flex-shrink:0;margin-top:2px;}'
    + '.pt-bbl{max-width:84%;border-radius:11px;padding:7px 10px;font-size:12px;line-height:1.62;}'
    + '.pt-bbl.user{background:#3b9eff;color:#fff;border-radius:11px 11px 3px 11px;}'
    + '.pt-bbl.ai{background:#141b27;color:#e8edf5;border:1px solid #1e2a3d;border-radius:3px 11px 11px 11px;}'
    + '.pt-cb{display:inline-flex;align-items:center;gap:4px;background:rgba(77,232,122,.1);'
    + 'border:1px solid rgba(77,232,122,.28);color:#4de87a;padding:4px 9px;border-radius:7px;'
    + 'font-size:11px;font-weight:700;text-decoration:none;margin:4px 2px 2px;cursor:pointer;'
    + 'font-family:inherit;transition:background .15s;}'
    + '.pt-cb:hover{background:rgba(77,232,122,.2);}'
    + '.pt-cur{display:inline-block;width:6px;height:11px;background:#4de87a;border-radius:2px;'
    + 'margin-left:2px;animation:ptbk .9s steps(1) infinite;}'
    + '.pt-ir{padding:7px 10px 10px;border-top:1px solid #1e2a3d;display:flex;gap:6px;align-items:center;flex-shrink:0;}'
    + '.pt-in{flex:1;background:#0d0f14;border:1px solid #1e2a3d;border-radius:7px;color:#e8edf5;'
    + 'padding:7px 10px;font-size:12px;font-family:inherit;outline:none;height:32px;}'
    + '.pt-in:focus{border-color:#3b9eff;}.pt-in::placeholder{color:#2a3a50;}'
    + '.pt-sb{width:32px;height:32px;background:#3b9eff;border:none;border-radius:7px;color:#fff;'
    + 'font-size:14px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;'
    + 'transition:all .15s;flex-shrink:0;font-family:inherit;}'
    + '.pt-sb:hover:not(:disabled){background:#2a8aef;}'
    + '.pt-sb:disabled{background:#1a2436;color:#2a3a50;cursor:not-allowed;}'
    + '.pt-ft{text-align:center;font-size:9px;color:#1e2a3d;padding:0 11px 8px;}'
    + '@keyframes ptfu{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}'
    + '@keyframes ptbk{0%,100%{opacity:1}50%{opacity:0}}';
  document.head.appendChild(sty);

  var fab = document.createElement('button');
  fab.id = 'pt-advisor-fab';
  fab.setAttribute('aria-label', 'Open Peptide Advisor');
  fab.innerHTML = '<svg class="ico-chat" width="23" height="23" fill="none" viewBox="0 0 24 24">'
    + '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="#0d0f14" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    + '</svg><svg class="ico-close" width="18" height="18" fill="none" viewBox="0 0 24 24">'
    + '<path d="M18 6L6 18M6 6l12 12" stroke="#0d0f14" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
    + '</svg>';
  document.body.appendChild(fab);

  var panel = document.createElement('div');
  panel.id = 'pt-panel';
  panel.innerHTML = '<div class="pt-hdr"><div class="pt-av">P</div>'
    + '<div><div class="pt-hn">Peptide Advisor</div><div class="pt-hs"><span class="pt-dot"></span> PepsTracker AI</div></div>'
    + '<div style="margin-left:auto;font-size:9.5px;color:#2a3a50;text-align:right;line-height:1.4">17 vendors<br>71 compounds</div></div>'
    + '<div class="pt-msgs" id="pt-msgs"></div>'
    + '<div class="pt-ir"><input class="pt-in" id="pt-in" placeholder="Ask about any compound..."/>'
    + '<button class="pt-sb" id="pt-sb" disabled>&#8593;</button></div>'
    + '<div class="pt-ft">For research purposes only &middot; pepstracker.com</div>';
  document.body.appendChild(panel);

  var msgsEl = document.getElementById('pt-msgs');
  var inEl = document.getElementById('pt-in');
  var sbEl = document.getElementById('pt-sb');

  function renderWelcome() {
    msgsEl.innerHTML = '<div class="pt-welcome"><div class="pt-wav">P</div>'
      + '<h3>Hi! I\'m your Peptide Advisor</h3>'
      + '<p>I know every vendor, compound &amp; discount code.</p>'
      + '<div class="pt-chips">'
      + STARTERS.map(function(s){ return '<button class="pt-chip" onclick="window.__ptSend(' + JSON.stringify(s) + ')">' + s + '</button>'; }).join('')
      + '</div></div>';
  }
  renderWelcome();

  function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function fmtBubble(m) {
    var html = esc(m.content).replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(_, label, href) {
      var url = href.startsWith('http') ? href : 'https://pepstracker.com' + href;
      return '<a class="pt-cb" href="' + url + '" target="_blank" rel="noopener">' + esc(label) + '</a>';
    });
    if (m.streaming) html += '<span class="pt-cur"></span>';
    return html;
  }

  function renderMsgs() {
    msgsEl.innerHTML = '';
    msgs.forEach(function(m) {
      var row = document.createElement('div');
      row.className = 'pt-row ' + (m.role === 'user' ? 'user' : 'ai');
      if (m.role === 'ai') {
        row.innerHTML = '<div class="pt-ai-av">P</div><div class="pt-bbl ai" id="bb' + m.id + '">' + fmtBubble(m) + '</div>';
      } else {
        row.innerHTML = '<div class="pt-bbl user">' + esc(m.content) + '</div>';
      }
      msgsEl.appendChild(row);
    });
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  window.__ptSend = function(text) {
    var txt = text || inEl.value.trim();
    if (!txt || loading) return;
    inEl.value = ''; sbEl.disabled = true; loading = true;
    msgs.push({ role: 'user', content: txt });
    var aid = Date.now();
    msgs.push({ role: 'ai', content: '', streaming: true, id: aid });
    renderMsgs();
    var apiMsgs = msgs.slice(0, -1).filter(function(m){ return m.content; }).map(function(m){
      return { role: m.role === 'ai' ? 'assistant' : 'user', content: m.content };
    });
    fetch('/.netlify/functions/advisor', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: apiMsgs }),
    })
    .then(function(r){ return r.json(); })
    .then(function(d){
      var last = msgs[msgs.length - 1];
      last.content = d.content || 'Sorry, something went wrong.';
      last.streaming = false;
      var el = document.getElementById('bb' + aid);
      if (el) el.innerHTML = fmtBubble(last);
      msgsEl.scrollTop = msgsEl.scrollHeight;
    })
    .catch(function(){
      var last = msgs[msgs.length - 1];
      last.content = 'Something went wrong. Please try again.';
      last.streaming = false;
      var el = document.getElementById('bb' + aid);
      if (el) el.innerHTML = fmtBubble(last);
    })
    .finally(function(){ loading = false; sbEl.disabled = false; inEl.focus(); });
  };

  inEl.addEventListener('input', function(){ sbEl.disabled = !inEl.value.trim(); });
  inEl.addEventListener('keydown', function(e){ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();window.__ptSend();} });
  sbEl.addEventListener('click', function(){ window.__ptSend(); });

  fab.addEventListener('click', function(){
    open = !open;
    fab.classList.toggle('open', open);
    panel.classList.toggle('open', open);
    fab.setAttribute('aria-label', open ? 'Close Peptide Advisor' : 'Open Peptide Advisor');
    if (open) setTimeout(function(){ inEl.focus(); }, 230);
  });

  document.addEventListener('click', function(e){
    if (open && !panel.contains(e.target) && e.target !== fab && !fab.contains(e.target)) {
      open = false; fab.classList.remove('open'); panel.classList.remove('open');
    }
  });
})();
