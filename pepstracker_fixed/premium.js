/* ═══════════════════════════════════════════════════════════
   PepsTracker Premium JS — Price bars + hero enhancements
   ═══════════════════════════════════════════════════════════ */
(function() {
  'use strict';

  // ── Inject price bars into result cards ──────────────────
  function injectPriceBars() {
    var cards = document.querySelectorAll('#resultList .result-card');
    if (!cards.length) return;

    // Collect all prices (data-permg attribute set below)
    var prices = [];
    cards.forEach(function(card) {
      var permgEl = card.querySelector('.price-per-mg');
      if (permgEl) {
        var val = parseFloat(permgEl.textContent.replace(/[^0-9.]/g,''));
        if (!isNaN(val)) prices.push(val);
      }
    });
    if (!prices.length) return;

    var min = Math.min.apply(null, prices);
    var max = Math.max.apply(null, prices);
    var range = max - min || 1;

    cards.forEach(function(card) {
      if (card.querySelector('.pt-price-bar-wrap')) return; // already added

      var permgEl = card.querySelector('.price-per-mg');
      if (!permgEl) return;
      var val = parseFloat(permgEl.textContent.replace(/[^0-9.]/g,''));
      if (isNaN(val)) return;

      // Invert: lower price = fuller bar (best deal = 100%)
      var pct = 100 - ((val - min) / range * 80);

      var wrap = document.createElement('div');
      wrap.className = 'pt-price-bar-wrap';
      var fill = document.createElement('div');
      fill.className = 'pt-price-bar-fill';
      fill.style.width = '0%';
      wrap.appendChild(fill);
      card.appendChild(wrap);

      // Animate in after a short delay
      var delay = Array.from(cards).indexOf(card) * 60 + 300;
      setTimeout(function() {
        fill.style.width = pct.toFixed(1) + '%';
      }, delay);
    });
  }

  // ── Watch for new results ─────────────────────────────────
  var resultList = document.getElementById('resultList');
  if (resultList) {
    var barObserver = new MutationObserver(function(mutations) {
      mutations.forEach(function(m) {
        if (m.addedNodes.length) {
          setTimeout(injectPriceBars, 80);
        }
      });
    });
    barObserver.observe(resultList, { childList: true });
  }

  // ── Upgrade hero with live chips ─────────────────────────
  var hero = document.querySelector('.hero');
  if (hero) {
    // Add eyebrow if not present
    if (!hero.querySelector('.hero-eyebrow')) {
      var eyebrow = document.createElement('div');
      eyebrow.className = 'hero-eyebrow';
      eyebrow.innerHTML = '<span class="live-dot"></span> Live prices &middot; Updated daily';
      hero.insertBefore(eyebrow, hero.firstElementChild);
    }

    // Add proof chips if not present
    if (!hero.querySelector('.hero-proof')) {
      var proof = document.createElement('div');
      proof.className = 'hero-proof';
      proof.innerHTML =
        '<span class="proof-chip">Semaglutide from $2.90/mg</span>' +
        '<span class="proof-chip">Tirzepatide from $1.50/mg</span>' +
        '<span class="proof-chip">BPC-157 from $2.90/mg</span>';
      var heroP = hero.querySelector('p');
      if (heroP) heroP.insertAdjacentElement('afterend', proof);
    }
  }

  // ── Upgrade stats to gradient text ───────────────────────
  // (handled by CSS, but ensure DOM is ready)
  document.querySelectorAll('.stat-num').forEach(function(el) {
    el.style.webkitTextFillColor = '';
    el.style.backgroundClip = '';
  });

  // ── Add premium body class ────────────────────────────────
  document.body.classList.add('pt-premium');

})();
