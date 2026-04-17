# Nelson Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six independent issues identified in the Nelson codebase review (broken import, stale marketplace version, missing CI coverage, untested utility, empty templates, stale README text) and ship them as a single PR.

**Architecture:** Six independent fixes grouped into logical tasks. Simple edits first (version, README, template cleanup), then file moves (conflict_radar relocation), then new tests (count-tokens), then CI update to exercise the newly testable root `scripts/` directory. Each task ends with a commit so history reads as discrete fixes.

**Tech Stack:** Python 3.12+ (stdlib only), pytest, GitHub Actions CI, bash, Markdown.

**Beads issues closed by this plan:** `nelson-qns`, `nelson-76d`, `nelson-2q9`, `nelson-339`, `nelson-2a2`, `nelson-zlf`

**Working directory:** `/Users/harry/Workspace/nelson/.claude/worktrees/gifted-jemison` (worktree on branch `main`).

---

## Pre-flight

### Task 0: Create feature branch

**Files:**
- None (git branch operation only)

- [ ] **Step 1: Create and switch to a new branch for the PR**

Run:
```bash
cd /Users/harry/Workspace/nelson/.claude/worktrees/gifted-jemison
git checkout -b fix/review-findings-2026-04
```

Expected: `Switched to a new branch 'fix/review-findings-2026-04'`

- [ ] **Step 2: Claim the six beads issues**

Run:
```bash
bd update nelson-qns --claim
bd update nelson-76d --claim
bd update nelson-2q9 --claim
bd update nelson-339 --claim
bd update nelson-2a2 --claim
bd update nelson-zlf --claim
```

Expected: each prints `✓ Updated …`.

---

## Task 1: Bump marketplace.json version (closes nelson-76d)

**Files:**
- Modify: `.claude-plugin/marketplace.json:13`

- [ ] **Step 1: Edit the version field**

Change line 13 of `.claude-plugin/marketplace.json` from:
```json
      "version": "2.1.0",
```
to:
```json
      "version": "2.1.1",
```

- [ ] **Step 2: Verify both version fields agree**

Run:
```bash
grep -n '"version"' .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Expected:
```
.claude-plugin/plugin.json:4:  "version": "2.1.1",
.claude-plugin/marketplace.json:13:      "version": "2.1.1",
```

- [ ] **Step 3: Commit**

Run:
```bash
git add .claude-plugin/marketplace.json
git commit -m "fix: sync marketplace.json version to 2.1.1

plugin.json was bumped to 2.1.1 but marketplace.json was missed.
Closes nelson-76d."
```

---

## Task 2: Refresh README evergreen reference (closes nelson-zlf)

**Files:**
- Modify: `README.md:76`

- [ ] **Step 1: Update the self-coordination line**

Change line 76 of `README.md` from:
```markdown
Nelson coordinates its own development — the v1.7.0 release was planned and executed as a Nelson mission.
```
to:
```markdown
Nelson coordinates its own development — recent releases have been planned and executed as Nelson missions.
```

- [ ] **Step 2: Verify the change**

Run:
```bash
grep -n "coordinates its own development" README.md
```

Expected:
```
76:Nelson coordinates its own development — recent releases have been planned and executed as Nelson missions.
```

- [ ] **Step 3: Commit**

Run:
```bash
git add README.md
git commit -m "docs: make self-coordination line evergreen

The README pinned to v1.7.0, which makes the project look stale
now that 2.1.1 is out. Generalise to 'recent releases'.
Closes nelson-zlf."
```

---

## Task 3: Remove empty codemap.md templates (closes nelson-2a2)

**Files:**
- Delete: `agents/codemap.md`
- Delete: `codemap.md`
- Delete: `demos/battleships/codemap.md`
- Delete: `demos/battleships/js/codemap.md`
- Delete: `demos/battleships/styles/codemap.md`
- Delete: `demos/codemap.md`
- Delete: `docs/codemap.md`
- Delete: `scripts/codemap.md`
- Delete: `skills/codemap.md`
- Delete: `skills/nelson/codemap.md`
- Delete: `skills/nelson/scripts/codemap.md`

- [ ] **Step 1: Confirm all 11 templates are identical empty scaffolds**

Run:
```bash
md5 agents/codemap.md codemap.md demos/battleships/codemap.md \
    demos/battleships/js/codemap.md demos/battleships/styles/codemap.md \
    demos/codemap.md docs/codemap.md scripts/codemap.md skills/codemap.md \
    skills/nelson/codemap.md skills/nelson/scripts/codemap.md
