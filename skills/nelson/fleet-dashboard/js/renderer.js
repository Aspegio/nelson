/* ============================================================
   NELSON FLEET DASHBOARD — Renderer
   Safe DOM construction via textContent / createElement.
   No raw string concatenation into innerHTML with unsanitised data.

   Public API (via window.Renderer):
     Renderer.render(state, dismissState)  — update all dashboard sections
   ============================================================ */

(function (global) {
  'use strict';

  /* -- Aliases from DashboardUtils ----------------------------- */

  var formatTime   = DashboardUtils.formatTime;
  var formatTokens = DashboardUtils.formatTokens;

  /* -- Constants ---------------------------------------------- */

  var BUDGET_RED_THRESHOLD   = 80;
  var BUDGET_AMBER_THRESHOLD = 60;
  var VALID_TIERS = { 0: true, 1: true, 2: true, 3: true };

  /* -- Helpers ----------------------------------------------- */

  /** @param {string} id @returns {HTMLElement|null} */
  function $(id) {
    return document.getElementById(id);
  }

  /* -- Icon maps --------------------------------------------- */

  var STATUS_ICONS = {
    green:       { icon: '\u25CF', cls: 'success' },
    amber:       { icon: '\u25CF', cls: 'warning' },
    red:         { icon: '\u25CF', cls: 'danger'  },
    critical:    { icon: '\u25B2', cls: 'danger'  },
    completed:   { icon: '\u2714', cls: 'success' },
    in_progress: { icon: '\u25B6', cls: 'info'    },
    pending:     { icon: '\u25CB', cls: 'system'  },
    blocked:     { icon: '\u2716', cls: 'danger'  }
  };

  var EVENT_ICONS = [
    { test: /complet/i,   icon: '\u2714', cls: 'success' },
    { test: /hull|damage/i, icon: '\u25B2', cls: 'warning' },
    { test: /relief|overboard/i, icon: '\u2691', cls: 'warning' },
    { test: /block/i,     icon: '\u2716', cls: 'danger'  },
    { test: /start|begin/i, icon: '\u25B6', cls: 'info'  },
    { test: /checkpoint/i, icon: '\u2693', cls: 'info'   },
    { test: /error|fail/i, icon: '\u2716', cls: 'danger'  }
  ];

  function eventIcon(text) {
    for (var i = 0; i < EVENT_ICONS.length; i++) {
      if (EVENT_ICONS[i].test.test(text)) {
        return { icon: EVENT_ICONS[i].icon, cls: EVENT_ICONS[i].cls };
      }
    }
    return { icon: '\u00B7', cls: 'system' };
  }

  /* -- Text-setting helper ----------------------------------- */

  function setText(el, text) {
    if (el && el.textContent !== text) {
      el.textContent = text;
    }
  }

  /* -- Header ----------------------------------------------- */

  function renderHeader(state) {
    var fleetStatus = state.fleetStatus;
    var mission     = fleetStatus && fleetStatus.mission;

    var outcomeEl = $('mission-outcome');
    setText(outcomeEl, (mission && mission.outcome) ? mission.outcome : '');

    var badgeEl = $('status-badge');
    if (badgeEl) {
      var status     = (mission && mission.status) || '';
      var badgeText  = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Initialising';
      setText(badgeEl, badgeText);

      var wantUnderway = (status === 'underway');
      var wantComplete = (status === 'complete');
      if (wantUnderway && !badgeEl.classList.contains('status--underway')) {
        badgeEl.classList.remove('status--complete');
        badgeEl.classList.add('status--underway');
      } else if (wantComplete && !badgeEl.classList.contains('status--complete')) {
        badgeEl.classList.remove('status--underway');
        badgeEl.classList.add('status--complete');
      }
    }

    var dotEl = $('polling-dot');
    if (dotEl) {
      var connLost   = state.connectionState === 'lost';
      var wantActive = !connLost;
      if (wantActive && !dotEl.classList.contains('polling--active')) {
        dotEl.classList.remove('polling--lost');
        dotEl.classList.add('polling--active');
      } else if (connLost && !dotEl.classList.contains('polling--lost')) {
        dotEl.classList.remove('polling--active');
        dotEl.classList.add('polling--lost');
      }
    }
  }

  /* -- Ship card shared population (QUAL-4) ------------------- */

  /**
   * Populate (or update) a ship card's children from ship data.
   * Used by both createShipCard and the in-place update path.
   *
   * @param {HTMLElement} card
   * @param {object}      ship
   */
  function populateShipCard(card, ship) {
    var hullCls = DataLoader.hullClass(ship.hull_integrity_status || 'green');
    var hullPct = typeof ship.hull_integrity_pct === 'number' ? ship.hull_integrity_pct : 0;

    card.className = 'ship-card hull--' + hullCls;
    if (ship.relief_requested) { card.classList.add('ship-card--highlight'); }

    var nameEl = card.querySelector('.ship-card__name');
    if (nameEl) { setText(nameEl, ship.ship_name || '\u2014'); }

    var classEl = card.querySelector('.ship-card__class');
    if (classEl) {
      var classText = ship.ship_class || '';
      if (ship.role && ship.role !== 'ship') {
        classText += classText ? ' \u00B7 ' + ship.role : ship.role;
      }
      setText(classEl, classText || '\u2014');
    }

    var barEl = card.querySelector('.ship-card__hull-bar');
    if (barEl) {
      barEl.className = 'ship-card__hull-bar hull--' + hullCls;
      var safeWidth = Math.max(0, Math.min(100, hullPct)) + '%';
      if (barEl.style.width !== safeWidth) { barEl.style.width = safeWidth; }
    }

    var lblRight = card.querySelector('.ship-card__hull-label span:last-child');
    if (lblRight) {
      setText(lblRight, hullPct + '% \u00B7 ' + (ship.hull_integrity_status || '\u2014'));
    }

    var taskEl = card.querySelector('.ship-card__task');
    if (taskEl) { setText(taskEl, ship.task_name || '\u2014'); }

    var taskStatusEl = card.querySelector('.ship-card__task-status');
    if (taskStatusEl) {
      var tsKey  = (ship.task_status || '').toLowerCase();
      var tsIcon = STATUS_ICONS[tsKey] || { icon: '\u25CB', cls: 'system' };
      var iconSp = taskStatusEl.querySelector('.task-status-icon');
      if (iconSp) {
        iconSp.className = 'task-status-icon event-entry__icon--' + tsIcon.cls;
        setText(iconSp, tsIcon.icon);
      }
      var tsTxt = taskStatusEl.querySelector('span:last-child');
      if (tsTxt) {
        setText(tsTxt, (ship.task_status || 'pending').replace(/_/g, ' '));
      }
    }
  }

  /* -- Ship card builder ------------------------------------- */

  /**
   * Build a complete ship card element from a squadron ship object.
   * A11Y-8: Creates <li> elements with aria-label.
   *
   * @param {object} ship
   * @returns {HTMLElement}
   */
  function createShipCard(ship) {
    var hullPct = typeof ship.hull_integrity_pct === 'number' ? ship.hull_integrity_pct : 0;
    var hullCls = DataLoader.hullClass(ship.hull_integrity_status || 'green');

    var card = document.createElement('li');
    card.className = 'ship-card hull--' + hullCls;
    card.setAttribute('aria-label',
      (ship.ship_name || 'Unknown') + ', hull ' + hullPct + '%, ' +
      (ship.task_status || 'pending').replace(/_/g, ' '));
    if (ship.relief_requested) {
      card.classList.add('ship-card--highlight');
    }

    var nameEl = document.createElement('div');
    nameEl.className = 'ship-card__name';
    nameEl.textContent = ship.ship_name || '\u2014';
    card.appendChild(nameEl);

    var classEl = document.createElement('div');
    classEl.className = 'ship-card__class';
    var classText = ship.ship_class || '';
    if (ship.role && ship.role !== 'ship') {
      classText += classText ? ' \u00B7 ' + ship.role : ship.role;
    }
    classEl.textContent = classText || '\u2014';
    card.appendChild(classEl);

    var trackEl = document.createElement('div');
    trackEl.className = 'ship-card__hull-bar-track';
    var barEl = document.createElement('div');
    barEl.className = 'ship-card__hull-bar hull--' + hullCls;
    barEl.style.width = Math.max(0, Math.min(100, hullPct)) + '%';
    trackEl.appendChild(barEl);
    card.appendChild(trackEl);

    var labelEl = document.createElement('div');
    labelEl.className = 'ship-card__hull-label';
    var lblLeft = document.createElement('span');
    lblLeft.textContent = 'Hull';
    var lblRight = document.createElement('span');
    lblRight.textContent = hullPct + '% \u00B7 ' + (ship.hull_integrity_status || '\u2014');
    labelEl.appendChild(lblLeft);
    labelEl.appendChild(lblRight);
    card.appendChild(labelEl);

    var taskEl = document.createElement('div');
    taskEl.className = 'ship-card__task';
    taskEl.textContent = ship.task_name || '\u2014';
    card.appendChild(taskEl);

    var taskStatusEl = document.createElement('div');
    taskStatusEl.className = 'ship-card__task-status';
    var tsKey = (ship.task_status || '').toLowerCase();
    var tsIcon = STATUS_ICONS[tsKey] || { icon: '\u25CB', cls: 'system' };
    var iconSpan = document.createElement('span');
    iconSpan.className = 'task-status-icon event-entry__icon--' + tsIcon.cls;
    iconSpan.textContent = tsIcon.icon;
    var tsText = document.createElement('span');
    tsText.textContent = (ship.task_status || 'pending').replace(/_/g, ' ');
    taskStatusEl.appendChild(iconSpan);
    taskStatusEl.appendChild(tsText);
    card.appendChild(taskStatusEl);

    return card;
  }

  /* -- Squadron --------------------------------------------- */

  function renderSquadron(state) {
    var container = $('ship-cards');
    if (!container) { return; }

    var squadron = (state.fleetStatus && state.fleetStatus.squadron) || [];
    var existing = container.querySelectorAll('.ship-card');

    if (existing.length !== squadron.length) {
      while (container.firstChild) { container.removeChild(container.firstChild); }
      for (var i = 0; i < squadron.length; i++) {
        container.appendChild(createShipCard(squadron[i]));
      }
    } else {
      for (var j = 0; j < squadron.length; j++) {
        populateShipCard(existing[j], squadron[j]);
      }
    }
  }

  /* -- Task row builder ------------------------------------- */

  function createTaskRow(task, status) {
    var tr = document.createElement('tr');
    var statusLower = (status || 'pending').toLowerCase();

    if (statusLower === 'completed')       { tr.classList.add('task--completed'); }
    else if (statusLower === 'blocked')    { tr.classList.add('task--blocked'); }
    else if (statusLower === 'in_progress') { tr.classList.add('task--active'); }

    var tdId = document.createElement('td');
    tdId.className = 'task-cell--id';
    tdId.textContent = String(task.id != null ? task.id : '\u2014');
    tr.appendChild(tdId);

    var tdName = document.createElement('td');
    tdName.textContent = task.name || '\u2014';
    tr.appendChild(tdName);

    var tdOwner = document.createElement('td');
    tdOwner.className = 'task-cell--owner';
    tdOwner.textContent = task.owner || '\u2014';
    tr.appendChild(tdOwner);

    var tdStatus = document.createElement('td');
    tdStatus.className = 'task-cell--status';
    var sKey  = statusLower;
    var sIcon = STATUS_ICONS[sKey] || { icon: '\u25CB', cls: 'system' };
    var iconSp = document.createElement('span');
    iconSp.className = 'task-status-icon event-entry__icon--' + sIcon.cls;
    iconSp.textContent = sIcon.icon;
    var sTxt = document.createElement('span');
    sTxt.textContent = statusLower.replace(/_/g, ' ');
    tdStatus.appendChild(iconSp);
    tdStatus.appendChild(sTxt);
    tr.appendChild(tdStatus);

    /* SEC-2: Station tier validation */
    var tdStn = document.createElement('td');
    var tier  = task.station_tier != null ? task.station_tier : '';
    var safeTier = (tier !== '' && VALID_TIERS[tier]) ? tier : '';
    var badge = document.createElement('span');
    badge.className = 'station-badge' + (safeTier !== '' ? ' station-badge--' + safeTier : '');
    badge.textContent = safeTier !== '' ? String(safeTier) : '\u2014';
    tdStn.appendChild(badge);
    tr.appendChild(tdStn);

    return tr;
  }

  /* -- Tasks (PERF-3: in-place updates) ---------------------- */

  function updateTaskRow(tr, task, status) {
    var statusLower = (status || 'pending').toLowerCase();
    tr.className = '';
    if (statusLower === 'completed')       { tr.classList.add('task--completed'); }
    else if (statusLower === 'blocked')    { tr.classList.add('task--blocked'); }
    else if (statusLower === 'in_progress') { tr.classList.add('task--active'); }

    var cells = tr.querySelectorAll('td');
    if (cells.length < 5) { return; }

    setText(cells[0], String(task.id != null ? task.id : '\u2014'));
    setText(cells[1], task.name || '\u2014');
    setText(cells[2], task.owner || '\u2014');

    var sIcon = STATUS_ICONS[statusLower] || { icon: '\u25CB', cls: 'system' };
    var iconSp = cells[3].querySelector('.task-status-icon');
    if (iconSp) {
      iconSp.className = 'task-status-icon event-entry__icon--' + sIcon.cls;
      setText(iconSp, sIcon.icon);
    }
    var sTxt = cells[3].querySelector('span:last-child');
    if (sTxt) { setText(sTxt, statusLower.replace(/_/g, ' ')); }

    var tier = task.station_tier != null ? task.station_tier : '';
    var safeTier = (tier !== '' && VALID_TIERS[tier]) ? tier : '';
    var badge = cells[4].querySelector('.station-badge');
    if (badge) {
      badge.className = 'station-badge' + (safeTier !== '' ? ' station-badge--' + safeTier : '');
      setText(badge, safeTier !== '' ? String(safeTier) : '\u2014');
    }
  }

  function renderTasks(state) {
    var tbody = $('task-tbody');
    if (!tbody) { return; }

    var squadron   = (state.fleetStatus && state.fleetStatus.squadron) || [];
    var battlePlan = state.battlePlan;
    var tasks;

    if (battlePlan && Array.isArray(battlePlan.tasks) && battlePlan.tasks.length > 0) {
      tasks = battlePlan.tasks.map(function (t) {
        return {
          id:           t.id,
          name:         t.name,
          owner:        t.owner,
          station_tier: t.station_tier,
          status:       DataLoader.taskStatusFromSquadron(squadron, t.id)
        };
      });
    } else {
      tasks = squadron.map(function (ship) {
        return {
          id:           ship.task_id,
          name:         ship.task_name,
          owner:        ship.ship_name,
          station_tier: null,
          status:       ship.task_status
        };
      });
    }

    var existing = tbody.querySelectorAll('tr');
    if (existing.length !== tasks.length) {
      while (tbody.firstChild) { tbody.removeChild(tbody.firstChild); }
      for (var i = 0; i < tasks.length; i++) {
        tbody.appendChild(createTaskRow(tasks[i], tasks[i].status));
      }
    } else {
      for (var j = 0; j < tasks.length; j++) {
        updateTaskRow(existing[j], tasks[j], tasks[j].status);
      }
    }
  }

  /* -- Progress --------------------------------------------- */

  function renderProgress(state) {
    var progress  = state.fleetStatus && state.fleetStatus.progress;
    var barEl     = $('progress-bar');
    var labelEl   = $('progress-label');
    var trackEl   = $('progress-track');

    if (!progress) {
      if (barEl)   { barEl.style.width = '0%'; }
      if (labelEl) { setText(labelEl, '0 / 0 tasks'); }
      if (trackEl) { trackEl.setAttribute('aria-valuenow', '0'); }
      return;
    }

    var completed = typeof progress.completed === 'number' ? progress.completed : 0;
    var total     = typeof progress.total     === 'number' ? progress.total     : 0;
    var pct       = total > 0 ? Math.round((completed / total) * 100) : 0;

    if (barEl) {
      var width = pct + '%';
      if (barEl.style.width !== width) { barEl.style.width = width; }
    }

    if (trackEl) { trackEl.setAttribute('aria-valuenow', String(pct)); }

    if (labelEl) {
      var parts = [completed + ' / ' + total + ' tasks'];
      if (typeof progress.blocked === 'number' && progress.blocked > 0) {
        parts.push(progress.blocked + ' blocked');
      }
      setText(labelEl, parts.join(' \u00B7 '));
    }
  }

  /* -- Budget ----------------------------------------------- */

  function renderBudget(state) {
    var budget  = state.fleetStatus && state.fleetStatus.budget;
    var barEl   = $('budget-bar');
    var labelEl = $('budget-label');
    var trackEl = $('budget-track');

    if (!budget) {
      if (barEl)   { barEl.style.width = '0%'; }
      if (labelEl) { setText(labelEl, '\u2014'); }
      if (trackEl) { trackEl.setAttribute('aria-valuenow', '0'); }
      return;
    }

    var pct   = typeof budget.pct_consumed === 'number' ? budget.pct_consumed : 0;
    var width = Math.min(100, Math.max(0, pct)) + '%';

    if (barEl) {
      if (barEl.style.width !== width) { barEl.style.width = width; }

      var colourCls = pct >= BUDGET_RED_THRESHOLD ? 'budget--red'
        : pct >= BUDGET_AMBER_THRESHOLD ? 'budget--amber'
        : 'budget--green';
      ['budget--green', 'budget--amber', 'budget--red'].forEach(function (cls) {
        if (cls === colourCls) {
          if (!barEl.classList.contains(cls)) { barEl.classList.add(cls); }
        } else {
          barEl.classList.remove(cls);
        }
      });
    }

    if (trackEl) { trackEl.setAttribute('aria-valuenow', String(Math.round(pct))); }

    if (labelEl) {
      var spent     = formatTokens(budget.tokens_spent);
      var remaining = formatTokens(budget.tokens_remaining);
      var label     = spent + ' spent \u00B7 ' + remaining + ' remaining (' + Math.round(pct) + '%)';
      if (typeof budget.burn_rate_per_checkpoint === 'number' && budget.burn_rate_per_checkpoint > 0) {
        label += ' \u00B7 ' + formatTokens(budget.burn_rate_per_checkpoint) + '/chk';
      }
      setText(labelEl, label);
    }
  }

  /* -- Events (PERF-4: fingerprint cache) --------------------- */

  var _lastEventFingerprint = '';

  function renderEvents(state) {
    var container = $('events-log');
    if (!container) { return; }

    var events = (state.fleetStatus && state.fleetStatus.recent_events) || [];
    var lastUpdated = (state.fleetStatus && state.fleetStatus.last_updated) || null;

    if (!Array.isArray(events) || events.length === 0) {
      if (container.childElementCount !== 0) {
        while (container.firstChild) { container.removeChild(container.firstChild); }
        _lastEventFingerprint = '';
      }
      return;
    }

    var fingerprint = events.join('|') + '|' + (lastUpdated || '');
    if (fingerprint === _lastEventFingerprint) { return; }
    _lastEventFingerprint = fingerprint;

    var fragment = document.createDocumentFragment();
    for (var i = 0; i < events.length; i++) {
      var text   = String(events[i]);
      var evIcon = eventIcon(text);

      var entry = document.createElement('div');
      entry.className = 'event-entry';

      var timeEl = document.createElement('span');
      timeEl.className = 'event-entry__time';
      timeEl.textContent = lastUpdated ? formatTime(lastUpdated) : '\u2014';
      entry.appendChild(timeEl);

      var iconEl = document.createElement('span');
      iconEl.className = 'event-entry__icon event-entry__icon--' + evIcon.cls;
      iconEl.setAttribute('aria-hidden', 'true');
      iconEl.textContent = evIcon.icon;
      entry.appendChild(iconEl);

      var textEl = document.createElement('span');
      textEl.className = 'event-entry__text';
      textEl.textContent = text;
      entry.appendChild(textEl);

      fragment.appendChild(entry);
    }

    while (container.firstChild) { container.removeChild(container.firstChild); }
    container.appendChild(fragment);
  }

  /* -- Footer ----------------------------------------------- */

  function renderFooter(state) {
    var mission     = state.fleetStatus && state.fleetStatus.mission;
    var lastUpdated = state.fleetStatus && state.fleetStatus.last_updated;

    var ckEl = $('checkpoint-label');
    if (ckEl) {
      var ckNum = mission && mission.checkpoint_number != null ? mission.checkpoint_number : '\u2014';
      setText(ckEl, 'Checkpoint ' + ckNum);
    }

    var luEl = $('last-updated');
    if (luEl) { setText(luEl, formatTime(lastUpdated)); }

    var csEl = $('connection-status');
    if (csEl) {
      var connState = state.connectionState || 'connecting';
      var connMap = {
        connected:  { text: 'Connected',       colour: 'var(--signal-green)' },
        connecting: { text: 'Connecting\u2026', colour: 'var(--text-dim)'    },
        ok:         { text: 'Connected',        colour: 'var(--signal-green)' },
        lost:       { text: 'Connection lost',  colour: 'var(--signal-red)'  }
      };
      var conn = connMap[connState] || { text: connState, colour: 'var(--text-dim)' };
      setText(csEl, conn.text);
      if (csEl.style.color !== conn.colour) { csEl.style.color = conn.colour; }
    }
  }

  /* -- Blockers (BUG-2: classList only) ----------------------- */

  function renderBlockers(state, dismissState) {
    var banner  = $('blocker-banner');
    var msgEl   = $('blocker-message');
    if (!banner) { return; }

    var blockers = (state.fleetStatus && state.fleetStatus.blockers) || [];
    if (!Array.isArray(blockers) || blockers.length === 0) {
      banner.classList.add('hidden');
      return;
    }

    var text = blockers.join(' | ');

    /* Re-show if blocker text changed (new blocker), otherwise respect dismiss */
    if (dismissState && dismissState.blockerText !== null) {
      if (dismissState.blockerText === text) { return; }
      dismissState.blockerText = null;
    }

    banner.classList.remove('hidden');
    if (msgEl) { setText(msgEl, text); }
  }

  /* -- Overlay body builder (QUAL-4) -------------------------- */

  function createOverlayBody(sd, mission) {
    var bodyFrag = document.createDocumentFragment();

    if (sd) {
      var stats = [
        ['Outcome achieved', sd.outcome_achieved ? 'Yes' : 'No'],
        ['Duration',  sd.duration_minutes != null ? sd.duration_minutes + ' min' : '\u2014'],
        ['Tasks',     (sd.tasks && sd.tasks.total != null)
          ? sd.tasks.completed + ' / ' + sd.tasks.total + ' completed' : '\u2014'],
        ['Ships used', (sd.fleet && sd.fleet.ships_used != null)
          ? String(sd.fleet.ships_used) : '\u2014'],
        ['Tokens',    (sd.budget && sd.budget.tokens_consumed != null)
          ? formatTokens(sd.budget.tokens_consumed) + ' consumed (' +
            Math.round(sd.budget.pct_consumed || 0) + '%)' : '\u2014']
      ];

      var dl = document.createElement('dl');
      dl.className = 'overlay__stats';
      stats.forEach(function (pair) {
        var dt = document.createElement('dt');
        dt.className = 'overlay__stat-label';
        dt.textContent = pair[0];
        var dd = document.createElement('dd');
        dd.className = 'overlay__stat-value';
        dd.textContent = pair[1];
        dl.appendChild(dt);
        dl.appendChild(dd);
      });
      bodyFrag.appendChild(dl);

      if (Array.isArray(sd.mentioned_in_despatches) && sd.mentioned_in_despatches.length > 0) {
        var mid = document.createElement('p');
        mid.className = 'overlay__despatches-title';
        mid.textContent = 'Mentioned in Despatches';
        bodyFrag.appendChild(mid);

        sd.mentioned_in_despatches.forEach(function (entry) {
          var p = document.createElement('p');
          p.className = 'overlay__despatch-entry';
          var strong = document.createElement('strong');
          strong.textContent = entry.ship_name || '\u2014';
          var rest = document.createTextNode(': ' + (entry.contribution || ''));
          p.appendChild(strong);
          p.appendChild(rest);
          bodyFrag.appendChild(p);
        });
      }
    } else {
      var p = document.createElement('p');
      p.className = 'overlay__compiling';
      p.textContent = 'Stand-down report is being compiled\u2026';
      bodyFrag.appendChild(p);
    }

    return bodyFrag;
  }

  /* -- Mission summary overlay (BUG-2, PERF-7, A11Y-4) ------- */

  var _lastStandDown    = undefined;
  var _previousFocusEl  = null;

  function renderOverlay(state, dismissState) {
    var overlay = $('mission-summary-overlay');
    if (!overlay) { return; }

    var mission = state.fleetStatus && state.fleetStatus.mission;
    var isComplete = mission && mission.status === 'complete';

    if (!isComplete) { return; }

    /* BUG-2: Respect dismiss state */
    if (dismissState && dismissState.overlayDismissed) { return; }

    var sd = state.standDown;

    var titleEl = $('summary-title');
    if (titleEl) { setText(titleEl, 'Mission Complete'); }

    var outcomeEl = $('summary-outcome');
    if (outcomeEl) {
      var outcomeText = (sd && sd.actual_outcome)
        ? sd.actual_outcome
        : (mission && mission.outcome) || 'Stand down.';
      setText(outcomeEl, outcomeText);
    }

    /* PERF-7: Only rebuild body when standDown data changes */
    var bodyEl = $('summary-body');
    if (bodyEl && sd !== _lastStandDown) {
      _lastStandDown = sd;
      while (bodyEl.firstChild) { bodyEl.removeChild(bodyEl.firstChild); }
      bodyEl.appendChild(createOverlayBody(sd, mission));
    }

    /* Show overlay */
    var wasHidden = overlay.classList.contains('hidden');
    overlay.classList.remove('hidden');

    /* A11Y-4: Focus management */
    if (wasHidden) {
      _previousFocusEl = document.activeElement;
      var closeBtn = $('summary-close');
      if (closeBtn) { closeBtn.focus(); }
    }

    /* Wire up close button once */
    var closeBtn = $('summary-close');
    if (closeBtn && !closeBtn._nelsonBound) {
      closeBtn._nelsonBound = true;
      closeBtn.addEventListener('click', function () {
        overlay.classList.add('hidden');
        if (dismissState) { dismissState.overlayDismissed = true; }
        if (_previousFocusEl) { _previousFocusEl.focus(); }
      });
    }

    /* A11Y-4: Focus trap within dialog */
    if (!overlay._nelsonTrap) {
      overlay._nelsonTrap = true;
      overlay.addEventListener('keydown', function (e) {
        if (e.key !== 'Tab') { return; }
        var focusable = overlay.querySelectorAll('button, [href], [tabindex]:not([tabindex="-1"])');
        if (focusable.length === 0) { return; }
        var first = focusable[0];
        var last  = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      });
    }
  }

  /* -- Public render ---------------------------------------- */

  function render(state, dismissState) {
    if (!state) { return; }
    renderHeader(state);
    renderSquadron(state);
    renderTasks(state);
    renderProgress(state);
    renderBudget(state);
    renderEvents(state);
    renderFooter(state);
    renderBlockers(state, dismissState);
    renderOverlay(state, dismissState);
  }

  /* -- Expose on global ------------------------------------- */

  global.Renderer = { render: render };

}(typeof window !== 'undefined' ? window : this));
