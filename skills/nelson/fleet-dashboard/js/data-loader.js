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

  /* -- URL parameter helpers --------------------------------- */

  /**
   * Read `mission` and `poll` from the current URL search params.
   * `poll` is clamped to a minimum of MIN_POLL_MS.
   *
   * @returns {{ mission: string|null, pollMs: number }}
   */
  function getParams() {
    var params  = new URLSearchParams(global.location.search);
    var mission = params.get('mission') || null;
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

  /* -- Fetch helper ------------------------------------------ */

  /**
   * Fetch a JSON file relative to `basePath`.
   * Returns the parsed object on success, or null on any error
   * (network failure, non-2xx response, parse error).
   *
   * @param {string}      basePath  Base directory path (no trailing slash).
   * @param {string}      filename  Filename to fetch.
   * @returns {Promise<object|null>}
   */
  function fetchJSON(basePath, filename) {
    var url = basePath + '/' + filename;
    return fetch(url)
      .then(function (response) {
        if (!response.ok) { return null; }
        return response.json();
      })
      .catch(function () {
        return null;
      });
  }

  /* -- Static utility helpers -------------------------------- */

  /**
   * Map a hull_integrity_status string to its lowercase CSS class name.
   *
   * @param {string} status  'Green' | 'Amber' | 'Red' | 'Critical'
   * @returns {string}
   */
  function hullClass(status) {
    if (typeof status !== 'string') { return 'unknown'; }
    return status.toLowerCase();
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

  /**
   * Deep-equality check via JSON serialisation.
   *
   * @param {*} prev
   * @param {*} next
   * @returns {boolean}
   */
  function didChange(prev, next) {
    return JSON.stringify(prev) !== JSON.stringify(next);
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
    var urlParams  = getParams();
    this._mission  = urlParams.mission;
    this._pollMs   = urlParams.pollMs;
    this._state    = createEmptyState(urlParams.mission);
    this._timer    = null;
    this._callback = null;
  }

  /**
   * Start polling.  Runs an immediate first poll then schedules
   * subsequent polls on the configured interval.
   *
   * @param {function(Readonly<object>): void} callback
   */
  DataLoader.prototype.start = function (callback) {
    this._callback = callback;
    var self = this;
    this._poll().then(function () {
      self._timer = setInterval(function () {
        self._poll();
      }, self._pollMs);
    });
  };

  /**
   * Stop polling and clear the scheduled interval.
   */
  DataLoader.prototype.stop = function () {
    if (this._timer !== null) {
      clearInterval(this._timer);
      this._timer = null;
    }
  };

  /**
   * Trigger an immediate out-of-band poll without waiting for the
   * next scheduled tick.
   */
  DataLoader.prototype.forceRefresh = function () {
    this._poll();
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
    var basePath = this._mission || '.';

    return fetchJSON(basePath, 'fleet-status.json').then(function (fleetStatus) {

      /* ---- Failure path ------------------------------------ */
      if (fleetStatus === null) {
        var failures = self._state.consecutiveFailures + 1;
        var lostConn = failures >= MAX_FAILURES;

        /* Back off the polling interval when connection is lost */
        if (lostConn && self._timer !== null) {
          clearInterval(self._timer);
          self._timer = setInterval(function () {
            self._poll();
          }, BACKOFF_POLL_MS);
        }

        var failState = Object.freeze(Object.assign({}, self._state, {
          connectionState:     lostConn ? 'lost' : self._state.connectionState,
          consecutiveFailures: failures
        }));

        if (didChange(self._state, failState)) {
          self._state = failState;
          if (self._callback) { self._callback(self._state); }
        }
        return;
      }

      /* ---- Success: restore interval if we were in backoff - */
      var wasInBackoff = self._state.consecutiveFailures >= MAX_FAILURES;
      if (wasInBackoff && self._timer !== null) {
        clearInterval(self._timer);
        self._timer = setInterval(function () {
          self._poll();
        }, self._pollMs);
      }

      /* ---- Detect state transitions ----------------------- */
      var prevStatus = self._state.fleetStatus;
      var isFirstLoad = prevStatus === null;

      var prevCheckpoint = prevStatus
        ? prevStatus.mission.checkpoint_number
        : null;
      var newCheckpoint  = fleetStatus.mission.checkpoint_number;
      var checkpointChanged = !isFirstLoad && newCheckpoint !== prevCheckpoint;

      var missionComplete = fleetStatus.mission.status === 'complete';
      var wasComplete = prevStatus
        ? prevStatus.mission.status === 'complete'
        : false;
      var justCompleted = missionComplete && !wasComplete;

      /* ---- Supplementary fetches -------------------------- */
      var fetchSailingOrders = isFirstLoad
        ? fetchJSON(basePath, 'sailing-orders.json')
        : Promise.resolve(self._state.sailingOrders);

      var fetchBattlePlan = (isFirstLoad || checkpointChanged)
        ? fetchJSON(basePath, 'battle-plan.json')
        : Promise.resolve(self._state.battlePlan);

      var fetchMissionLog = (isFirstLoad || checkpointChanged)
        ? fetchJSON(basePath, 'mission-log.json')
        : Promise.resolve(self._state.missionLog);

      var fetchStandDown = justCompleted
        ? fetchJSON(basePath, 'stand-down.json')
        : Promise.resolve(self._state.standDown);

      return Promise.all([
        fetchSailingOrders,
        fetchBattlePlan,
        fetchMissionLog,
        fetchStandDown
      ]).then(function (results) {
        var sailingOrders = results[0];
        var battlePlan    = results[1];
        var missionLog    = results[2];
        var standDown     = results[3];

        var nextState = Object.freeze({
          mission:            self._mission,
          fleetStatus:        Object.freeze(fleetStatus),
          sailingOrders:      sailingOrders ? Object.freeze(sailingOrders) : null,
          battlePlan:         battlePlan    ? Object.freeze(battlePlan)    : null,
          missionLog:         missionLog    ? Object.freeze(missionLog)    : null,
          standDown:          standDown     ? Object.freeze(standDown)     : null,
          connectionState:    'connected',
          consecutiveFailures: 0
        });

        if (didChange(self._state, nextState)) {
          self._state = nextState;
          if (self._callback) { self._callback(self._state); }
        }
      });
    });
  };

  /* -- Attach static helpers --------------------------------- */

  DataLoader.hullClass              = hullClass;
  DataLoader.taskStatusFromSquadron = taskStatusFromSquadron;
  DataLoader.getParams              = getParams;

  /* -- Expose on global ------------------------------------- */

  global.DataLoader = DataLoader;

}(typeof window !== 'undefined' ? window : this));