```

Expected: all 11 hashes identical (they are empty placeholders from the codemap agent).

If any hash differs, STOP and inspect that file — it has been populated and must not be deleted. Skip populated files from the deletion list below.

- [ ] **Step 2: Delete all 11 template files via git**

Run:
```bash
git rm \
  agents/codemap.md \
  codemap.md \
  demos/battleships/codemap.md \
  demos/battleships/js/codemap.md \
  demos/battleships/styles/codemap.md \
  demos/codemap.md \
  docs/codemap.md \
  scripts/codemap.md \
  skills/codemap.md \
  skills/nelson/codemap.md \
  skills/nelson/scripts/codemap.md
```

Expected: 11 `rm` lines in output.

- [ ] **Step 3: Verify no doc references to the deleted templates remain**

Run:
```bash
grep -rn "codemap\.md" skills/ README.md CLAUDE.md 2>/dev/null
```

Expected: no output (empty result). The review already confirmed no references exist.

If output appears, STOP and remove each reference before committing.

- [ ] **Step 4: Commit**

Run:
```bash
git commit -m "chore: remove empty codemap.md templates

11 identical empty scaffolds were committed across the repo. The
codemap agent regenerates these on demand, so they add noise with
no value. Removed. If someone runs the codemap agent and wants the
output tracked, they can commit the populated file then.
Closes nelson-2a2."
```

---

## Task 4: Relocate conflict_radar to fix broken import (closes nelson-qns)

**Context:** `scripts/nelson_conflict_radar.py` imports `from nelson_conflict_scan import parse_battle_plan`, but `nelson_conflict_scan.py` lives in `skills/nelson/scripts/`. Moving the radar (plus its test) to the same directory fixes the import and colocates related scripts.

**Files:**
- Delete: `scripts/nelson_conflict_radar.py`
- Delete: `scripts/test_nelson_conflict_radar.py`
- Create: `skills/nelson/scripts/nelson_conflict_radar.py` (moved)
- Create: `skills/nelson/scripts/test_nelson_conflict_radar.py` (moved)
- Modify: `skills/nelson/scripts/nelson_conflict_radar.py` docstring (paths)
- Modify: `README.md:202` and `README.md:523`

- [ ] **Step 1: Move the script and its test with `git mv`**

Run:
```bash
git mv scripts/nelson_conflict_radar.py skills/nelson/scripts/nelson_conflict_radar.py
git mv scripts/test_nelson_conflict_radar.py skills/nelson/scripts/test_nelson_conflict_radar.py
```

Expected: two `rename` entries when you `git status`.

- [ ] **Step 2: Update in-file path references in the moved script**

Edit `skills/nelson/scripts/nelson_conflict_radar.py`. Replace the two docstring path references:

Change:
```
  python3 scripts/nelson_conflict_radar.py --plan .nelson/missions/<your-mission-dir>/battle-plan.md
```
to:
```
  python3 skills/nelson/scripts/nelson_conflict_radar.py --plan .nelson/missions/<your-mission-dir>/battle-plan.md
```

And change:
```
    if [ -d .nelson/missions ]; then python3 scripts/nelson_conflict_radar.py --plan <path>; fi
```
to:
```
    if [ -d .nelson/missions ]; then python3 skills/nelson/scripts/nelson_conflict_radar.py --plan <path>; fi
```

- [ ] **Step 3a: Move the radar entry in the README tree diagram**

Edit `README.md`. In the file-structure tree block (lines 509–524), the radar currently sits at the bottom of the root-level `scripts/` subtree. It needs to move next to `nelson_conflict_scan.py` in the `skills/nelson/scripts/` subtree.

Change this fragment:
```
    ├── nelson_conflict_scan.py               # Pre-flight split-keel scanner
    ├── nelson-phase.py                       # Deterministic phase engine
    └── test_*.py                             # Test suite (pytest)
