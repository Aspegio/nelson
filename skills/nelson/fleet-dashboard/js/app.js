/* ============================================================
   NELSON FLEET DASHBOARD — App Controller
   Orchestrates DataLoader and Renderer; handles keyboard shortcuts.

   Keyboard shortcuts:
     r       — force immediate refresh
     p       — toggle polling pause
     Escape  — dismiss overlay and blocker banner
   ============================================================ */

(function () {
  'use strict';

  /* -- Clock ------------------------------------------------- */

  function updateClock() {
    var clockEl = document.getElementById('clock');
    if (clockEl) {
      clockEl.textContent = DashboardUtils.currentTimeString();
    }
  }

  /* -- Dismiss state (BUG-2) --------------------------------- */

  var dismissState = {
    blockerText:      null,
    overlayDismissed: false
  };

  /* -- State change handler ---------------------------------- */

  function onStateChange(state) {
    Renderer.render(state, dismissState);
  }

  /* -- Keyboard shortcuts (QUAL-4: extracted) ----------------- */

  function setupKeyboardShortcuts(loader, params, pollIntervalEl) {
    var paused = false;

    document.addEventListener('keydown', function (event) {
      /* A11Y-5: Ignore modified keystrokes */
      if (event.ctrlKey || event.altKey || event.metaKey) { return; }

      var tag = event.target && event.target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') { return; }

      switch (event.key) {
        case 'r':
          loader.forceRefresh();
          break;

        case 'p':
          if (paused) {
            paused = false;
            loader.start(onStateChange);
            if (pollIntervalEl) {
              pollIntervalEl.textContent = (params.pollMs / 1000).toFixed(1) + 's';
            }
          } else {
            paused = true;
            loader.stop();
            if (pollIntervalEl) {
              pollIntervalEl.textContent = 'paused';
            }
          }
          break;

        case 'Escape':
          var overlay = document.getElementById('mission-summary-overlay');
          if (overlay && !overlay.classList.contains('hidden')) {
            overlay.classList.add('hidden');
            dismissState.overlayDismissed = true;
          }
          var banner = document.getElementById('blocker-banner');
          if (banner && !banner.classList.contains('hidden')) {
            var msgEl = document.getElementById('blocker-message');
            dismissState.blockerText = msgEl ? msgEl.textContent : '';
            banner.classList.add('hidden');
          }
          break;
      }
    });
  }

  /* -- Dismiss button handler (QUAL-4: extracted) ------------- */

  function setupDismissHandlers() {
    var blockerDismiss = document.getElementById('blocker-dismiss');
    if (blockerDismiss) {
      blockerDismiss.addEventListener('click', function () {
        var banner = document.getElementById('blocker-banner');
        if (banner) {
          var msgEl = document.getElementById('blocker-message');
          dismissState.blockerText = msgEl ? msgEl.textContent : '';
          banner.classList.add('hidden');
        }
      });
    }
  }

  /* -- Initialise -------------------------------------------- */

  function init() {
    var loader = new DataLoader();

    updateClock();
    setInterval(updateClock, DashboardUtils.CLOCK_INTERVAL_MS);

    var params = DataLoader.getParams();
    var pollIntervalEl = document.getElementById('poll-interval');
    if (pollIntervalEl) {
      pollIntervalEl.textContent = (params.pollMs / 1000).toFixed(1) + 's';
    }

    loader.start(onStateChange);

    setupKeyboardShortcuts(loader, params, pollIntervalEl);
    setupDismissHandlers();
  }

  /* -- Boot -------------------------------------------------- */

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
