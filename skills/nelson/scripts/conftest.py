"""Shared test helpers for Nelson data tests.

Provides common fixtures and utilities used across test_nelson_data.py,
test_nelson_data_fleet.py, and test_nelson_data_memory.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "nelson-data.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(
    *args: str,
    cwd: Path | None = None,
    expect_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run nelson-data.py with the given arguments."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if expect_fail:
        assert result.returncode != 0, (
            f"Expected failure but got rc=0.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    else:
        assert result.returncode == 0, (
            f"Unexpected failure (rc={result.returncode}).\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def init_mission(cwd: Path, **kwargs: str) -> Path:
    """Create a mission via `init` and return the absolute mission directory path."""
    defaults = {
        "--outcome": "Test mission",
        "--metric": "All tests pass",
        "--deadline": "this_session",
        "--token-budget": "100000",
    }
    defaults.update(kwargs)
    cmd_args = []
    for k, v in defaults.items():
        cmd_args.extend([k, v])
    result = run("init", *cmd_args, cwd=cwd)
    # init outputs a relative path — make it absolute relative to cwd
    return cwd / result.stdout.strip()


def add_squadron(mission_dir: Path, captains: list[str] | None = None) -> None:
    """Add a basic squadron to an existing mission."""
    captain_specs = captains or ["HMS Argyll:frigate:sonnet:1"]
    captain_args = []
    for spec in captain_specs:
        captain_args.extend(["--captain", spec])
    run(
        "squadron",
        "--mission-dir", str(mission_dir),
        "--admiral", "HMS Victory",
        "--admiral-model", "opus",
        *captain_args,
        "--mode", "subagents",
    )


def add_task(
    mission_dir: Path,
    task_id: int = 1,
    name: str = "Test task",
    owner: str = "HMS Argyll",
    deps: str = "",
    station_tier: int = 0,
) -> None:
    """Add a task to the battle plan."""
    run(
        "task",
        "--mission-dir", str(mission_dir),
        "--id", str(task_id),
        "--name", name,
        "--owner", owner,
        "--deliverable", f"Deliverable for {name}",
        "--deps", deps,
        "--station-tier", str(station_tier),
        "--files", "",
    )


def read_json(path: Path) -> dict:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def add_estimate(
    mission_dir: Path,
    body: str | None = None,
) -> None:
    """Write a minimal estimate.md to *mission_dir* to satisfy the phase exit."""
    text = body or (
        "# The Estimate\n\n"
        "## 1. Reconnaissance\nTest mission.\n\n"
        "## 2. Task analysis\nTest task.\n\n"
        "## 3. Environment\nTest environment.\n\n"
        "## 4. Courses of action\nSingle course.\n\n"
        "## 5. Coordination\nSingle captain.\n\n"
        "## 6. Execution\nProceed.\n\n"
        "## 7. Control\nWatch for drift.\n"
    )
    (mission_dir / "estimate.md").write_text(text, encoding="utf-8")


def record_estimate_outcome(
    mission_dir: Path,
    *,
    effect_id: str = "E1",
    criterion_id: str = "C1",
    status: str = "pass",
    method: str = "test",
    evidence: str = "pytest -q",
    recorded_by: str = "HMS Argyll",
) -> None:
    """Append an estimate outcome via the CLI."""
    run(
        "estimate-outcome",
        "--mission-dir", str(mission_dir),
        "--effect-id", effect_id,
        "--criterion-id", criterion_id,
        "--status", status,
        "--method", method,
        "--evidence", evidence,
        "--recorded-by", recorded_by,
    )


def create_completed_mission(
    cwd: Path,
    mission_id: str | None = None,
    outcome_achieved: bool = True,
    captains: list[str] | None = None,
    task_count: int = 1,
    station_tiers: list[int] | None = None,
    actual_outcome: str = "Mission completed",
    metric_result: str = "All tests pass",
    estimate_outcomes: list[dict] | None = None,
) -> Path:
    """Create a fully completed mission with all 4 JSON files.

    If *mission_id* is provided, the mission directory is renamed to that ID
    to allow deterministic test fixtures without timing issues.
    tmp_path isolation prevents rename collisions across tests.
    """
    mission_dir = init_mission(cwd)
    captain_specs = captains or ["HMS Argyll:frigate:sonnet:1"]
    add_squadron(mission_dir, captains=captain_specs)

    tiers = station_tiers or [0] * task_count
    for i in range(task_count):
        owner = captain_specs[i % len(captain_specs)].split(":")[0]
        tier = tiers[i] if i < len(tiers) else 0
        add_task(
            mission_dir,
            task_id=i + 1,
            name=f"Task {i + 1}",
            owner=owner,
            station_tier=tier,
        )

    run("plan-approved", "--mission-dir", str(mission_dir))

    if estimate_outcomes:
        for o in estimate_outcomes:
            record_estimate_outcome(mission_dir, **o)

    run(
        "checkpoint",
        "--mission-dir", str(mission_dir),
        "--pending", "0",
        "--in-progress", "0",
        "--completed", str(task_count),
        "--blocked", "0",
        "--tokens-spent", "50000",
        "--tokens-remaining", "50000",
        "--hull-green", str(len(captain_specs)),
        "--hull-amber", "0",
        "--hull-red", "0",
        "--hull-critical", "0",
        "--decision", "continue",
        "--rationale", "All good",
    )

    sd_args = [
        "stand-down",
        "--mission-dir", str(mission_dir),
        "--actual-outcome", actual_outcome,
        "--metric-result", metric_result,
    ]
    if outcome_achieved:
        sd_args.append("--outcome-achieved")
    run(*sd_args)

    if mission_id:
        target = mission_dir.parent / mission_id
        mission_dir.rename(target)
        return target
    return mission_dir