agents/
└── nelson.md                                 # Agent definition with skill binding
scripts/
├── check-references.sh                       # Cross-reference validation for documentation links
├── count-tokens.py                           # Token counter for hull integrity monitoring
└── nelson_conflict_radar.py                  # Runtime file-conflict monitor
```
to:
```
    ├── nelson_conflict_scan.py               # Pre-flight split-keel scanner
    ├── nelson_conflict_radar.py              # Runtime file-conflict monitor
    ├── nelson-phase.py                       # Deterministic phase engine
    └── test_*.py                             # Test suite (pytest)
agents/
└── nelson.md                                 # Agent definition with skill binding
scripts/
├── check-references.sh                       # Cross-reference validation for documentation links
└── count-tokens.py                           # Token counter for hull integrity monitoring
```

- [ ] **Step 3b: Update the prose explanation that lists root-level utilities**

On line 533 (the bullet beginning `skills/nelson/scripts/` ships…), change:
```markdown
- `skills/nelson/scripts/` ships `nelson-data.py` and its sibling modules alongside the skill so they are distributed on install. The root-level `scripts/` directory holds repo-level utilities (`count-tokens.py`, `check-references.sh`, runtime conflict radar).
```
to:
```markdown
- `skills/nelson/scripts/` ships `nelson-data.py` and its sibling modules (including the conflict radar and pre-flight conflict scanner) alongside the skill so they are distributed on install. The root-level `scripts/` directory holds repo-level utilities (`count-tokens.py`, `check-references.sh`).
```

Line 202 (the prose bullet that names the radar) still applies unchanged — it references the filename without a path prefix, so the move does not invalidate it.

- [ ] **Step 4: Run the relocated test to confirm the import now resolves**

Run:
```bash
python3 -m pytest skills/nelson/scripts/test_nelson_conflict_radar.py -v
```

Expected: all 13 tests PASS (the tests were green when run from the right cwd before; the move makes them green from any cwd).

- [ ] **Step 5: Run the full skill test suite to confirm no regressions**

Run:
```bash
python3 -m pytest skills/nelson/scripts/ -v 2>&1 | tail -5
```

Expected: `231 passed` (218 previous + 13 relocated).

- [ ] **Step 6: Commit**

Run:
```bash
git add -A
git commit -m "fix: move nelson_conflict_radar.py next to its dependency

The script imported nelson_conflict_scan, which lives in
skills/nelson/scripts/. Running the tests from the root scripts/
directory raised ModuleNotFoundError because that directory never
had conflict_scan alongside it.

