/* ═══════════════════════════════════════════════════════════
   PepsTracker Polish Layer — JS interactions
   ═══════════════════════════════════════════════════════════ */
(function() {
  'use strict';

  // ── Scroll progress bar ──────────────────────────────────
  var prog = document.createElement('div');
  prog.id = 'pt-progress';
  document.body.prepend(prog);
  window.addEventListener('scroll', function() {
    var h = document.documentElement;
    var pct = (h.scrollTop / (h.scrollHeight - h.clientHeight)) * 100;
    prog.style.width = Math.min(pct, 100) + '%';
  }, { passive: true });

  // ── Toast system ─────────────────────────────────────────
  window.ptToast = function(msg, color) {
    var old = document.querySelector('.pt-toast');
    if (old) { old.remove(); }
    var t = document.createElement('div');
    t.className = 'pt-toast';
    t.textContent = msg;
    if (color) t.style.color = color;
    document.body.appendChild(t);
    requestAnimationFrame(function() {
      requestAnimationFrame(function() { t.classList.add('pt-show'); });
    });
    setTimeout(function() {
      t.classList.remove('pt-show');
      setTimeout(function() { if (t.parentNode) t.remove(); }, 280);
    }, 2400);
  };

  // ── Intercept clipboard to show toast ────────────────────
  if (navigator.clipboard && navigator.clipboard.writeText) {
    var origWrite = navigator.clipboard.writeText.bind(navigator.clipboard);
    navigator.clipboard.writeText = function(text) {
      return origWrite(text).then(function() {
        ptToast('✓ Copied!');
      }).catch(function(err) { return Promise.reject(err); });
    };
  }

  // ── Stagger result card animations ───────────────────────
  var resultsEl = document.getElementById('resultList') || document.getElementById('results');
  if (resultsEl) {
    var cardObserver = new MutationObserver(function(mutations) {
      mutations.forEach(function(m) {
        if (m.type === 'childList' && m.addedNodes.length) {
          var cards = resultsEl.querySelectorAll('.result-card');
          cards.forEach(function(card, i) {
            card.classList.remove('animate-in');
            void card.offsetWidth; // force reflow
            card.style.animationDelay = (i * 38) + 'ms';
            card.classList.add('animate-in');
          });
        }
      });
    });
    cardObserver.observe(resultsEl, { childList: true, subtree: false });
  }

  // ── Scroll fade-in observer ───────────────────────────────
  if ('IntersectionObserver' in window) {
    var fadeObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) {
          e.target.classList.add('pt-visible');
          fadeObserver.unobserve(e.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    // Add fade class to key sections
    var fadeTargets = document.querySelectorAll(
      '.stats-row, .stat-item, .glp-banner, .quick-pills, ' +
      '.also-compare, [class*="section"], [class*="card"]:not(.result-card)'
    );
    fadeTargets.forEach(function(el, i) {
      // Don't re-animate elements already in view on load
      var rect = el.getBoundingClientRect();
      if (rect.top > window.innerHeight) {
        el.classList.add('pt-fade');
        if (el.classList.contains('stat-item')) {
          el.style.transitionDelay = (i % 5 * 70) + 'ms';
        }
        fadeObserver.observe(el);
      }
    });
  }

  // ── Keyboard nav: press Enter on pill buttons ────────────
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.target.classList.contains('pill')) {
      e.target.click();
    }
  });

  // ── Number count-up for stats ─────────────────────────────
  function countUp(el) {
    var text = el.textContent;
    var numMatch = text.match(/[\d,]+/);
    if (!numMatch) return;
    var target = parseInt(numMatch[0].replace(/,/g,''));
    if (target < 10 || isNaN(target)) return;
    var start = 0;
    var duration = 900;
    var startTime = null;
    var suffix = text.replace(numMatch[0], '').trim();
    var prefix = text.slice(0, text.indexOf(numMatch[0]));

    function step(ts) {
      if (!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / duration, 1);
      var ease = 1 - Math.pow(1 - progress, 3);
      var current = Math.floor(ease * target);
      el.textContent = prefix + current.toLocaleString() + suffix;
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = text; // restore original exactly
    }
    requestAnimationFrame(step);
  }

  if ('IntersectionObserver' in window) {
    var statObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) {
          countUp(e.target);
          statObserver.unobserve(e.target);
        }
      });
    }, { threshold: 0.5 });
    document.querySelectorAll('.stat-num').forEach(function(el) {
      statObserver.observe(el);
    });
  }

  // ── Active pill state on quick-pills ─────────────────────
  document.querySelectorAll('.quick-pill, .pill').forEach(function(pill) {
    pill.addEventListener('click', function() {
      var parent = this.closest('.quick-pills, .pill-row, .also-pills');
      if (parent) {
        parent.querySelectorAll('.quick-pill, .pill').forEach(function(p) {
          p.style.background = '';
          p.style.color = '';
          p.style.borderColor = '';
        });
      }
    });
  });

  // ── Smooth results reveal ─────────────────────────────────
  var origScrollIntoView = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function(options) {
    origScrollIntoView.call(this, options);
    // Flash the results header softly
    var header = document.querySelector('.results-header, .results-title');
    if (header && (this.id === 'results' || this.classList.contains('result-card'))) {
      header.style.transition = 'opacity 0.15s ease';
      header.style.opacity = '0.6';
      setTimeout(function() { header.style.opacity = '1'; }, 150);
    }
  };

})();
