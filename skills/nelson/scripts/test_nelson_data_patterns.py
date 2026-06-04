"""Tests for the DGM-inspired learned standing orders pipeline.

Covers:
- Synthetic-data detection: planted anti-pattern surfaces with high confidence.
- Edge cases: empty / single-mission / all-success / all-failure data sets.
- Novelty filter: patterns covered by existing orders are dropped.
- Dismissed archive: re-running detection does not re-surface a dismissed pattern.
- Promotion: writes a well-formed .md and updates the SKILL.md lookup table.
- rank_for_review ordering: confidence × novelty (DGM parent-selection style).
- CLI smoke: detect-patterns reports gracefully on empty memory; promote /
  dismiss handlers fail with a clear error when the candidate is unknown.
- Brief surfacing: the candidate count appears when present and is omitted
  cleanly when zero.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import read_json, run
from nelson_data_patterns import (
    Candidate,
    _fisher_exact_pvalue,
    _heuristic_stub,
    _mine_event_sequences,
    _novelty_score,
    _parse_fm_response,
    _prepare_skill_md_insertion,
    _sanitize_table_cell,
    _score_pattern,
    count_pending_candidates,
    detect_candidate_orders,
    dismiss_candidate,
    promote_candidate,
    rank_for_review,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


PLANTED = "Spawning too many shells without coordination plan"


def _make_patterns_file(
    memory_dir: Path,
    *,
    with_pattern_failing: int,
    without_pattern_succeeding: int,
    extra_noise_avoid: list[str] | None = None,
) -> None:
    """Write a synthetic patterns.json into *memory_dir*.

    The planted pattern PLANTED appears in `with_pattern_failing` missions,
    all of which failed.  Another `without_pattern_succeeding` missions
    succeeded without the pattern.  Together they form a strong negative
    correlation that Fisher's exact will detect with high confidence.
    """
    patterns = []
    counter = 0
    for _ in range(with_pattern_failing):
        counter += 1
        patterns.append(
            {
                "mission_id": f"2026-01-01_{counter:06d}",
                "outcome_achieved": False,
                "adopt": [],
                "avoid": [PLANTED, *(extra_noise_avoid or [])],
                "standing_order_violations": [],
                "damage_control_events": 0,
            }
        )
    for _ in range(without_pattern_succeeding):
        counter += 1
        patterns.append(
            {
                "mission_id": f"2026-01-01_{counter:06d}",
                "outcome_achieved": True,
                "adopt": ["Clean dispatch"],
                "avoid": [],
                "standing_order_violations": [],
                "damage_control_events": 0,
            }
        )
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "patterns.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-01-02T00:00:00Z",
                "pattern_count": len(patterns),
                "patterns": patterns,
            }
        ),
        encoding="utf-8",
    )


def _empty_standing_orders_dir(tmp_path: Path) -> Path:
    so_dir = tmp_path / "standing-orders"
    so_dir.mkdir()
    return so_dir


# ---------------------------------------------------------------------------
# Statistical primitives
# ---------------------------------------------------------------------------


class TestFisherExact:
    def test_strong_signal_low_pvalue(self) -> None:
        # 4 failures all have the pattern; 8 successes never do
        p = _fisher_exact_pvalue(0, 8, 4, 0)
        assert p < 0.01

    def test_no_signal_high_pvalue(self) -> None:
        # Pattern equally distributed across successes and failures
        p = _fisher_exact_pvalue(4, 4, 4, 4)
        assert p > 0.5

    def test_degenerate_table_returns_one(self) -> None:
        assert _fisher_exact_pvalue(0, 0, 0, 0) == 1.0
        assert _fisher_exact_pvalue(0, 0, 5, 5) == 1.0  # all in one row


# ---------------------------------------------------------------------------
# Mining (clustering) and scoring
# ---------------------------------------------------------------------------


class TestMining:
    def test_groups_near_duplicates(self) -> None:
        data = {
            "patterns": [
                {"mission_id": "m1", "avoid": ["Spawning many shells at once"]},
                {"mission_id": "m2", "avoid": ["Spawning too many shells without plan"]},
                {"mission_id": "m3", "avoid": ["Forgot to ration tokens"]},
            ]
        }
        clusters = _mine_event_sequences(data, similarity_threshold=0.3)
        # The two "shell" phrases should cluster; the token-ration phrase stands alone
        shell_clusters = [c for c in clusters if "shells" in c.canonical_text.lower()]
        assert len(shell_clusters) == 1
        assert len(shell_clusters[0].mission_ids) == 2

    def test_empty_input_yields_no_clusters(self) -> None:
        assert _mine_event_sequences({}) == []
        assert _mine_event_sequences({"patterns": []}) == []

    def test_blank_avoid_text_skipped(self) -> None:
        data = {"patterns": [{"mission_id": "m1", "avoid": ["", "   "]}]}
        assert _mine_event_sequences(data) == []


class TestScoring:
    def test_correlated_pattern_high_confidence(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        patterns_data = json.loads((memory_dir / "patterns.json").read_text(encoding="utf-8"))
        clusters = _mine_event_sequences(patterns_data)
        assert len(clusters) == 1, f"Expected one cluster, got {len(clusters)}"
        scored = _score_pattern(clusters[0], patterns_data["patterns"])
        assert scored.missions_with == 4
        assert scored.failures_with == 4
        assert scored.successes_with == 0
        assert scored.confidence > 0.95, f"Expected high confidence, got {scored.confidence}"


# ---------------------------------------------------------------------------
# Novelty
# ---------------------------------------------------------------------------


class TestNovelty:
    def test_pattern_covered_by_existing_order_is_low_novelty(self, tmp_path: Path) -> None:
        so_dir = _empty_standing_orders_dir(tmp_path)
        (so_dir / "split-keel.md").write_text(
            "# Standing Order: Split Keel\n\n"
            "Do not assign the same file to multiple captains.\n\n"
            "**Symptoms:** captains overwrite each other; merge conflicts on the "
            "same artifact; coordination time reconciling divergent edits.\n",
            encoding="utf-8",
        )
        data = {
            "patterns": [
                {
                    "mission_id": "m1",
                    "avoid": ["captains overwrite same artifact merge conflicts"],
                }
            ]
        }
        clusters = _mine_event_sequences(data)
        existing = [(p.stem, p.read_text(encoding="utf-8")) for p in so_dir.glob("*.md")]
        novelty = _novelty_score(clusters[0], existing)
        assert novelty < 0.3, f"Expected low novelty for known pattern, got {novelty}"

    def test_unrelated_pattern_is_high_novelty(self, tmp_path: Path) -> None:
        so_dir = _empty_standing_orders_dir(tmp_path)
        (so_dir / "split-keel.md").write_text("# Split Keel — file ownership\n", encoding="utf-8")
        data = {"patterns": [{"mission_id": "m1", "avoid": [PLANTED]}]}
        clusters = _mine_event_sequences(data)
        existing = [(p.stem, p.read_text(encoding="utf-8")) for p in so_dir.glob("*.md")]
        novelty = _novelty_score(clusters[0], existing)
        assert novelty > 0.5


# ---------------------------------------------------------------------------
# End-to-end detection
# ---------------------------------------------------------------------------


class TestDetectCandidateOrders:
    def test_planted_pattern_is_detected(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)

        candidates = detect_candidate_orders(
            memory_dir,
            standing_orders_dir=so_dir,
            min_missions=10,
            confidence_threshold=0.7,
        )
        assert len(candidates) == 1
        cand = candidates[0]
        assert cand.scores["confidence"] > 0.7
        assert cand.evidence_mission_ids  # mission lineage carried through

    def test_below_min_missions_returns_nothing(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=2, without_pattern_succeeding=3)
        so_dir = _empty_standing_orders_dir(tmp_path)
        assert detect_candidate_orders(memory_dir, standing_orders_dir=so_dir, min_missions=10) == []

    def test_empty_memory_returns_nothing(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "patterns.json").write_text('{"patterns": []}', encoding="utf-8")
        so_dir = _empty_standing_orders_dir(tmp_path)
        assert detect_candidate_orders(memory_dir, standing_orders_dir=so_dir, min_missions=0) == []

    def test_all_success_returns_nothing(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=0, without_pattern_succeeding=12)
        so_dir = _empty_standing_orders_dir(tmp_path)
        # No failures at all → no anti-pattern is correlated with failure
        assert detect_candidate_orders(memory_dir, standing_orders_dir=so_dir, min_missions=10) == []

    def test_pattern_matching_existing_order_dropped(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        # Plant a pattern whose tokens are fully covered by the existing order
        (so_dir / "split-keel.md").write_text(
            "# Split Keel\nfile captain assignment overwrite merge conflict ownership\n",
            encoding="utf-8",
        )

        patterns = []
        for i in range(4):
            patterns.append(
                {
                    "mission_id": f"m{i}",
                    "outcome_achieved": False,
                    "avoid": ["file captain assignment overwrite ownership"],
                    "adopt": [],
                    "standing_order_violations": [],
                    "damage_control_events": 0,
                }
            )
        for i in range(8):
            patterns.append(
                {
                    "mission_id": f"n{i}",
                    "outcome_achieved": True,
                    "avoid": [],
                    "adopt": [],
                    "standing_order_violations": [],
                    "damage_control_events": 0,
                }
            )
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "patterns.json").write_text(
            json.dumps({"version": 1, "pattern_count": 12, "patterns": patterns}),
            encoding="utf-8",
        )

        candidates = detect_candidate_orders(
            memory_dir,
            standing_orders_dir=so_dir,
            min_missions=10,
        )
        assert candidates == [], "Existing-order coverage should suppress the candidate"

    def test_dismissed_pattern_not_resurfaced(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)

        first = detect_candidate_orders(memory_dir, standing_orders_dir=so_dir, min_missions=10)
        assert len(first) == 1
        cand = first[0]

        # Persist the candidate so dismiss_candidate can find it
        queue_path = memory_dir / "candidate-standing-orders.json"
        queue_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "updated_at": "2026-01-02T00:00:00Z",
                    "candidate_count": 1,
                    "candidates": [cand.to_dict()],
                }
            ),
            encoding="utf-8",
        )

        dismiss_candidate(cand.id, memory_dir=memory_dir, reason="duplicate")
        assert detect_candidate_orders(memory_dir, standing_orders_dir=so_dir, min_missions=10) == []


# ---------------------------------------------------------------------------
# Synthesis (with and without an FM client)
# ---------------------------------------------------------------------------


class TestSynthesis:
    def test_heuristic_stub_used_when_no_fm(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)

        candidates = detect_candidate_orders(memory_dir, standing_orders_dir=so_dir, min_missions=10, fm_client=None)
        assert candidates[0].source == "heuristic-stub"
        assert candidates[0].title  # slug derived from canonical text

    def test_fm_client_supplies_prose(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)

        def fake_fm(prompt: str) -> str:
            return json.dumps(
                {
                    "title": "shell-spawning",
                    "trigger": "When the captain proposes more than 3 parallel shells.",
                    "anti_pattern": "Shells without a coordination plan.",
                    "symptoms": ["High shell count", "Tokens consumed coordinating shells"],
                    "remedy": "Consolidate shell work into a single dispatch.",
                    "related_orders": ["light-squadron"],
                }
            )

        candidates = detect_candidate_orders(
            memory_dir,
            standing_orders_dir=so_dir,
            min_missions=10,
            fm_client=fake_fm,
        )
        assert candidates[0].source == "fm"
        assert candidates[0].title == "shell-spawning"
        assert candidates[0].remedy

    def test_fm_malformed_falls_back_to_stub(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)

        def bad_fm(prompt: str) -> str:
            return "not valid JSON at all"

        candidates = detect_candidate_orders(
            memory_dir,
            standing_orders_dir=so_dir,
            min_missions=10,
            fm_client=bad_fm,
        )
        assert candidates[0].source == "heuristic-stub"

    def test_fm_exception_falls_back_to_stub(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)

        def crashing_fm(prompt: str) -> str:
            raise RuntimeError("FM down")

        candidates = detect_candidate_orders(
            memory_dir,
            standing_orders_dir=so_dir,
            min_missions=10,
            fm_client=crashing_fm,
        )
        assert candidates[0].source == "heuristic-stub"

    def test_parse_fm_response_strips_fences(self) -> None:
        fenced = '```json\n{"title": "foo"}\n```'
        parsed = _parse_fm_response(fenced)
        assert parsed == {"title": "foo"}

    def test_heuristic_stub_carries_evidence(self) -> None:
        from nelson_data_patterns import RawPattern, ScoredPattern

        raw = RawPattern(
            cluster_id="abc123",
            canonical_text="planted text",
            variants=("planted text",),
            mission_ids=("m1", "m2"),
        )
        sp = ScoredPattern(
            raw=raw,
            total_missions=10,
            missions_with=2,
            missions_without=8,
            successes_with=0,
            failures_with=2,
            successes_without=8,
            failures_without=0,
            p_value=0.02,
            correlation=-2.0,
            confidence=0.98,
            frequency_score=0.2,
        )
        stub = _heuristic_stub(sp)
        assert "planted text" in stub["anti_pattern"]
        assert stub["title"]


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    def test_high_confidence_high_novelty_ranks_first(self) -> None:
        a = Candidate.from_dict(
            {
                "id": "cand-a",
                "title": "a",
                "pattern_fingerprint": "a",
                "scores": {"confidence": 0.95, "novelty": 0.9},
            }
        )
        b = Candidate.from_dict(
            {
                "id": "cand-b",
                "title": "b",
                "pattern_fingerprint": "b",
                "scores": {"confidence": 0.95, "novelty": 0.1},
            }
        )
        c = Candidate.from_dict(
            {
                "id": "cand-c",
                "title": "c",
                "pattern_fingerprint": "c",
                "scores": {"confidence": 0.3, "novelty": 0.9},
            }
        )
        ranked = rank_for_review([b, c, a])
        # a (high conf, high nov) > b (high conf, low nov) > c (low conf, high nov)
        assert [r.id for r in ranked] == ["cand-a", "cand-b", "cand-c"]


# ---------------------------------------------------------------------------
# Promotion and dismissal
# ---------------------------------------------------------------------------


def _seed_candidate(memory_dir: Path, candidate: Candidate) -> None:
    memory_dir.mkdir(parents=True, exist_ok=True)
    queue_path = memory_dir / "candidate-standing-orders.json"
    queue_path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-01-02T00:00:00Z",
                "candidate_count": 1,
                "candidates": [candidate.to_dict()],
            }
        ),
        encoding="utf-8",
    )


def _make_candidate(**overrides) -> Candidate:
    base = {
        "id": "cand-test123",
        "title": "echoing-decks",
        "pattern_fingerprint": "test123",
        "trigger": "When the admiral repeats orders rather than issuing fresh ones.",
        "anti_pattern": ("The admiral re-issues the same brief rather than diagnosing why the first dispatch failed."),
        "symptoms": ["Same brief dispatched twice", "Captain reports no progress"],
        "remedy": "Diagnose first; only re-dispatch with a fixed brief.",
        "related_orders": ["pulling-the-oar"],
        "evidence_mission_ids": ["2026-01-01_000001", "2026-01-01_000002"],
        "scores": {"confidence": 0.95, "novelty": 0.8},
        "created_at": "2026-01-02T00:00:00Z",
        "source": "fm",
    }
    base.update(overrides)
    return Candidate.from_dict(base)


class TestPromotion:
    def test_promote_writes_well_formed_md(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n"
            "|---|---|\n"
            "| Existing | `references/standing-orders/split-keel.md` |\n",
            encoding="utf-8",
        )
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)

        out_path = promote_candidate(
            cand.id,
            memory_dir=memory_dir,
            standing_orders_dir=so_dir,
            skill_md_path=skill_md,
        )
        assert out_path == so_dir / "echoing-decks.md"
        text = out_path.read_text(encoding="utf-8")
        assert "# Standing Order: Echoing Decks" in text
        assert "**Trigger:**" in text
        assert "**Symptoms:**" in text
        assert "**Remedy:**" in text
        assert "audit-lineage" in text
        assert "2026-01-01_000001" in text

    def test_promote_updates_skill_md_table(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n"
            "|---|---|\n"
            "| Existing | `references/standing-orders/split-keel.md` |\n",
            encoding="utf-8",
        )
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)

        promote_candidate(
            cand.id,
            memory_dir=memory_dir,
            standing_orders_dir=so_dir,
            skill_md_path=skill_md,
        )
        updated = skill_md.read_text(encoding="utf-8")
        assert "`references/standing-orders/echoing-decks.md`" in updated

    def test_promote_removes_from_queue(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n|---|---|\n"
            "| Existing | `references/standing-orders/split-keel.md` |\n",
            encoding="utf-8",
        )
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)

        promote_candidate(
            cand.id,
            memory_dir=memory_dir,
            standing_orders_dir=so_dir,
            skill_md_path=skill_md,
        )
        assert count_pending_candidates(memory_dir) == 0

    def test_promote_refuses_overwrite(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n|---|---|\n"
            "| Existing | `references/standing-orders/split-keel.md` |\n",
            encoding="utf-8",
        )
        # Pre-existing hand-written order
        (so_dir / "echoing-decks.md").write_text("hand-written", encoding="utf-8")
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)

        try:
            promote_candidate(
                cand.id,
                memory_dir=memory_dir,
                standing_orders_dir=so_dir,
                skill_md_path=skill_md,
            )
        except FileExistsError:
            pass
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected FileExistsError")
        # Hand-written content preserved
        assert (so_dir / "echoing-decks.md").read_text(encoding="utf-8") == "hand-written"

    def test_promote_unknown_candidate_raises(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        try:
            promote_candidate(
                "cand-missing",
                memory_dir=memory_dir,
                standing_orders_dir=_empty_standing_orders_dir(tmp_path),
                skill_md_path=tmp_path / "SKILL.md",
            )
        except ValueError as exc:
            assert "cand-missing" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected ValueError")


class TestDismissal:
    def test_dismiss_archives_candidate(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)

        dismiss_candidate(cand.id, memory_dir=memory_dir, reason="too vague")
        archive = json.loads((memory_dir / "dismissed-candidates.json").read_text(encoding="utf-8"))
        assert archive["dismissed_count"] == 1
        assert archive["dismissed"][0]["pattern_fingerprint"] == cand.pattern_fingerprint
        assert archive["dismissed"][0]["reason"] == "too vague"
        assert count_pending_candidates(memory_dir) == 0

    def test_dismiss_unknown_candidate_raises(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        try:
            dismiss_candidate("cand-missing", memory_dir=memory_dir, reason="x")
        except ValueError as exc:
            assert "cand-missing" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected ValueError")


# ---------------------------------------------------------------------------
# CLI smoke tests (subprocess)
# ---------------------------------------------------------------------------


class TestCLI:
    def test_detect_patterns_empty_memory(self, tmp_path: Path) -> None:
        result = run(
            "detect-patterns",
            "--memory-dir",
            str(tmp_path / ".nelson" / "memory"),
            cwd=tmp_path,
        )
        assert "No patterns.json" in result.stdout

    def test_detect_patterns_synthetic_dataset(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / ".nelson" / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)

        result = run(
            "detect-patterns",
            "--memory-dir",
            str(memory_dir),
            "--standing-orders-dir",
            str(so_dir),
            "--min-missions",
            "10",
            "--confidence-threshold",
            "0.7",
            cwd=tmp_path,
        )
        assert "Detected 1 new candidate" in result.stdout
        queue = read_json(memory_dir / "candidate-standing-orders.json")
        assert queue["candidate_count"] == 1

    def test_dismiss_then_redetect_excludes_candidate(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / ".nelson" / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)

        run(
            "detect-patterns",
            "--memory-dir",
            str(memory_dir),
            "--standing-orders-dir",
            str(so_dir),
            "--min-missions",
            "10",
            cwd=tmp_path,
        )
        queue = read_json(memory_dir / "candidate-standing-orders.json")
        cid = queue["candidates"][0]["id"]

        run(
            "dismiss-candidate",
            "--candidate-id",
            cid,
            "--reason",
            "duplicate of split-keel",
            "--memory-dir",
            str(memory_dir),
            cwd=tmp_path,
        )
        result = run(
            "detect-patterns",
            "--memory-dir",
            str(memory_dir),
            "--standing-orders-dir",
            str(so_dir),
            "--min-missions",
            "10",
            cwd=tmp_path,
        )
        assert "Detected 0 new candidate" in result.stdout

    def test_promote_unknown_candidate_exits_nonzero(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / ".nelson" / "memory"
        memory_dir.mkdir(parents=True)
        run(
            "promote-candidate",
            "--candidate-id",
            "cand-missing",
            "--memory-dir",
            str(memory_dir),
            cwd=tmp_path,
            expect_fail=True,
        )


# ---------------------------------------------------------------------------
# Intelligence brief surfacing
# ---------------------------------------------------------------------------


class TestBriefSurfacing:
    def test_brief_omits_line_when_zero_candidates(self, tmp_path: Path) -> None:
        # Build an index from a single completed mission so the brief has body
        from conftest import create_completed_mission

        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        run(
            "index",
            "--missions-dir",
            str(tmp_path / ".nelson" / "missions"),
            cwd=tmp_path,
        )
        result = run("brief", "--missions-dir", str(tmp_path / ".nelson" / "missions"), cwd=tmp_path)
        assert "CANDIDATE STANDING ORDERS" not in result.stdout

    def test_brief_includes_line_when_candidate_present(self, tmp_path: Path) -> None:
        from conftest import create_completed_mission

        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        run(
            "index",
            "--missions-dir",
            str(tmp_path / ".nelson" / "missions"),
            cwd=tmp_path,
        )
        memory_dir = tmp_path / ".nelson" / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)

        result = run("brief", "--missions-dir", str(tmp_path / ".nelson" / "missions"), cwd=tmp_path)
        assert "CANDIDATE STANDING ORDERS (awaiting review): 1" in result.stdout


# ---------------------------------------------------------------------------
# Regressions surfaced by PR review (#120)
# ---------------------------------------------------------------------------


class TestClusterStability:
    """Cluster fingerprint must be invariant under input order.

    Documented contract at module line 211: "re-runs that observe the same
    anti-pattern expressed differently still resolve to the same fingerprint."
    """

    def _data(self, ordering: list[str]) -> dict:
        # Three avoid texts where the middle one bridges the other two — under
        # the old greedy clusterer, this collapsed to one cluster or two
        # depending on the order observed.
        bank = {
            "a": "shells coordination parallel spawn",
            "b": "shells coordination",
            "c": "parallel spawn workflow",
        }
        return {"patterns": [{"mission_id": f"m-{k}", "avoid": [bank[k]]} for k in ordering]}

    def test_cluster_id_invariant_under_reordering(self) -> None:
        order1 = _mine_event_sequences(self._data(["a", "b", "c"]))
        order2 = _mine_event_sequences(self._data(["c", "b", "a"]))
        order3 = _mine_event_sequences(self._data(["b", "a", "c"]))
        ids1 = sorted(c.cluster_id for c in order1)
        ids2 = sorted(c.cluster_id for c in order2)
        ids3 = sorted(c.cluster_id for c in order3)
        assert ids1 == ids2 == ids3, f"Cluster IDs diverged under reordering: {ids1} vs {ids2} vs {ids3}"

    def test_bridge_pattern_groups_consistently(self) -> None:
        # The bridge text "b" must connect "a" and "c" regardless of order.
        order1 = _mine_event_sequences(self._data(["a", "b", "c"]))
        order2 = _mine_event_sequences(self._data(["c", "b", "a"]))
        assert len(order1) == len(order2)


class TestPolarityGate:
    """Standing orders are 'avoid this' — the candidate gate must require
    that the pattern correlate with failure (negative log-odds)."""

    def test_success_correlated_avoid_text_is_filtered_out(self, tmp_path: Path) -> None:
        # Build a synthetic dataset where the avoid-text only appears in
        # SUCCESSFUL missions.  Old impl: confidence 0.998 → candidate surfaces.
        # New impl: correlation > 0 → filtered out at the gate.
        memory_dir = tmp_path / "memory"
        patterns: list[dict] = []
        for i in range(8):
            patterns.append(
                {
                    "mission_id": f"win-{i}",
                    "outcome_achieved": True,
                    "avoid": ["wardroom timetable was burned"],
                    "adopt": [],
                    "standing_order_violations": [],
                    "damage_control_events": 0,
                }
            )
        for i in range(4):
            patterns.append(
                {
                    "mission_id": f"loss-{i}",
                    "outcome_achieved": False,
                    "avoid": [],
                    "adopt": [],
                    "standing_order_violations": [],
                    "damage_control_events": 0,
                }
            )
        memory_dir.mkdir(parents=True)
        (memory_dir / "patterns.json").write_text(
            json.dumps({"version": 1, "pattern_count": len(patterns), "patterns": patterns}),
            encoding="utf-8",
        )

        candidates = detect_candidate_orders(
            memory_dir,
            standing_orders_dir=_empty_standing_orders_dir(tmp_path),
            min_missions=10,
        )
        assert candidates == [], (
            "Success-correlated avoid texts must not surface as anti-pattern candidates; remedy would invert the data."
        )


class TestPathTraversalGuard:
    def test_promote_rejects_title_with_path_traversal(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n|---|---|\n"
            "| Existing | `references/standing-orders/split-keel.md` |\n",
            encoding="utf-8",
        )
        cand = _make_candidate(title="../../../tmp/pwn", id="cand-evil")
        _seed_candidate(memory_dir, cand)

        out_path = promote_candidate(
            cand.id,
            memory_dir=memory_dir,
            standing_orders_dir=so_dir,
            skill_md_path=skill_md,
        )
        # The slug rewrite forces the new file under so_dir, not /tmp.
        assert out_path.parent == so_dir
        assert ".." not in out_path.name
        assert "/" not in out_path.name
        # And nothing escaped the standing-orders directory.
        outside_files = list(tmp_path.glob("**/pwn.md"))
        assert outside_files in ([out_path], [])


class TestSkillMdInjectionGuard:
    def test_newline_in_trigger_is_neutralised(self) -> None:
        evil = "step one\n## OVERRIDE\n| evil | row |"
        cleaned = _sanitize_table_cell(evil)
        assert "\n" not in cleaned
        assert "##" in cleaned  # text is preserved as a single line
        # And pipe escaping survives the flatten
        assert "\\|" in cleaned

    def test_promote_inserts_into_standing_orders_section_only(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        # Damage Control table appears BEFORE Standing Orders.  Old impl would
        # take the last table-shape line in the entire file as anchor; new impl
        # must insert beneath Standing Orders specifically.
        skill_md.write_text(
            "## Damage Control\n\n"
            "| Situation | Procedure |\n|---|---|\n"
            "| Other | `references/standing-orders/decoy.md` |\n\n"
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n|---|---|\n"
            "| Existing | `references/standing-orders/split-keel.md` |\n\n"
            "## Trailing section\n",
            encoding="utf-8",
        )
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)
        promote_candidate(
            cand.id,
            memory_dir=memory_dir,
            standing_orders_dir=so_dir,
            skill_md_path=skill_md,
        )
        text = skill_md.read_text(encoding="utf-8")
        # New row appears below the Standing Orders heading, above Trailing
        so_idx = text.index("## Standing Orders")
        trailing_idx = text.index("## Trailing section")
        new_row_idx = text.index("echoing-decks.md")
        assert so_idx < new_row_idx < trailing_idx


class TestPromoteIdempotency:
    def test_promote_then_promote_again_is_clean(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n|---|---|\n"
            "| Existing | `references/standing-orders/split-keel.md` |\n",
            encoding="utf-8",
        )
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)
        promote_candidate(
            cand.id,
            memory_dir=memory_dir,
            standing_orders_dir=so_dir,
            skill_md_path=skill_md,
        )
        # Same row shouldn't appear twice if pre-insertion is called twice.
        text_after_first = skill_md.read_text(encoding="utf-8")
        # Manually re-run the SKILL.md preparation for the same candidate to
        # confirm idempotency on the table mutation path.
        result = _prepare_skill_md_insertion(skill_md, cand.to_dict())
        assert result is None  # already present → no-op
        assert text_after_first.count("`references/standing-orders/echoing-decks.md`") == 1

    def test_promote_missing_skill_md_raises_before_writing_md(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)
        # No SKILL.md on disk → must fail before writing the standing order .md
        try:
            promote_candidate(
                cand.id,
                memory_dir=memory_dir,
                standing_orders_dir=so_dir,
                skill_md_path=tmp_path / "SKILL.md",
            )
        except FileNotFoundError:
            pass
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected FileNotFoundError")
        assert not (so_dir / "echoing-decks.md").exists()

    def test_promote_table_missing_aborts_atomically(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        # Heading present but no table beneath it.
        skill_md.write_text(
            "# Skill\n\n## Standing Orders\n\nNo table here.\n",
            encoding="utf-8",
        )
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)
        try:
            promote_candidate(
                cand.id,
                memory_dir=memory_dir,
                standing_orders_dir=so_dir,
                skill_md_path=skill_md,
            )
        except ValueError:
            pass
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected ValueError when table missing")
        # Neither file should have been mutated.
        assert not (so_dir / "echoing-decks.md").exists()
        assert "echoing-decks" not in skill_md.read_text(encoding="utf-8")
        # Candidate still in queue — no partial commit.
        assert count_pending_candidates(memory_dir) == 1


class TestAddOnlyInvariant:
    """The headline DGM safety claim: candidates may ADD standing orders but
    never modify or delete existing ones (DGM Appendix H mitigation)."""

    def test_existing_standing_orders_files_are_untouched_after_promote(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        existing_path = so_dir / "split-keel.md"
        existing_content = "# Split Keel\n\nHand-written, must not change.\n"
        existing_path.write_text(existing_content, encoding="utf-8")
        another_path = so_dir / "becalmed-fleet.md"
        another_content = "# Becalmed Fleet\n\nAlso hand-written.\n"
        another_path.write_text(another_content, encoding="utf-8")

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n|---|---|\n"
            "| Split keel | `references/standing-orders/split-keel.md` |\n"
            "| Becalmed | `references/standing-orders/becalmed-fleet.md` |\n",
            encoding="utf-8",
        )
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)

        promote_candidate(
            cand.id,
            memory_dir=memory_dir,
            standing_orders_dir=so_dir,
            skill_md_path=skill_md,
        )
        # Existing files are byte-identical
        assert existing_path.read_text(encoding="utf-8") == existing_content
        assert another_path.read_text(encoding="utf-8") == another_content
        # New file is the only addition
        new_files = sorted(p.name for p in so_dir.glob("*.md"))
        assert new_files == ["becalmed-fleet.md", "echoing-decks.md", "split-keel.md"]

    def test_existing_skill_md_rows_are_preserved(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        so_dir = _empty_standing_orders_dir(tmp_path)
        skill_md = tmp_path / "SKILL.md"
        original = (
            "## Standing Orders\n\n"
            "| Situation | Standing Order |\n|---|---|\n"
            "| Split keel | `references/standing-orders/split-keel.md` |\n"
            "| Becalmed | `references/standing-orders/becalmed-fleet.md` |\n"
        )
        skill_md.write_text(original, encoding="utf-8")
        cand = _make_candidate()
        _seed_candidate(memory_dir, cand)
        promote_candidate(
            cand.id,
            memory_dir=memory_dir,
            standing_orders_dir=so_dir,
            skill_md_path=skill_md,
        )
        updated = skill_md.read_text(encoding="utf-8")
        # Every original row still present, byte for byte.
        for line in original.split("\n"):
            assert line in updated


class TestEmptyQueueSkipsWrite:
    def test_detect_patterns_does_not_create_empty_queue_on_first_run(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / ".nelson" / "memory"
        # patterns.json exists but has no failure correlation → 0 candidates.
        _make_patterns_file(memory_dir, with_pattern_failing=0, without_pattern_succeeding=12)
        so_dir = _empty_standing_orders_dir(tmp_path)
        run(
            "detect-patterns",
            "--memory-dir",
            str(memory_dir),
            "--standing-orders-dir",
            str(so_dir),
            "--min-missions",
            "10",
            cwd=tmp_path,
        )
        queue_path = memory_dir / "candidate-standing-orders.json"
        assert not queue_path.exists(), "First-run with no candidates must not litter the memory dir."


class TestMissionDirDerivation:
    """detect-patterns and brief must read the same memory dir when given the
    same --missions-dir, even when it is not the default location."""

    def test_detect_patterns_with_missions_dir_finds_queue_seen_by_brief(self, tmp_path: Path) -> None:
        # Non-default layout: project_root/.nelson/missions and memory siblings
        missions_dir = tmp_path / "project" / ".nelson" / "missions"
        missions_dir.mkdir(parents=True)
        memory_dir = missions_dir.parent / "memory"  # The derived path
        memory_dir.mkdir()

        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)
        # Run from a CWD that is NOT the project root — old impl would use
        # cwd-relative .nelson/memory and miss the queue entirely.
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        result = run(
            "detect-patterns",
            "--missions-dir",
            str(missions_dir),
            "--standing-orders-dir",
            str(so_dir),
            "--min-missions",
            "10",
            cwd=elsewhere,
        )
        assert "Detected 1 new candidate" in result.stdout
        # Queue must land where brief will look for it.
        assert (memory_dir / "candidate-standing-orders.json").exists()


class TestMalformedRecordTolerance:
    def test_missing_mission_id_is_skipped_not_raised(self) -> None:
        # Old impl: KeyError on the first record without "mission_id".
        data = {
            "patterns": [
                {"avoid": ["something"], "outcome_achieved": False},  # no id
                {"mission_id": "m1", "avoid": ["other"], "outcome_achieved": True},
            ]
        }
        clusters = _mine_event_sequences(data)
        # The bad record was skipped silently; the good one survives.
        assert any("other" in c.canonical_text for c in clusters)


class TestDetectPatternsJsonOutput:
    def test_json_flag_emits_machine_readable_summary(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / ".nelson" / "memory"
        _make_patterns_file(memory_dir, with_pattern_failing=4, without_pattern_succeeding=8)
        so_dir = _empty_standing_orders_dir(tmp_path)
        result = run(
            "detect-patterns",
            "--memory-dir",
            str(memory_dir),
            "--standing-orders-dir",
            str(so_dir),
            "--min-missions",
            "10",
            "--json",
            cwd=tmp_path,
        )
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["detected"] == 1
        assert payload["queue_size"] == 1
