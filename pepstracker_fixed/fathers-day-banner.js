(function(){
  // Glow Aminos Father's Day Bonus banner — expires June 21, 2026 11:59:59 PM ET automatically
  var deadline = new Date("2026-06-22T03:59:59Z"); // 11:59:59 PM ET (EDT, UTC-4)
  if (new Date() > deadline) return;
  if (sessionStorage.getItem('gpFathersDayDismissed') === '1') return;

  var bar = document.createElement('div');
  bar.id = 'gp-fathersday-banner';
  bar.style.cssText = 'position:relative;width:100%;background:linear-gradient(90deg,#0d0f14,#1a1206);' +
    'border-bottom:2px solid #f5c842;padding:10px 16px;font-family:"Plus Jakarta Sans",sans-serif;' +
    'display:flex;align-items:center;justify-content:center;gap:14px;flex-wrap:wrap;z-index:9999;font-size:14px;color:#e8edf5;';

  bar.innerHTML =
    '<span style="font-weight:700;">🎁 Glow Aminos Father\'s Day Bonus — ' +
    '<span style="color:#4de87a;">40% Off Sitewide</span> (auto-applied) + extra ' +
    '<span style="color:#f5c842;">15% off</span> with code ' +
    '<span style="font-family:Fira Code,monospace;background:#1c2230;padding:2px 8px;border-radius:4px;color:#f5c842;">GLOWLAB</span> ' +
    '= <span style="color:#f5c842;font-weight:800;">55% OFF TOTAL</span> · ends tonight 11:59 PM ET</span>' +
    '<button id="gp-fd-copy" style="background:#f5c842;color:#0d0f14;border:none;padding:6px 14px;border-radius:6px;font-weight:700;cursor:pointer;font-size:13px;">Copy Code</button>' +
    '<a href="https://glowaminos.com/shop/?coupon=Glowlab" target="_blank" rel="noopener" style="background:#3b9eff;color:#fff;padding:6px 16px;border-radius:6px;font-weight:700;text-decoration:none;font-size:13px;">Shop Now →</a>' +
    '<button id="gp-fd-close" aria-label="Dismiss" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;color:#7a8ba8;font-size:18px;cursor:pointer;line-height:1;">×</button>';

  document.body.insertBefore(bar, document.body.firstChild);

  document.getElementById('gp-fd-copy').addEventListener('click', function(){
    var btn = this;
    navigator.clipboard.writeText('GLOWLAB').then(function(){
      btn.textContent = 'Copied!';
      setTimeout(function(){ btn.textContent = 'Copy Code'; }, 1800);
    });
  });
  document.getElementById('gp-fd-close').addEventListener('click', function(){
    bar.remove();
    sessionStorage.setItem('gpFathersDayDismissed', '1');
  });
})();