Moves both the script and its test into skills/nelson/scripts/,
updates the in-file docstring paths and README path references.
Closes nelson-qns."
```

---

## Task 5: Write tests for count-tokens.py (closes nelson-339)

**Context:** `scripts/count-tokens.py` has four pure functions and one orchestrator (`main`) that is driven by argparse and subprocess-friendly CLI. The file name uses a hyphen, so import it via `importlib.util` from the file path. Tests go next to it in `scripts/`.

**Files:**
- Create: `scripts/conftest.py` (helper to import hyphenated module)
- Create: `scripts/test_count_tokens.py`

- [ ] **Step 1: Write the conftest that loads the hyphenated module**

Create `scripts/conftest.py` with content:

```python
"""Shared test helpers for scripts/ tests.

Provides a pytest fixture that loads count-tokens.py by file path,
since the hyphenated filename blocks ordinary `import count_tokens`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT_PATH = Path(__file__).parent / "count-tokens.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("count_tokens", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def count_tokens():
    """Load count-tokens.py as an importable module."""
    return _load()
```

- [ ] **Step 2: Write the failing test file**

Create `scripts/test_count_tokens.py` with content:

```python
"""Tests for count-tokens.py — token counting and damage reports."""

from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# count_tokens_from_jsonl
# ---------------------------------------------------------------------------


class TestCountTokensFromJsonl:
    def test_returns_none_when_no_assistant_turns(self, tmp_path: Path, count_tokens):
        path = tmp_path / "session.jsonl"
        path.write_text(
            '{"type":"user","message":{"content":"hi"}}\n',
            encoding="utf-8",
        )
        assert count_tokens.count_tokens_from_jsonl(path) is None

    def test_returns_none_on_empty_file(self, tmp_path: Path, count_tokens):
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert count_tokens.count_tokens_from_jsonl(path) is None

    def test_sums_last_assistant_usage(self, tmp_path: Path, count_tokens):
        lines = [
            {"type": "user", "message": {"content": "a"}},
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 100,
                        "cache_creation_input_tokens": 10,
                        "cache_read_input_tokens": 5,
                        "output_tokens": 42,
                    }
                },
            },
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 200,
                        "cache_creation_input_tokens": 20,
                        "cache_read_input_tokens": 30,
                        "output_tokens": 7,
                    }
                },
            },
        ]
        path = tmp_path / "session.jsonl"
        path.write_text(
            "\n".join(json.dumps(line) for line in lines) + "\n",
            encoding="utf-8",
        )
        # uses the LAST usage record, sums the three input-side fields,
        # ignoring output_tokens
        assert count_tokens.count_tokens_from_jsonl(path) == 250

    def test_skips_malformed_json_lines(self, tmp_path: Path, count_tokens):
        path = tmp_path / "session.jsonl"
        path.write_text(
            "not json\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "usage": {
                            "input_tokens": 1,
                            "cache_creation_input_tokens": 2,
                            "cache_read_input_tokens": 3,
                            "output_tokens": 4,
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert count_tokens.count_tokens_from_jsonl(path) == 6

    def test_skips_assistant_records_without_usage(self, tmp_path: Path, count_tokens):
        path = tmp_path / "session.jsonl"
        path.write_text(
            json.dumps({"type": "assistant", "message": {"content": "no usage"}})
            + "\n",
            encoding="utf-8",
        )
        assert count_tokens.count_tokens_from_jsonl(path) is None

    def test_treats_missing_usage_fields_as_zero(self, tmp_path: Path, count_tokens):
        path = tmp_path / "session.jsonl"
        path.write_text(
            json.dumps(
                {"type": "assistant", "message": {"usage": {"input_tokens": 50}}}
            )
            + "\n",
            encoding="utf-8",
        )
        assert count_tokens.count_tokens_from_jsonl(path) == 50


# ---------------------------------------------------------------------------
# count_tokens_heuristic
# ---------------------------------------------------------------------------


class TestCountTokensHeuristic:
    def test_char_count_divided_by_four(self, tmp_path: Path, count_tokens):
        path = tmp_path / "plain.txt"
        path.write_text("a" * 40, encoding="utf-8")
        assert count_tokens.count_tokens_heuristic(path) == 10

    def test_rounds_down(self, tmp_path: Path, count_tokens):
        path = tmp_path / "plain.txt"
        path.write_text("a" * 7, encoding="utf-8")  # 7 // 4 == 1
        assert count_tokens.count_tokens_heuristic(path) == 1

    def test_empty_file_is_zero(self, tmp_path: Path, count_tokens):
        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")
        assert count_tokens.count_tokens_heuristic(path) == 0


# ---------------------------------------------------------------------------
# hull_integrity_status
# ---------------------------------------------------------------------------


class TestHullIntegrityStatus:
    def test_green_at_or_above_75(self, count_tokens):
        assert count_tokens.hull_integrity_status(100) == "Green"
        assert count_tokens.hull_integrity_status(75) == "Green"

    def test_amber_between_60_and_74(self, count_tokens):
        assert count_tokens.hull_integrity_status(74) == "Amber"
        assert count_tokens.hull_integrity_status(60) == "Amber"

    def test_red_between_40_and_59(self, count_tokens):
        assert count_tokens.hull_integrity_status(59) == "Red"
        assert count_tokens.hull_integrity_status(40) == "Red"

    def test_critical_below_40(self, count_tokens):
        assert count_tokens.hull_integrity_status(39) == "Critical"
        assert count_tokens.hull_integrity_status(0) == "Critical"


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------


class TestBuildReport:
    def test_green_status_does_not_request_relief(self, count_tokens):
        report = count_tokens.build_report(
            "HMS Victory", 50_000, 200_000, "jsonl_usage"
        )
        assert report["ship_name"] == "HMS Victory"
        assert report["token_count"] == 50_000
        assert report["token_limit"] == 200_000
        assert report["hull_integrity_pct"] == 75
        assert report["hull_integrity_status"] == "Green"
        assert report["relief_requested"] is False
        assert report["method"] == "jsonl_usage"
        # timestamp is present and ISO-8601-ish
        assert "T" in report["timestamp"]

    def test_red_status_requests_relief(self, count_tokens):
        report = count_tokens.build_report("HMS Kent", 130_000, 200_000, "heuristic")
        assert report["hull_integrity_pct"] == 35
        assert report["hull_integrity_status"] == "Critical"
        assert report["relief_requested"] is True

    def test_zero_limit_yields_zero_pct(self, count_tokens):
        report = count_tokens.build_report("HMS Edge", 100, 0, "heuristic")
        assert report["hull_integrity_pct"] == 0
        assert report["hull_integrity_status"] == "Critical"

    def test_count_exceeding_limit_clamps_to_zero_remaining(self, count_tokens):
        report = count_tokens.build_report("HMS Overrun", 300_000, 200_000, "jsonl_usage")
        assert report["hull_integrity_pct"] == 0
        assert report["hull_integrity_status"] == "Critical"
        assert report["relief_requested"] is True


# ---------------------------------------------------------------------------
# scan_squadron
# ---------------------------------------------------------------------------


class TestScanSquadron:
    def _write_assistant_jsonl(self, path: Path, input_tokens: int) -> None:
        path.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "usage": {
                            "input_tokens": input_tokens,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 0,
                            "output_tokens": 0,
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_flagship_only(self, tmp_path: Path, count_tokens):
        session_dir = tmp_path / "session-abc"
        session_dir.mkdir()
        flagship = tmp_path / "session-abc.jsonl"
        self._write_assistant_jsonl(flagship, 100)

        reports = count_tokens.scan_squadron(str(session_dir), 200_000)

        assert len(reports) == 1
        assert reports[0]["ship_name"] == "Flagship"
        assert reports[0]["token_count"] == 100

    def test_flagship_and_subagents(self, tmp_path: Path, count_tokens):
        session_dir = tmp_path / "session-xyz"
        (session_dir / "subagents").mkdir(parents=True)
        flagship = tmp_path / "session-xyz.jsonl"
        self._write_assistant_jsonl(flagship, 50)
        self._write_assistant_jsonl(
            session_dir / "subagents" / "agent-first.jsonl", 77
        )
        self._write_assistant_jsonl(
            session_dir / "subagents" / "agent-second.jsonl", 99
        )

        reports = count_tokens.scan_squadron(str(session_dir), 200_000)
        ships = [r["ship_name"] for r in reports]

        assert "Flagship" in ships
        assert "agent-first" in ships
        assert "agent-second" in ships
        assert len(reports) == 3

    def test_missing_flagship_and_subagents_returns_empty(
        self, tmp_path: Path, count_tokens
    ):
        session_dir = tmp_path / "session-empty"
        session_dir.mkdir()
        assert count_tokens.scan_squadron(str(session_dir), 200_000) == []

    def test_trailing_slash_on_session_dir_is_handled(
        self, tmp_path: Path, count_tokens
    ):
        session_dir = tmp_path / "session-slash"
        session_dir.mkdir()
        self._write_assistant_jsonl(tmp_path / "session-slash.jsonl", 25)

        reports = count_tokens.scan_squadron(str(session_dir) + "/", 200_000)

        assert len(reports) == 1
        assert reports[0]["token_count"] == 25
```

- [ ] **Step 3: Run the new tests to confirm they pass**

Run:
```bash
python3 -m pytest scripts/ -v
```

Expected: every test PASSES (approximately 20 tests across the five classes).

If a test fails, fix the test (not the tested code — it is existing behaviour to be exercised, not improved).

- [ ] **Step 4: Confirm nothing else regressed**

Run:
```bash
python3 -m pytest skills/nelson/scripts/ hooks/ scripts/ 2>&1 | tail -5
```

Expected: all tests pass, totalling at least `283 passed` (231 skill + 52 hook + ~20 scripts).

- [ ] **Step 5: Commit**

Run:
```bash
git add scripts/conftest.py scripts/test_count_tokens.py
git commit -m "test: add unit tests for scripts/count-tokens.py

Adds a conftest.py that loads count-tokens.py via importlib (the
hyphenated filename blocks ordinary imports) and a test file
covering count_tokens_from_jsonl, count_tokens_heuristic,
hull_integrity_status, build_report, and scan_squadron.

Tests exercise existing behaviour only; no source changes.
Closes nelson-339."
```

---

## Task 6: Wire root `scripts/` into CI (closes nelson-2q9)

**Files:**
- Modify: `.github/workflows/ci.yml:64`

- [ ] **Step 1: Extend the test command to include scripts/**

Edit `.github/workflows/ci.yml`. Change line 64 from:
```yaml
      - run: pytest skills/nelson/scripts/ -v && pytest hooks/ -v
```
to:
```yaml
      - run: pytest skills/nelson/scripts/ -v && pytest hooks/ -v && pytest scripts/ -v
```

- [ ] **Step 2: Dry-run the composed pytest locally**

Run:
```bash
python3 -m pytest skills/nelson/scripts/ -v && python3 -m pytest hooks/ -v && python3 -m pytest scripts/ -v
```

Expected: the full composed command exits 0 with three separate test-suite runs. This mirrors what CI will execute.

- [ ] **Step 3: Commit**

Run:
```bash
git add .github/workflows/ci.yml
git commit -m "ci: run tests in scripts/ directory

The root scripts/ directory is now covered by tests (see
scripts/test_count_tokens.py and the relocated conflict_radar
tests). Wire it into the CI test job so regressions are caught.
Closes nelson-2q9."
```

---

## Finalisation

### Task 7: Push branch and open PR

**Files:**
- None (git + gh CLI operations)

- [ ] **Step 1: Confirm working tree is clean and branch diverges cleanly from main**

Run:
```bash
git status
git log --oneline main..HEAD
```

Expected: working tree clean, 6 commits on the branch (one per task).

- [ ] **Step 2: Run the full test suite one last time before push**

Run:
```bash
python3 -m pytest skills/nelson/scripts/ -v && \
  python3 -m pytest hooks/ -v && \
  python3 -m pytest scripts/ -v && \
  bash scripts/check-references.sh
```

Expected: all three pytest suites pass and the cross-reference check reports `OK: All cross-references are valid`.

- [ ] **Step 3: Push the branch**

Run:
```bash
git push -u origin fix/review-findings-2026-04
```

Expected: branch published, upstream set.

- [ ] **Step 4: Create the PR with a combined body**

Run:
```bash
gh pr create --title "fix: six findings from codebase review (#nelson-qns, -76d, -2q9, -339, -2a2, -zlf)" --body "$(cat <<'EOF'
## Summary

Fixes six issues found during a general review of the Nelson codebase that were not already tracked in GitHub issues.

- **Broken import** — `scripts/nelson_conflict_radar.py` imported `nelson_conflict_scan` from the wrong directory; tests failed with `ModuleNotFoundError`. Moved the radar (and its test) next to `nelson_conflict_scan.py` in `skills/nelson/scripts/`.
- **Marketplace version** — `marketplace.json` was still declaring `2.1.0` while `plugin.json` was at `2.1.1`. Synced.
- **CI test gap** — CI only ran `skills/nelson/scripts/` and `hooks/`. Root `scripts/` tests (previously broken, now working) were never exercised. Added `pytest scripts/` to the CI job.
- **Untested utility** — `scripts/count-tokens.py` had 228 lines and zero tests. Added `scripts/conftest.py` (importlib loader for the hyphenated filename) and `scripts/test_count_tokens.py` covering all five public functions.
- **Empty templates** — 11 identical empty `codemap.md` scaffolds committed across the repo. Removed; the codemap agent regenerates them on demand.
- **Stale README** — the self-coordination line pinned to v1.7.0; rewritten to be evergreen.

Closes beads: `nelson-qns`, `nelson-76d`, `nelson-2q9`, `nelson-339`, `nelson-2a2`, `nelson-zlf`.

## Test plan

- [x] `pytest skills/nelson/scripts/ -v` passes (231 tests)
- [x] `pytest hooks/ -v` passes (52 tests)
- [x] `pytest scripts/ -v` passes (new, ~20 + 13 relocated tests)
- [x] `bash scripts/check-references.sh` reports all cross-references valid
- [x] `grep '"version"' .claude-plugin/plugin.json .claude-plugin/marketplace.json` shows 2.1.1 in both
- [x] README no longer mentions v1.7.0 in the self-coordination line
- [x] `find . -name codemap.md -not -path './.claude/*'` prints nothing
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 5: Close all six beads issues**

Run:
```bash
bd close nelson-qns nelson-76d nelson-2q9 nelson-339 nelson-2a2 nelson-zlf
```

Expected: six `✓ Closed` lines.
