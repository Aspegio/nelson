/* ============================================================
   NELSON FLEET DASHBOARD — Renderer
   Safe DOM construction via textContent / createElement.
   No raw string concatenation into innerHTML with unsanitised data.

   Public API (via window.Renderer):
     Renderer.render(state)  — update all dashboard sections
   ============================================================ */

(function (global) {
  'use strict';

  /* -- Helpers ----------------------------------------------- */

  /** @param {string} id @returns {HTMLElement|null} */
  function $(id) {
    return document.getElementById(id);
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
    var pad = function (n) { return String(n).padStart(2, '0'); };
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
    if (num >= 1000000) { return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M'; }
    if (num >= 1000)    { return Math.round(num / 1000) + 'K'; }
    return String(num);
  }

  /**
   * XSS-safe HTML entity encoder.
   * Creates a temporary span, assigns the raw string to textContent
   * (which entity-encodes it), then reads back innerHTML.
   *
   * @param {string} str
   * @returns {string}
   */
  function esc(str) {
    var el = document.createElement('span');
    el.textContent = String(str == null ? '' : str);
    return el.innerHTML;
  }

  /* -- Icon maps --------------------------------------------- */

  /**
   * Maps hull_integrity_status / task_status keys to
   * { icon: char, cls: CSS-modifier } pairs.
   */
  var STATUS_ICONS = {
    green:       { icon: '●', cls: 'success' },
    amber:       { icon: '●', cls: 'warning' },
    red:         { icon: '●', cls: 'danger'  },
    critical:    { icon: '▲', cls: 'danger'  },
    completed:   { icon: '✔', cls: 'success' },
    in_progress: { icon: '▶', cls: 'info'    },
    pending:     { icon: '○', cls: 'system'  },
    blocked:     { icon: '✖', cls: 'danger'  }
  };

  /**
   * Maps event-text keywords to icon chars.
   * Evaluated in order — first match wins.
   */
  var EVENT_ICONS = [
    { test: /complet/i,   icon: '✔', cls: 'success' },
    { test: /hull|damage/i, icon: '▲', cls: 'warning' },
    { test: /relief|overboard/i, icon: '⚑', cls: 'warning' },
    { test: /block/i,     icon: '✖', cls: 'danger'  },
    { test: /start|begin/i, icon: '▶', cls: 'info'  },
    { test: /checkpoint/i, icon: '⚓', cls: 'info'   },
    { test: /error|fail/i, icon: '✖', cls: 'danger'  }
  ];

  /**
   * Derive an { icon, cls } pair from an event text string.
   *
   * @param {string} text
   * @returns {{ icon: string, cls: string }}
   */
  function eventIcon(text) {
    for (var i = 0; i < EVENT_ICONS.length; i++) {
      if (EVENT_ICONS[i].test.test(text)) {
        return { icon: EVENT_ICONS[i].icon, cls: EVENT_ICONS[i].cls };
      }
    }
    return { icon: '·', cls: 'system' };
  }

  /* -- Text-setting helper ----------------------------------- */

  /**
   * Set an element's textContent only if the value has changed,
   * avoiding unnecessary layout invalidations.
   *
   * @param {HTMLElement} el
   * @param {string}      text
   */
  function setText(el, text) {
    if (el && el.textContent !== text) {
      el.textContent = text;
    }
  }

  /* -- Header ----------------------------------------------- */

  /**
   * Update mission outcome text, status badge, and polling dot.
   *
   * @param {Readonly<object>} state
   */
  function renderHeader(state) {
    var fleetStatus = state.fleetStatus;
    var mission     = fleetStatus && fleetStatus.mission;

    /* Mission outcome */
    var outcomeEl = $('mission-outcome');
    setText(outcomeEl, (mission && mission.outcome) ? mission.outcome : '');

    /* Status badge */
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

    /* Polling dot */
    var dotEl = $('polling-dot');
    if (dotEl) {
      var connLost  = state.connectionState === 'lost';
      var wantLost  = connLost;
      var wantActive = !connLost;
      if (wantActive && !dotEl.classList.contains('polling--active')) {
        dotEl.classList.remove('polling--lost');
        dotEl.classList.add('polling--active');
      } else if (wantLost && !dotEl.classList.contains('polling--lost')) {
        dotEl.classList.remove('polling--active');
        dotEl.classList.add('polling--lost');
      }
    }
  }

  /* -- Ship card builder ------------------------------------- */

  /**
   * Build a complete ship card element from a squadron ship object.
   * All text is set via textContent; no innerHTML with dynamic values.
   *
   * @param {object} ship
   * @returns {HTMLElement}
   */
  function createShipCard(ship) {
    var hullPct   = typeof ship.hull_integrity_pct === 'number' ? ship.hull_integrity_pct : 0;
    var hullSt    = (ship.hull_integrity_status || 'green').toLowerCase();
    var hullCls   = DataLoader.hullClass(ship.hull_integrity_status || 'green');

    var card = document.createElement('div');
    card.className = 'ship-card hull--' + hullCls;
    if (ship.relief_requested) {
      card.classList.add('ship-card--highlight');
    }

    /* Name row */
    var nameEl = document.createElement('div');
    nameEl.className = 'ship-card__name';
    nameEl.textContent = ship.ship_name || '—';
    card.appendChild(nameEl);

    /* Class / role row */
    var classEl = document.createElement('div');
    classEl.className = 'ship-card__class';
    var classText = ship.ship_class || '';
    if (ship.role && ship.role !== 'ship') {
      classText += classText ? ' · ' + ship.role : ship.role;
    }
    classEl.textContent = classText || '—';
    card.appendChild(classEl);

    /* Hull bar track */
    var trackEl = document.createElement('div');
    trackEl.className = 'ship-card__hull-bar-track';

    var barEl = document.createElement('div');
    barEl.className = 'ship-card__hull-bar hull--' + hullCls;
    barEl.style.width = Math.max(0, Math.min(100, hullPct)) + '%';
    trackEl.appendChild(barEl);
    card.appendChild(trackEl);

    /* Hull label */
    var labelEl = document.createElement('div');
    labelEl.className = 'ship-card__hull-label';

    var lblLeft = document.createElement('span');
    lblLeft.textContent = 'Hull';
    var lblRight = document.createElement('span');
    lblRight.textContent = hullPct + '% · ' + (ship.hull_integrity_status || '—');
    labelEl.appendChild(lblLeft);
    labelEl.appendChild(lblRight);
    card.appendChild(labelEl);

    /* Task name */
    var taskEl = document.createElement('div');
    taskEl.className = 'ship-card__task';
    taskEl.textContent = ship.task_name || '—';
    card.appendChild(taskEl);

    /* Task status */
    var taskStatusEl = document.createElement('div');
    taskStatusEl.className = 'ship-card__task-status';
    var tsKey = (ship.task_status || '').toLowerCase();
    var tsIcon = STATUS_ICONS[tsKey] || { icon: '○', cls: 'system' };
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

  /**
   * Render the squadron sidebar.
   * Rebuilds all cards when the count changes; updates in-place otherwise.
   *
   * @param {Readonly<object>} state
   */
  function renderSquadron(state) {
    var container = $('ship-cards');
    if (!container) { return; }

    var squadron = (state.fleetStatus && state.fleetStatus.squadron) || [];
    var existing = container.querySelectorAll('.ship-card');

    if (existing.length !== squadron.length) {
      /* Rebuild entirely */
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
      for (var i = 0; i < squadron.length; i++) {
        container.appendChild(createShipCard(squadron[i]));
      }
    } else {
      /* Update existing cards in-place */
      for (var j = 0; j < squadron.length; j++) {
        var ship    = squadron[j];
        var card    = existing[j];
        var hullCls = DataLoader.hullClass(ship.hull_integrity_status || 'green');
        var hullPct = typeof ship.hull_integrity_pct === 'number' ? ship.hull_integrity_pct : 0;

        /* Hull classes on card container */
        card.className = 'ship-card hull--' + hullCls;
        if (ship.relief_requested) { card.classList.add('ship-card--highlight'); }

        /* Name */
        var nameEl = card.querySelector('.ship-card__name');
        if (nameEl) { setText(nameEl, ship.ship_name || '—'); }

        /* Class / role */
        var classEl = card.querySelector('.ship-card__class');
        if (classEl) {
          var classText = ship.ship_class || '';
          if (ship.role && ship.role !== 'ship') {
            classText += classText ? ' · ' + ship.role : ship.role;
          }
          setText(classEl, classText || '—');
        }

        /* Hull bar */
        var barEl = card.querySelector('.ship-card__hull-bar');
        if (barEl) {
          barEl.className = 'ship-card__hull-bar hull--' + hullCls;
          var safeWidth = Math.max(0, Math.min(100, hullPct)) + '%';
          if (barEl.style.width !== safeWidth) { barEl.style.width = safeWidth; }
        }

        /* Hull label right span */
        var lblRight = card.querySelector('.ship-card__hull-label span:last-child');
        if (lblRight) {
          setText(lblRight, hullPct + '% · ' + (ship.hull_integrity_status || '—'));
        }

        /* Task name */
        var taskEl = card.querySelector('.ship-card__task');
        if (taskEl) { setText(taskEl, ship.task_name || '—'); }

        /* Task status */
        var taskStatusEl = card.querySelector('.ship-card__task-status');
        if (taskStatusEl) {
          var tsKey  = (ship.task_status || '').toLowerCase();
          var tsIcon = STATUS_ICONS[tsKey] || { icon: '○', cls: 'system' };
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
    }
  }

  /* -- Task row builder ------------------------------------- */

  /**
   * Build a `<tr>` element for a single task.
   *
   * @param {object} task   — from battlePlan.tasks
   * @param {string} status — resolved task status string
   * @returns {HTMLTableRowElement}
   */
  function createTaskRow(task, status) {
    var tr = document.createElement('tr');

    var statusLower = (status || 'pending').toLowerCase();
    if (statusLower === 'completed') { tr.classList.add('task--completed'); }
    else if (statusLower === 'blocked')     { tr.classList.add('task--blocked'); }
    else if (statusLower === 'in_progress') { tr.classList.add('task--active'); }

    /* # */
    var tdId = document.createElement('td');
    tdId.style.cssText = 'color: var(--text-dim); font-variant-numeric: tabular-nums; white-space: nowrap;';
    tdId.textContent = String(task.id != null ? task.id : '—');
    tr.appendChild(tdId);

    /* Task name */
    var tdName = document.createElement('td');
    tdName.textContent = task.name || '—';
    tr.appendChild(tdName);

    /* Owner */
    var tdOwner = document.createElement('td');
    tdOwner.style.cssText = 'white-space: nowrap; color: var(--text-secondary);';
    tdOwner.textContent = task.owner || '—';
    tr.appendChild(tdOwner);

    /* Status */
    var tdStatus = document.createElement('td');
    tdStatus.style.cssText = 'white-space: nowrap;';
    var sKey  = statusLower;
    var sIcon = STATUS_ICONS[sKey] || { icon: '○', cls: 'system' };
    var iconSp = document.createElement('span');
    iconSp.className = 'task-status-icon event-entry__icon--' + sIcon.cls;
    iconSp.textContent = sIcon.icon;
    var sTxt = document.createElement('span');
    sTxt.textContent = statusLower.replace(/_/g, ' ');
    tdStatus.appendChild(iconSp);
    tdStatus.appendChild(sTxt);
    tr.appendChild(tdStatus);

    /* Station tier badge */
    var tdStn = document.createElement('td');
    var tier  = task.station_tier != null ? task.station_tier : '';
    var badge = document.createElement('span');
    badge.className = 'station-badge' + (tier !== '' ? ' station-badge--' + tier : '');
    badge.textContent = tier !== '' ? String(tier) : '—';
    tdStn.appendChild(badge);
    tr.appendChild(tdStn);

    return tr;
  }

  /* -- Tasks ------------------------------------------------- */

  /**
   * Render the tasks table.
   * Uses battlePlan.tasks when available, falling back to squadron data.
   *
   * @param {Readonly<object>} state
   */
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
      /* Fall back: derive tasks from squadron */
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

    /* Build new rows and serialise for comparison */
    var newRows = tasks.map(function (t) { return createTaskRow(t, t.status); });
    var newHTML = newRows.map(function (r) { return r.outerHTML; }).join('');
    var oldHTML = tbody.innerHTML;

    if (newHTML !== oldHTML) {
      while (tbody.firstChild) { tbody.removeChild(tbody.firstChild); }
      for (var i = 0; i < newRows.length; i++) {
        tbody.appendChild(newRows[i]);
      }
    }
  }

  /* -- Progress --------------------------------------------- */

  /**
   * Render the progress bar and label.
   *
   * @param {Readonly<object>} state
   */
  function renderProgress(state) {
    var progress  = state.fleetStatus && state.fleetStatus.progress;
    var barEl     = $('progress-bar');
    var labelEl   = $('progress-label');

    if (!progress) {
      if (barEl)   { barEl.style.width = '0%'; }
      if (labelEl) { setText(labelEl, '0 / 0 tasks'); }
      return;
    }

    var completed = typeof progress.completed === 'number' ? progress.completed : 0;
    var total     = typeof progress.total     === 'number' ? progress.total     : 0;
    var pct       = total > 0 ? Math.round((completed / total) * 100) : 0;

    if (barEl) {
      var width = pct + '%';
      if (barEl.style.width !== width) { barEl.style.width = width; }
    }

    if (labelEl) {
      var parts = [completed + ' / ' + total + ' tasks'];
      if (typeof progress.blocked === 'number' && progress.blocked > 0) {
        parts.push(progress.blocked + ' blocked');
      }
      setText(labelEl, parts.join(' · '));
    }
  }

  /* -- Budget ----------------------------------------------- */

  /**
   * Render the budget bar and label.
   * Applies colour class based on thresholds: green < 60%, amber 60–79%, red >= 80%.
   *
   * @param {Readonly<object>} state
   */
  function renderBudget(state) {
    var budget  = state.fleetStatus && state.fleetStatus.budget;
    var barEl   = $('budget-bar');
    var labelEl = $('budget-label');

    if (!budget) {
      if (barEl)   { barEl.style.width = '0%'; }
      if (labelEl) { setText(labelEl, '—'); }
      return;
    }

    var pct   = typeof budget.pct_consumed === 'number' ? budget.pct_consumed : 0;
    var width = Math.min(100, Math.max(0, pct)) + '%';

    if (barEl) {
      if (barEl.style.width !== width) { barEl.style.width = width; }

      var colourCls = pct >= 80 ? 'budget--red' : pct >= 60 ? 'budget--amber' : 'budget--green';
      ['budget--green', 'budget--amber', 'budget--red'].forEach(function (cls) {
        if (cls === colourCls) {
          if (!barEl.classList.contains(cls)) { barEl.classList.add(cls); }
        } else {
          barEl.classList.remove(cls);
        }
      });
    }

    if (labelEl) {
      var spent     = formatTokens(budget.tokens_spent);
      var remaining = formatTokens(budget.tokens_remaining);
      var label     = spent + ' spent · ' + remaining + ' remaining (' + Math.round(pct) + '%)';
      if (typeof budget.burn_rate_per_checkpoint === 'number' && budget.burn_rate_per_checkpoint > 0) {
        label += ' · ' + formatTokens(budget.burn_rate_per_checkpoint) + '/chk';
      }
      setText(labelEl, label);
    }
  }

  /* -- Events ----------------------------------------------- */

  /**
   * Render the events log.
   * Rebuilds the list when content changes.
   *
   * @param {Readonly<object>} state
   */
  function renderEvents(state) {
    var container = $('events-log');
    if (!container) { return; }

    var events = (state.fleetStatus && state.fleetStatus.recent_events) || [];
    var lastUpdated = (state.fleetStatus && state.fleetStatus.last_updated) || null;

    if (!Array.isArray(events) || events.length === 0) {
      if (container.childElementCount !== 0) {
        while (container.firstChild) { container.removeChild(container.firstChild); }
      }
      return;
    }

    /* Build fragment from event strings */
    var fragment = document.createDocumentFragment();
    for (var i = 0; i < events.length; i++) {
      var text   = String(events[i]);
      var evIcon = eventIcon(text);

      var entry = document.createElement('div');
      entry.className = 'event-entry';

      /* Timestamp — use last_updated for simplicity (events lack individual timestamps) */
      var timeEl = document.createElement('span');
      timeEl.className = 'event-entry__time';
      timeEl.textContent = lastUpdated ? formatTime(lastUpdated) : '—';
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

    /* Compare serialised output to avoid unnecessary DOM churn */
    var tmpDiv = document.createElement('div');
    tmpDiv.appendChild(fragment.cloneNode(true));
    if (tmpDiv.innerHTML !== container.innerHTML) {
      while (container.firstChild) { container.removeChild(container.firstChild); }
      container.appendChild(fragment);
    }
  }

  /* -- Footer ----------------------------------------------- */

  /**
   * Update checkpoint label, last-updated time, and connection status.
   *
   * @param {Readonly<object>} state
   */
  function renderFooter(state) {
    var mission     = state.fleetStatus && state.fleetStatus.mission;
    var lastUpdated = state.fleetStatus && state.fleetStatus.last_updated;

    /* Checkpoint */
    var ckEl = $('checkpoint-label');
    if (ckEl) {
      var ckNum  = mission && mission.checkpoint_number != null ? mission.checkpoint_number : '—';
      setText(ckEl, 'Checkpoint ' + ckNum);
    }

    /* Last updated */
    var luEl = $('last-updated');
    if (luEl) {
      setText(luEl, formatTime(lastUpdated));
    }

    /* Connection status */
    var csEl = $('connection-status');
    if (csEl) {
      var connState = state.connectionState || 'connecting';
      var connMap = {
        connected:  { text: 'Connected',   colour: 'var(--signal-green)' },
        connecting: { text: 'Connecting…', colour: 'var(--text-dim)'    },
        ok:         { text: 'Connected',   colour: 'var(--signal-green)' },
        lost:       { text: 'Connection lost', colour: 'var(--signal-red)' }
      };
      var conn = connMap[connState] || { text: connState, colour: 'var(--text-dim)' };
      setText(csEl, conn.text);
      if (csEl.style.color !== conn.colour) { csEl.style.color = conn.colour; }
    }
  }

  /* -- Blockers --------------------------------------------- */

  /**
   * Show or hide the blocker banner.
   *
   * @param {Readonly<object>} state
   */
  function renderBlockers(state) {
    var banner  = $('blocker-banner');
    var msgEl   = $('blocker-message');
    if (!banner) { return; }

    var blockers = (state.fleetStatus && state.fleetStatus.blockers) || [];
    if (!Array.isArray(blockers) || blockers.length === 0) {
      if (banner.style.display !== 'none') { banner.style.display = 'none'; }
      return;
    }

    if (banner.style.display !== 'flex') { banner.style.display = 'flex'; }
    if (msgEl) {
      var text = blockers.join(' | ');
      setText(msgEl, text);
    }
  }

  /* -- Mission summary overlay ------------------------------ */

  /**
   * Show the mission summary overlay when the mission status is 'complete'.
   * Populates with stand-down data when available.
   *
   * @param {Readonly<object>} state
   */
  function renderOverlay(state) {
    var overlay = $('mission-summary-overlay');
    if (!overlay) { return; }

    var mission = state.fleetStatus && state.fleetStatus.mission;
    var isComplete = mission && mission.status === 'complete';

    if (!isComplete) {
      /* Keep overlay hidden; do not forcibly close once manually dismissed */
      return;
    }

    var sd = state.standDown;

    /* Title */
    var titleEl = $('summary-title');
    if (titleEl) { setText(titleEl, 'Mission Complete'); }

    /* Outcome subtitle */
    var outcomeEl = $('summary-outcome');
    if (outcomeEl) {
      var outcomeText = (sd && sd.actual_outcome)
        ? sd.actual_outcome
        : (mission && mission.outcome) || 'Stand down.';
      setText(outcomeEl, outcomeText);
    }

    /* Body — summary stats from stand-down */
    var bodyEl = $('summary-body');
    if (bodyEl) {
      while (bodyEl.firstChild) { bodyEl.removeChild(bodyEl.firstChild); }

      if (sd) {
        var stats = [
          ['Outcome achieved', sd.outcome_achieved ? 'Yes' : 'No'],
          ['Duration',  sd.duration_minutes != null ? sd.duration_minutes + ' min' : '—'],
          ['Tasks',     (sd.tasks && sd.tasks.total != null)
            ? sd.tasks.completed + ' / ' + sd.tasks.total + ' completed' : '—'],
          ['Ships used', (sd.fleet && sd.fleet.ships_used != null)
            ? String(sd.fleet.ships_used) : '—'],
          ['Tokens',    (sd.budget && sd.budget.tokens_consumed != null)
            ? formatTokens(sd.budget.tokens_consumed) + ' consumed (' +
              Math.round(sd.budget.pct_consumed || 0) + '%)' : '—']
        ];

        var dl = document.createElement('dl');
        dl.style.cssText = 'display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 1rem;';
        stats.forEach(function (pair) {
          var dt = document.createElement('dt');
          dt.style.cssText = 'color: var(--text-muted); font-size: 0.8rem;';
          dt.textContent = pair[0];
          var dd = document.createElement('dd');
          dd.style.cssText = 'color: var(--text-primary); font-size: 0.8rem;';
          dd.textContent = pair[1];
          dl.appendChild(dt);
          dl.appendChild(dd);
        });
        bodyEl.appendChild(dl);

        /* Mentioned in despatches */
        if (Array.isArray(sd.mentioned_in_despatches) && sd.mentioned_in_despatches.length > 0) {
          var mid = document.createElement('p');
          mid.style.cssText = 'margin-top: 1rem; font-size: 0.8rem; color: var(--text-muted);';
          mid.textContent = 'Mentioned in Despatches';
          bodyEl.appendChild(mid);

          sd.mentioned_in_despatches.forEach(function (entry) {
            var p = document.createElement('p');
            p.style.cssText = 'font-size: 0.8rem; color: var(--text-primary); margin-top: 0.25rem;';
            var strong = document.createElement('strong');
            strong.textContent = entry.ship_name || '—';
            var rest = document.createTextNode(': ' + (entry.contribution || ''));
            p.appendChild(strong);
            p.appendChild(rest);
            bodyEl.appendChild(p);
          });
        }
      } else {
        var p = document.createElement('p');
        p.style.cssText = 'color: var(--text-muted); font-size: 0.85rem;';
        p.textContent = 'Stand-down report is being compiled…';
        bodyEl.appendChild(p);
      }
    }

    /* Show overlay */
    if (overlay.style.display !== 'flex') { overlay.style.display = 'flex'; }

    /* Wire up close button once */
    var closeBtn = $('summary-close');
    if (closeBtn && !closeBtn._nelsonBound) {
      closeBtn._nelsonBound = true;
      closeBtn.addEventListener('click', function () {
        overlay.style.display = 'none';
      });
    }
  }

  /* -- Public render ---------------------------------------- */

  /**
   * Update all dashboard sections from a new state snapshot.
   *
   * @param {Readonly<object>} state
   */
  function render(state) {
    if (!state) { return; }
    renderHeader(state);
    renderSquadron(state);
    renderTasks(state);
    renderProgress(state);
    renderBudget(state);
    renderEvents(state);
    renderFooter(state);
    renderBlockers(state);
    renderOverlay(state);
  }

  /* -- Expose on global ------------------------------------- */

  global.Renderer = { render: render };

}(typeof window !== 'undefined' ? window : this));
