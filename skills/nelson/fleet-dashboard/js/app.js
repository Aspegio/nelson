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

  /**
   * Format the current local time as HH:MM:SS.
   *
   * @returns {string}
   */
  function currentTimeString() {
    var now = new Date();
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
  }

  /**
   * Update the #clock element with the current time.
   * Called every second via setInterval.
   */
  function updateClock() {
    var clockEl = document.getElementById('clock');
    if (clockEl) {
      clockEl.textContent = currentTimeString();
    }
  }

  /* -- State change handler ---------------------------------- */

  /**
   * Delegate state changes to the Renderer.
   *
   * @param {Readonly<object>} state
   */
  function onStateChange(state) {
    Renderer.render(state);
  }

  /* -- Initialise -------------------------------------------- */

  /**
   * Bootstraps the dashboard: starts the clock, the data loader,
   * and populates the footer poll-interval label.
   */
  function init() {
    var loader  = new DataLoader();
    var paused  = false;

    /* Start clock */
    updateClock();
    setInterval(updateClock, 1000);

    /* Populate poll interval in footer */
    var params = DataLoader.getParams();
    var pollIntervalEl = document.getElementById('poll-interval');
    if (pollIntervalEl) {
      pollIntervalEl.textContent = (params.pollMs / 1000).toFixed(1) + 's';
    }

    /* Start polling */
    loader.start(onStateChange);

    /* -- Keyboard shortcuts ---------------------------------- */

    document.addEventListener('keydown', function (event) {
      /* Ignore events originating from text inputs */
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
          if (overlay) { overlay.classList.add('hidden'); }
          var banner  = document.getElementById('blocker-banner');
          if (banner)  { banner.classList.add('hidden'); }
          break;
      }
    });

    /* -- Blocker banner dismiss button ----------------------- */

    var blockerDismiss = document.getElementById('blocker-dismiss');
    if (blockerDismiss) {
      blockerDismiss.addEventListener('click', function () {
        var banner = document.getElementById('blocker-banner');
        if (banner) { banner.classList.add('hidden'); }
      });
    }
  }

  /* -- Boot -------------------------------------------------- */

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
