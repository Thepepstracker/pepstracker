/* PepsTracker newsletter signup popup - shows once, 30-day re-ask on dismiss. */
(function () {
  var LS_SUB = "ptNewsSub", LS_DIS = "ptNewsDismiss";
  var ENDPOINT = "https://formsubmit.co/ajax/jonahszedertuba@gmail.com";
  try {
    if (localStorage.getItem(LS_SUB)) return;
    var d = parseInt(localStorage.getItem(LS_DIS) || "0", 10);
    if (d && Date.now() - d < 30 * 864e5) return;
  } catch (e) { return; }

  var css = document.createElement("style");
  css.textContent =
    "#pt-news-overlay{position:fixed;inset:0;background:rgba(6,8,12,.7);backdrop-filter:blur(2px);z-index:9998;opacity:0;transition:opacity .3s}" +
    "#pt-news-overlay.on{opacity:1}" +
    "#pt-news{position:fixed;left:50%;top:50%;transform:translate(-50%,-46%);width:min(420px,92vw);background:var(--card,#1c2230);border:1px solid var(--border,#2a3347);border-radius:var(--radius,12px);padding:28px 26px 22px;z-index:9999;color:var(--text,#e8edf5);font-family:'Plus Jakarta Sans','Segoe UI',system-ui,sans-serif;box-shadow:0 24px 64px rgba(0,0,0,.55);opacity:0;transition:opacity .3s,transform .3s}" +
    "#pt-news.on{opacity:1;transform:translate(-50%,-50%)}" +
    "#pt-news h3{margin:0 0 6px;font-size:1.25rem}" +
    "#pt-news p{margin:0 0 16px;color:var(--muted,#7a8ba8);font-size:.9rem;line-height:1.55}" +
    "#pt-news .row{display:flex;gap:8px}" +
    "#pt-news input[type=email]{flex:1;background:var(--surface,#161b25);border:1px solid var(--border,#2a3347);border-radius:8px;padding:10px 12px;color:inherit;font:inherit;font-size:.9rem}" +
    "#pt-news input[type=email]:focus{outline:none;border-color:var(--green,#4de87a)}" +
    "#pt-news button.go{background:var(--green,#4de87a);color:#0d0f14;border:0;border-radius:8px;padding:10px 16px;font-weight:700;font-family:inherit;cursor:pointer;font-size:.9rem}" +
    "#pt-news button.go:disabled{opacity:.6;cursor:default}" +
    "#pt-news .no{display:block;margin:12px auto 0;background:none;border:0;color:var(--muted,#7a8ba8);font-family:inherit;font-size:.8rem;cursor:pointer;text-decoration:underline}" +
    "#pt-news .x{position:absolute;top:10px;right:14px;background:none;border:0;color:var(--muted,#7a8ba8);font-size:1.2rem;cursor:pointer}" +
    "#pt-news .ok{color:var(--green,#4de87a);font-weight:600;margin:0}";
  document.head.appendChild(css);

  function show() {
    var ov = document.createElement("div"); ov.id = "pt-news-overlay";
    var box = document.createElement("div"); box.id = "pt-news";
    box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true"); box.setAttribute("aria-label", "Newsletter signup");
    box.innerHTML =
      '<button class="x" aria-label="Close">&times;</button>' +
      "<h3>Never overpay for peptides</h3>" +
      "<p>Get the week's biggest price drops and verified sale codes from 26+ vendors. No spam, unsubscribe anytime.</p>" +
      '<form class="row"><input type="email" required placeholder="you@email.com" aria-label="Email address"><button class="go" type="submit">Get the deals</button></form>' +
      '<button class="no">No thanks</button>';
    document.body.appendChild(ov); document.body.appendChild(box);
    requestAnimationFrame(function () { ov.className = "on"; box.className = "on"; });

    function close(remember) {
      try { if (remember) localStorage.setItem(LS_DIS, String(Date.now())); } catch (e) {}
      ov.remove(); box.remove(); document.removeEventListener("keydown", onKey);
    }
    function onKey(e) { if (e.key === "Escape") close(true); }
    document.addEventListener("keydown", onKey);
    ov.addEventListener("click", function () { close(true); });
    box.querySelector(".x").addEventListener("click", function () { close(true); });
    box.querySelector(".no").addEventListener("click", function () { close(true); });

    box.querySelector("form").addEventListener("submit", function (e) {
      e.preventDefault();
      var input = box.querySelector("input[type=email]");
      var btn = box.querySelector("button.go");
      btn.disabled = true; btn.textContent = "...";
      fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ email: input.value, _subject: "PepsTracker newsletter signup", _template: "table" })
      }).then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function () {
          try { localStorage.setItem(LS_SUB, "1"); } catch (e) {}
          box.querySelector("form").outerHTML = '<p class="ok">You\u2019re in \u2014 deals coming your way.</p>';
          box.querySelector(".no").remove();
          setTimeout(function () { close(false); }, 2600);
        })
        .catch(function () {
          btn.disabled = false; btn.textContent = "Get the deals";
          input.setCustomValidity("Something went wrong \u2014 please try again.");
          input.reportValidity(); input.setCustomValidity("");
        });
    });
    setTimeout(function () { box.querySelector("input[type=email]").focus(); }, 350);
  }

  if (document.readyState === "complete") setTimeout(show, 7000);
  else window.addEventListener("load", function () { setTimeout(show, 7000); });
})();
