/* ═══════════════════════════════════════════════════════════
   PepsTracker MyStack — Stack engine
   Shared between index.html and mystack.html
   ═══════════════════════════════════════════════════════════ */
(function() {
  'use strict';

  const STORAGE_KEY = 'pt_mystack_v1';

  // ── Goal presets ──────────────────────────────────────────
  window.STACK_GOALS = {
    'GLP-1 / Weight Loss':   ['Semaglutide','Tirzepatide','Lipo-C','5-Amino-1MQ'],
    'Healing & Recovery':    ['BPC-157','TB-500','BPC-157 + TB-500 Blend','GHK-Cu'],
    'Longevity':             ['Epithalon','NAD+','SS-31','MOTS-c','GHK-Cu'],
    'Cognitive':             ['Semax','Selank','PE-22-28','Dihexa'],
    'Performance':           ['Ipamorelin','CJC/Ipa Blend','Tesamorelin','IGF-1 LR3'],
  };

  // ── Load / save ───────────────────────────────────────────
  window.loadStack = function() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || { items: [] }; }
    catch(e) { return { items: [] }; }
  };
  window.saveStack = function(stack) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stack));
    window.dispatchEvent(new Event('stackUpdated'));
  };

  // ── Add to stack ──────────────────────────────────────────
  window.addToStack = function(vendorId, peptide, vendorName, vendorUrl, code, discount, price, mg, listing) {
    const stack = loadStack();
    const existing = stack.items.findIndex(i => i.peptide === peptide);
    const item = { peptide, vendorId, vendorName, vendorUrl, code, discount,
                   price: parseFloat(price), mg: parseFloat(mg), listing,
                   addedAt: Date.now() };

    if (existing >= 0) {
      stack.items[existing] = item; // update with new best price
      if (window.ptToast) ptToast('✓ ' + peptide + ' updated in stack');
    } else {
      stack.items.push(item);
      if (window.ptToast) ptToast('✓ ' + peptide + ' added to MyStack');
    }
    saveStack(stack);
    updateStackBadge();
  };

  // ── Remove from stack ─────────────────────────────────────
  window.removeFromStack = function(peptide) {
    const stack = loadStack();
    stack.items = stack.items.filter(i => i.peptide !== peptide);
    saveStack(stack);
    updateStackBadge();
  };

  // ── Update nav badge ──────────────────────────────────────
  window.updateStackBadge = function() {
    const stack = loadStack();
    const count = stack.items.length;
    document.querySelectorAll('.stack-badge').forEach(el => {
      el.textContent = count;
      el.style.display = count > 0 ? 'inline-flex' : 'none';
    });
    // Update add-to-stack buttons active state
    document.querySelectorAll('.btn-add-stack').forEach(btn => {
      const pep = btn.dataset.peptide;
      const inStack = stack.items.some(i => i.peptide === pep);
      btn.classList.toggle('in-stack', inStack);
      btn.textContent = inStack ? '✓ In Stack' : '+ Stack';
    });
  };

  // ── Total monthly cost ────────────────────────────────────
  window.calcStackTotal = function() {
    const stack = loadStack();
    return stack.items.reduce((sum, i) => sum + (i.price || 0), 0);
  };

  // Init badge on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateStackBadge);
  } else {
    setTimeout(updateStackBadge, 100);
  }
})();
