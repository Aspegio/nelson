/* ============================================================
   NELSON FLEET DASHBOARD — Data Loader
   Polls mission JSON files and emits immutable state updates.

   Public API (via window.DataLoader):
     new DataLoader()
     .start(callback)  — begin polling, invoke callback on change
     .stop()           — halt polling
     .forceRefresh()   — immediate out-of-band poll

   Static helpers:
     DataLoader.hullClass(status)
     DataLoader.taskStatusFromSquadron(squadron, taskId)
     DataLoader.getParams()
   ============================================================ */

(function (global) {
  'use strict';

  /* -- Constants -------------------------------------------- */

  var MIN_POLL_MS      = 1000;
  var DEFAULT_POLL_MS  = 3000;
  var BACKOFF_POLL_MS  = 10000;
  var MAX_FAILURES     = 3;

  /** SEC-1: Hull status allowlist — only these values become CSS classes. */
  var HULL_CLASSES = { green: 'green', amber: 'amber', red: 'red', critical: 'critical' };

  /* -- Path validation (SEC-3) -------------------------------- */

  /**
   * Validate a mission path is safe — reject traversal and absolute paths.
   *
   * @param {string|null} raw
   * @returns {string|null}  The raw value if safe, or null if rejected.
   */
  function validateMissionPath(raw) {
    if (!raw) { return null; }
    if (/\.\./.test(raw))    { return null; }
    if (/\/\//.test(raw))    { return null; }
    if (/^\//.test(raw))     { return null; }
    if (/^[a-z]+:/i.test(raw)) { return null; }
    return raw;
  }

  /* -- URL parameter helpers --------------------------------- */

  /**
   * Read `mission` and `poll` from the current URL search params.
   * `poll` is clamped to a minimum of MIN_POLL_MS.
   *
   * @returns {{ mission: string|null, pollMs: number }}
   */
  function getParams() {
    var params  = new URLSearchParams(global.location.search);
    var mission = validateMissionPath(params.get('mission') || null);
    var rawPoll = parseInt(params.get('poll'), 10);
    var pollMs  = isNaN(rawPoll) ? DEFAULT_POLL_MS : Math.max(rawPoll, MIN_POLL_MS);
    return Object.freeze({ mission: mission, pollMs: pollMs });
  }

  /* -- State factory ----------------------------------------- */

  /**
   * Return a frozen "empty" state object with no loaded data.
   *
   * @param {string|null} mission  Base path for the mission directory.
   * @returns {Readonly<object>}
   */
  function createEmptyState(mission) {
    return Object.freeze({
      mission:            mission,
      fleetStatus:        null,
      sailingOrders:      null,
      battlePlan:         null,
      missionLog:         null,
      standDown:          null,
      connectionState:    'connecting',
      consecutiveFailures: 0
    });
  }

  /* -- Fetch helper (PERF-1: raw text comparison) ------------- */

  /**
   * Fetch a JSON file relative to `basePath`.
   * Returns { text, data } on success, or null on any error
   * (network failure, non-2xx response, parse error).
   *
   * @param {string}      basePath  Base directory path (no trailing slash).
   * @param {string}      filename  Filename to fetch.
   * @returns {Promise<{ text: string, data: object }|null>}
   */
  function fetchJSON(basePath, filename) {
    var url = basePath + '/' + filename;
    return fetch(url)
      .then(function (response) {
        if (!response.ok) { return null; }
        return response.text();
      })
      .then(function (text) {
        if (text == null) { return null; }
        try {
          return { text: text, data: JSON.parse(text) };
        } catch (e) {
          return null;
        }
      })
      .catch(function () {
        return null;
      });
  }

  /* -- Schema validation (QUAL-9) ----------------------------- */

  /**
   * Validate that a fleet-status object has the required shape.
   *
   * @param {*} data
   * @returns {boolean}
   */
  function validateFleetStatus(data) {
    if (!data || typeof data !== 'object')          { return false; }
    if (!data.mission || typeof data.mission !== 'object') { return false; }
    if (typeof data.mission.status !== 'string')    { return false; }
    if (!Array.isArray(data.squadron))               { return false; }
    return true;
  }

  /* -- Static utility helpers -------------------------------- */

  /**
   * Map a hull_integrity_status string to its lowercase CSS class name.
   * SEC-1: Only allowlisted values are returned; everything else maps to 'unknown'.
   *
   * @param {string} status  'Green' | 'Amber' | 'Red' | 'Critical'
   * @returns {string}
   */
  function hullClass(status) {
    if (typeof status !== 'string') { return 'unknown'; }
    var key = status.toLowerCase();
    return HULL_CLASSES[key] || 'unknown';
  }

  /**
   * Find the ship in `squadron` whose task_id matches `taskId`
   * and return its task_status.  Falls back to 'pending' when no
   * match is found or when the matched ship has no task_status.
   *
   * @param {Array<object>} squadron
   * @param {number}        taskId
   * @returns {string}
   */
  function taskStatusFromSquadron(squadron, taskId) {
    if (!Array.isArray(squadron)) { return 'pending'; }
    for (var i = 0; i < squadron.length; i++) {
      var ship = squadron[i];
      if (ship.task_id === taskId) {
        return ship.task_status || 'pending';
      }
    }
    return 'pending';
  }

  /* -- DataLoader class -------------------------------------- */

  /**
   * Coordinates periodic fetching of mission JSON files and
   * emits immutable state snapshots to a registered callback
   * whenever the data changes.
   *
   * All internal state is replaced (never mutated) on each cycle.
   */
  function DataLoader() {
    var urlParams       = getParams();
    this._mission       = urlParams.mission;
    this._pollMs        = urlParams.pollMs;
    this._state         = createEmptyState(urlParams.mission);
    this._timer         = null;
    this._callback      = null;
    this._inflight      = false;
    this._lastResponseText = null;
  }

  /* -- PERF-2: setTimeout chain instead of setInterval -------- */

  /**
   * Schedule the next poll after `delayMs` using setTimeout.
   * Replaces setInterval to ensure polls don't overlap.
   *
   * @param {number} delayMs
   */
  DataLoader.prototype._scheduleNext = function (delayMs) {
    var self = this;
    this._timer = setTimeout(function () {
      self._poll().catch(function () {}).then(function () {
        if (self._timer !== null) {
          self._scheduleNext(self._pollMs);
        }
      });
    }, delayMs);
  };

  /**
   * Start polling.  Runs an immediate first poll then schedules
   * subsequent polls via setTimeout chain.
   * BUG-1: Calls stop() first to prevent timer leak on pause/unpause.
   *
   * @param {function(Readonly<object>): void} callback
   */
  DataLoader.prototype.start = function (callback) {
    this.stop();
    this._callback = callback;
    var self = this;
    this._poll().catch(function () {}).then(function () {
      self._scheduleNext(self._pollMs);
    });
  };

  /**
   * Stop polling and clear the scheduled timeout.
   */
  DataLoader.prototype.stop = function () {
    if (this._timer !== null) {
      clearTimeout(this._timer);
      this._timer = null;
    }
  };

  /**
   * Trigger an immediate out-of-band poll without waiting for the
   * next scheduled tick. Guarded against concurrent inflight polls.
   */
  DataLoader.prototype.forceRefresh = function () {
    if (this._inflight) { return; }
    this._poll().catch(function () {});
  };

  /* -- QUAL-4: Extracted poll success / failure handlers ------- */

  /**
   * Handle a successful fleet-status fetch.
   * Detects state transitions and fetches supplementary documents.
   *
   * @param {{ text: string, data: object }} result
   * @returns {Promise<void>}
   */
  DataLoader.prototype._handlePollSuccess = function (result) {
    var self     = this;
    var basePath = this._mission ? ('/' + this._mission) : '.';
    var fleetStatus = result.data;

    /* PERF-1: Skip processing if raw text is unchanged */
    if (result.text === self._lastResponseText) { return Promise.resolve(); }
    self._lastResponseText = result.text;

    /* Restore normal poll interval if we were in backoff */
    var wasInBackoff = self._state.consecutiveFailures >= MAX_FAILURES;
    if (wasInBackoff && self._timer !== null) {
      clearTimeout(self._timer);
      self._scheduleNext(self._pollMs);
    }

    /* Detect state transitions (BUG-3: null-check mission) */
    var prevStatus     = self._state.fleetStatus;
    var isFirstLoad    = prevStatus === null;
    var mission        = fleetStatus.mission || {};

    var prevCheckpoint = (prevStatus && prevStatus.mission)
      ? prevStatus.mission.checkpoint_number
      : null;
    var newCheckpoint  = mission.checkpoint_number;
    var checkpointChanged = !isFirstLoad && newCheckpoint !== prevCheckpoint;

    var missionComplete = mission.status === 'complete';
    var wasComplete     = (prevStatus && prevStatus.mission)
      ? prevStatus.mission.status === 'complete'
      : false;
    var justCompleted   = missionComplete && !wasComplete;

    /* Supplementary fetches */
    var fetchSailingOrders = isFirstLoad
      ? fetchJSON(basePath, 'sailing-orders.json')
      : Promise.resolve(null);

    var fetchBattlePlan = (isFirstLoad || checkpointChanged)
      ? fetchJSON(basePath, 'battle-plan.json')
      : Promise.resolve(null);

    var fetchMissionLog = (isFirstLoad || checkpointChanged)
      ? fetchJSON(basePath, 'mission-log.json')
      : Promise.resolve(null);

    var fetchStandDown = justCompleted
      ? fetchJSON(basePath, 'stand-down.json')
      : Promise.resolve(null);

    return Promise.all([
      fetchSailingOrders,
      fetchBattlePlan,
      fetchMissionLog,
      fetchStandDown
    ]).then(function (results) {
      var nextState = Object.freeze({
        mission:            self._mission,
        fleetStatus:        Object.freeze(fleetStatus),
        sailingOrders:      (results[0] ? Object.freeze(results[0].data) : null) || self._state.sailingOrders,
        battlePlan:         (results[1] ? Object.freeze(results[1].data) : null) || self._state.battlePlan,
        missionLog:         (results[2] ? Object.freeze(results[2].data) : null) || self._state.missionLog,
        standDown:          (results[3] ? Object.freeze(results[3].data) : null) || self._state.standDown,
        connectionState:    'connected',
        consecutiveFailures: 0
      });

      self._state = nextState;
      if (self._callback) { self._callback(self._state); }
    });
  };

  /**
   * Handle a failed fleet-status fetch.
   * Increments failure counter and transitions to backoff if needed.
   */
  DataLoader.prototype._handlePollFailure = function () {
    var failures = this._state.consecutiveFailures + 1;
    var lostConn = failures >= MAX_FAILURES;

    /* Back off the polling interval when connection is lost */
    if (lostConn && this._timer !== null) {
      clearTimeout(this._timer);
      this._scheduleNext(BACKOFF_POLL_MS);
    }

    var failState = Object.freeze(Object.assign({}, this._state, {
      connectionState:     lostConn ? 'lost' : this._state.connectionState,
      consecutiveFailures: failures
    }));

    this._state = failState;
    if (this._callback) { this._callback(this._state); }
  };

  /**
   * Core polling logic.  Fetches fleet-status.json and, on
   * relevant state transitions, supplementary documents.
   * Creates a new frozen state object and notifies the callback
   * only when something has changed.
   *
   * @returns {Promise<void>}
   */
  DataLoader.prototype._poll = function () {
    var self     = this;
    var basePath = this._mission ? ('/' + this._mission) : '.';

    self._inflight = true;
    return fetchJSON(basePath, 'fleet-status.json').then(function (result) {
      if (result === null || !validateFleetStatus(result.data)) {
        self._handlePollFailure();
        return;
      }
      return self._handlePollSuccess(result);
    }).catch(function () {
      self._handlePollFailure();
    }).then(function () {
      self._inflight = false;
    });
  };

  /* -- Attach static helpers --------------------------------- */

  DataLoader.hullClass              = hullClass;
  DataLoader.taskStatusFromSquadron = taskStatusFromSquadron;
  DataLoader.getParams              = getParams;

  /* -- Expose on global ------------------------------------- */

  global.DataLoader = DataLoader;

}(typeof window !== 'undefined' ? window : this));
