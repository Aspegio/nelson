"""Shared fixtures for hook tests."""

from __future__ import annotations

import textwrap

import pytest

VALID_STANDARD_BRIEF = textwrap.dedent("""\
    == TURNOVER BRIEF ==
    Ship: HMS Daring (destroyer)
    Role: Captain 1 — auth implementation
    Timestamp: 2026-01-01T12:00:00Z
    Reason for relief: Red hull

    Mission context:
    - Mission: Build auth system
    - Outcome: Working JWT auth
    - Success metric: All tests pass

    Task assignment:
    - Task ID: task-1
    - Task name: Build auth
    - Deliverable: JWT validation module
    - Action station: 1
    - File ownership: src/auth.py
    - Dependencies: none

    Progress log:
    - Implemented JWT validation in src/auth/validate.ts
    - Added tests in tests/auth.test.ts

    Running plot:
    - Working on refresh token rotation
    - Current state: halfway through implementation

    Files touched:
    - src/auth/validate.ts — JWT validation logic
    - tests/auth.test.ts — Test coverage

    Key decisions made:
    - Chose RS256 over HS256 — Rationale: asymmetric signing for microservices

    Hazards and blockers:
    - None discovered

    Recommended course of action:
    - Complete refresh token rotation
    - Add integration tests

    Relief chain:
    - This is the first ship on this task

    == END TURNOVER BRIEF ==
""")

VALID_FLAGSHIP_BRIEF = textwrap.dedent("""\
    == FLAGSHIP TURNOVER BRIEF ==
    Ship: Flagship HMS Victory
    Role: Admiral
    Timestamp: 2026-01-01T12:00:00Z
    Reason for relief: Amber hull at 65%

    Sailing orders:
    - Outcome: Build complete auth system
    - Success metric: All tests pass
    - Deadline: EOD
    - Constraints: None
    - Out of scope: OAuth

    Battle plan status:
    - Task task-1: Build auth | Owner: HMS Daring | Status: in_progress | Notes: on track

    Squadron state:
    - HMS Daring (destroyer) | Captain 1 | Task: task-1 | Hull: Green | Status: active

    Key decisions made:
    - Chose JWT over sessions — Rationale: stateless auth

    Active blockers and risks:
    - None

    Pending escalations:
    - None

    Quarterdeck rhythm:
    - Cadence: every 15 minutes
    - Last checkpoint: checkpoint 3
    - Next scheduled checkpoint: checkpoint 4

    Relief chain:
    - This is the first admiral on this mission

    Recommended course of action:
    - Continue monitoring HMS Daring progress
    - Check hull integrity at next checkpoint

    == END FLAGSHIP TURNOVER BRIEF ==
""")


@pytest.fixture()
def standard_brief() -> str:
    return VALID_STANDARD_BRIEF


@pytest.fixture()
def flagship_brief() -> str:
    return VALID_FLAGSHIP_BRIEF
