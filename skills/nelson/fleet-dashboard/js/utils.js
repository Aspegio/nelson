/* ============================================================
   NELSON FLEET DASHBOARD — Shared Utilities
   Constants and formatting helpers used across modules.

   Public API (via window.DashboardUtils):
     DashboardUtils.pad(n)
     DashboardUtils.formatTime(iso)
     DashboardUtils.formatTokens(n)
     DashboardUtils.currentTimeString()
     DashboardUtils.MILLION
     DashboardUtils.THOUSAND
     DashboardUtils.CLOCK_INTERVAL_MS
   ============================================================ */

(function (global) {
  'use strict';

  /* -- Constants ---------------------------------------------- */

  var MILLION  = 1000000;
  var THOUSAND = 1000;
  var CLOCK_INTERVAL_MS = 1000;

  /* -- Helpers ------------------------------------------------ */

  /**
   * Zero-pad a number to at least two digits.
   *
   * @param {number} n
   * @returns {string}
   */
  function pad(n) {
    return String(n).padStart(2, '0');
  }

  /**
   * Format an ISO date string to HH:MM:SS local time.
   * Returns '—' if the input is falsy or unparseable.
   *
   * @param {string} iso
   * @returns {string}
   */
  function formatTime(iso) {
    if (!iso) { return '—'; }
    var d = new Date(iso);
    if (isNaN(d.getTime())) { return '—'; }
    return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  /**
   * Format a token count to a short string like "80K" or "1.2M".
   * Falls back to the raw value as a string for non-numeric input.
   *
   * @param {*} n
   * @returns {string}
   */
  function formatTokens(n) {
    var num = Number(n);
    if (isNaN(num)) { return String(n); }
    if (num >= MILLION)  { return (num / MILLION).toFixed(1).replace(/\.0$/, '') + 'M'; }
    if (num >= THOUSAND) { return Math.round(num / THOUSAND) + 'K'; }
    return String(num);
  }

  /**
   * Format the current local time as HH:MM:SS.
   *
   * @returns {string}
   */
  function currentTimeString() {
    var now = new Date();
    return pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
  }

  /* -- Expose on global --------------------------------------- */

  global.DashboardUtils = Object.freeze({
    pad:               pad,
    formatTime:        formatTime,
    formatTokens:      formatTokens,
    currentTimeString: currentTimeString,
    MILLION:           MILLION,
    THOUSAND:          THOUSAND,
    CLOCK_INTERVAL_MS: CLOCK_INTERVAL_MS
  });

}(typeof window !== 'undefined' ? window : this));
