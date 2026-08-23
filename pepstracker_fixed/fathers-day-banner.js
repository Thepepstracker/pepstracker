// Glow Lab Protocols sponsored banner - Pep of the Week image edition.
// Replaces the old text strip (31% off / GLOW31 copy bar). Same dismiss key,
// same tracked link. Image lives in-repo; alt text carries the offer for SEO/a11y.
(function(){
  if(sessionStorage.getItem('gpGlowLabDismissed')==='1')return;
  var b=document.createElement('div');
  b.id='gp-glowlab-banner';
  b.style.cssText='position:relative;z-index:9999;background:#0b0f14;padding:10px 14px;text-align:center;';
  var a=document.createElement('a');
  a.href='https://glowlabprotocols.com/shop/';
  a.target='_blank';a.rel='sponsored noopener';
  a.style.cssText='display:inline-block;max-width:1200px;width:100%;';
  var img=document.createElement('img');
  img.src='/glp-pep-of-the-week.webp';
  img.alt='Pep of the Week: GHK-Cu 100mg for $25 at Glow Lab Protocols - home of the $25 NAD+ 500mg';
  img.style.cssText='width:100%;height:auto;display:block;border-radius:10px;';
  img.loading='eager';img.decoding='async';
  a.appendChild(img);b.appendChild(a);
  var x=document.createElement('button');
  x.id='gp-gl-close';x.setAttribute('aria-label','Dismiss banner');
  x.textContent='\u00d7';
  x.style.cssText='position:absolute;top:14px;right:18px;background:rgba(0,0,0,.45);color:#fff;border:none;border-radius:50%;width:26px;height:26px;line-height:1;font-size:16px;cursor:pointer;';
  x.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();sessionStorage.setItem('gpGlowLabDismissed','1');b.remove();});
  b.appendChild(x);
  document.body.insertBefore(b,document.body.firstChild);
})();
