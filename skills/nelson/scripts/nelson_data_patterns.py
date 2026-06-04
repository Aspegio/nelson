"""Darwin Gödel Machine inspired learned standing orders for Nelson.

Detects candidate standing orders from accumulated mission pattern data,
synthesizes them into Nelson-style prose, and manages the human review queue.

Pipeline:
1. Mine — cluster ``avoid`` text patterns from ``.nelson/memory/patterns.json``.
2. Score — Fisher's exact test for correlation with mission outcomes.
3. Filter — drop patterns similar to existing standing orders or previously
   dismissed.
4. Synthesize — FM-assisted prose generation (with heuristic-stub fallback).
5. Persist — append to ``.nelson/memory/candidate-standing-orders.json`` for
   human review.

Promotion writes a new ``.md`` file under
``skills/nelson/references/standing-orders/`` and adds a row to ``SKILL.md``.
Dismissal moves the entry to a dismissed archive so re-runs cannot
re-propose the same pattern.

Candidates may only ADD new standing orders, never modify or remove existing
ones — mitigates the objective-hacking failure mode documented in DGM
Appendix H (node 114 gamed the metric by deleting hallucination-detection
tokens).

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from hashlib import sha256
from math import exp, lgamma, log
from pathlib import Path

from nelson_data_utils import (
    _die,
    _err,
    _file_lock,
    _now_iso,
    _read_json_optional,
    _write_json,
)


def _write_text_atomic(path: Path, content: str) -> None:
    """Write text atomically via tempfile + os.replace.

    Matches the durability properties of ``_write_json`` for non-JSON files
    (SKILL.md, rendered standing orders) so a crash mid-write cannot leave a
    torn file behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:  # noqa: SIM105 -- nested cleanup; the outer raise dominates the control flow
            os.unlink(tmp)
        except OSError:
            pass
        raise


# Type alias for FM synthesis client. Receives a prompt, returns response text
# or ``None`` if the call could not be made (e.g. no client wired up).
FMClient = Callable[[str], "str | None"]


# ---------------------------------------------------------------------------
# Tunable defaults
# ---------------------------------------------------------------------------

DEFAULT_MIN_MISSIONS = 10
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_NOVELTY_THRESHOLD = 0.3  # = 1 - max token-containment to existing orders
DEFAULT_CLUSTER_SIMILARITY = 0.4  # Jaccard threshold for grouping avoid texts
DEFAULT_MAX_CANDIDATES_PER_RUN = 5


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawPattern:
    """A clustered group of avoid texts mined from mission patterns."""

    cluster_id: str
    canonical_text: str
    variants: tuple[str, ...]
    mission_ids: tuple[str, ...]


@dataclass(frozen=True)
class ScoredPattern:
    """A RawPattern with statistical scoring against mission outcomes."""

    raw: RawPattern
    total_missions: int
    missions_with: int
    missions_without: int
    successes_with: int
    failures_with: int
    successes_without: int
    failures_without: int
    p_value: float
    correlation: float  # log-odds ratio (positive = correlates with success)
    confidence: float
    frequency_score: float
    novelty: float = 1.0


@dataclass(frozen=True)
class Candidate:
    """A synthesized candidate standing order awaiting human review."""

    id: str
    title: str
    pattern_fingerprint: str
    trigger: str
    anti_pattern: str
    symptoms: tuple[str, ...]
    remedy: str
    related_orders: tuple[str, ...]
    evidence_mission_ids: tuple[str, ...]
    scores: dict
    created_at: str
    source: str

    @classmethod
    def from_dict(cls, d: dict) -> Candidate:
        return cls(
            id=d["id"],
            title=d.get("title", "untitled"),
            pattern_fingerprint=d.get("pattern_fingerprint", ""),
            trigger=d.get("trigger", ""),
            anti_pattern=d.get("anti_pattern", ""),
            symptoms=tuple(d.get("symptoms", [])),
            remedy=d.get("remedy", ""),
            related_orders=tuple(d.get("related_orders", [])),
            evidence_mission_ids=tuple(d.get("evidence_mission_ids", [])),
            scores=dict(d.get("scores", {})),
            created_at=d.get("created_at", ""),
            source=d.get("source", "unknown"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pattern_fingerprint": self.pattern_fingerprint,
            "trigger": self.trigger,
            "anti_pattern": self.anti_pattern,
            "symptoms": list(self.symptoms),
            "remedy": self.remedy,
            "related_orders": list(self.related_orders),
            "evidence_mission_ids": list(self.evidence_mission_ids),
            "scores": dict(self.scores),
            "created_at": self.created_at,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _default_missions_dir() -> Path:
    return Path(".nelson/missions")


def _default_memory_dir() -> Path:
    """Default memory dir derived the same way sibling modules derive theirs.

    Matches ``nelson_data_memory._resolve_memory_dir`` and ``cmd_brief``:
    ``{missions_dir}/../memory``. Without this consistency, ``detect-patterns``
    would write a queue that ``brief`` could not see under a non-default
    ``--missions-dir``.
    """
    return _default_missions_dir().parent / "memory"


def _default_standing_orders_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "standing-orders"


def _default_skill_md_path() -> Path:
    return Path(__file__).resolve().parent.parent / "SKILL.md"


# ---------------------------------------------------------------------------
# Tokenisation / similarity (used for clustering and novelty)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "that",
        "this",
        "these",
        "those",
        "have",
        "has",
        "had",
        "but",
        "not",
        "are",
        "was",
        "were",
        "their",
        "there",
        "what",
        "when",
        "which",
        "while",
        "where",
        "would",
        "could",
        "should",
        "will",
        "may",
        "can",
        "any",
        "all",
        "out",
        "too",
        "very",
        "just",
        "also",
        "only",
        "some",
        "such",
        "than",
        "then",
        "they",
        "you",
        "your",
        "our",
        "its",
        "his",
        "her",
    }
)


def _tokenize(text: str) -> set[str]:
    """Lowercase tokens of length >= 3, excluding common stopwords."""
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 3 and t not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _containment(small: set[str], large: set[str]) -> float:
    """Fraction of ``small`` covered by ``large``."""
    if not small:
        return 0.0
    return len(small & large) / len(small)


def _canonical_fingerprint(tokens: set[str]) -> str:
    """Stable 12-hex-char hash from a canonical token set.

    Sorting the tokens means re-runs that observe the same anti-pattern
    expressed differently still resolve to the same fingerprint.
    """
    canonical = "|".join(sorted(tokens))
    return sha256(canonical.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Stage 1: Mine event sequences
# ---------------------------------------------------------------------------


def _mine_event_sequences(  # noqa: C901, PLR0912 -- event-sequence miner with many state branches; refactor tracked in nelson-e6j
    patterns_data: dict,
    *,
    similarity_threshold: float = DEFAULT_CLUSTER_SIMILARITY,
) -> list[RawPattern]:
    """Cluster ``avoid`` texts across missions into recurring anti-patterns.

    Each cluster represents a free-text anti-pattern recorded at stand-down
    that has not yet been codified as a standing order. Near-duplicate
    phrasings are grouped using Jaccard token similarity so that
    "Spawning too many shells" and "Spawning many shells at once" collapse
    into the same cluster.

    The clusterer uses an order-independent union-find pass: every pair of
    inputs whose Jaccard similarity meets ``similarity_threshold`` ends up in
    the same cluster regardless of the order they were observed in.  This
    keeps the resulting ``cluster_id`` stable across reruns and across
    missions appended in different sequences — essential for the dismissed
    archive to keep working.
    """
    raw_inputs: list[tuple[str, str, frozenset[str]]] = []
    for p in patterns_data.get("patterns", []):
        mission_id = p.get("mission_id")
        if not mission_id:
            continue
        for text in p.get("avoid", []) or []:
            if not text:
                continue
            tokens = frozenset(_tokenize(text))
            if not tokens:
                continue
            raw_inputs.append((mission_id, text, tokens))

    if not raw_inputs:
        return []

    # Sort inputs deterministically so identical data always produces identical
    # cluster assignments.
    raw_inputs.sort(key=lambda r: (r[1], r[0]))

    # Union-find over input indices, joined when Jaccard >= threshold.
    parent = list(range(len(raw_inputs)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(len(raw_inputs)):
        for j in range(i + 1, len(raw_inputs)):
            if _jaccard(raw_inputs[i][2], raw_inputs[j][2]) >= similarity_threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(raw_inputs)):
        groups.setdefault(find(i), []).append(i)

    out: list[RawPattern] = []
    for indices in groups.values():
        members = [raw_inputs[i] for i in indices]
        all_tokens: set[str] = set()
        for _, _, toks in members:
            all_tokens |= toks
        variants = tuple(sorted({m[1] for m in members}))
        missions = tuple(sorted({m[0] for m in members}))
        # Canonical text is the shortest variant (ties broken alphabetically)
        # so re-runs always pick the same representative even if the order of
        # observation differs.
        canonical = min(variants, key=lambda v: (len(v), v))
        out.append(
            RawPattern(
                cluster_id=_canonical_fingerprint(all_tokens),
                canonical_text=canonical,
                variants=variants,
                mission_ids=missions,
            )
        )
    out.sort(key=lambda r: r.cluster_id)
    return out


# ---------------------------------------------------------------------------
# Stage 2: Score with Fisher's exact test
# ---------------------------------------------------------------------------


def _log_binom(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)


def _fisher_exact_pvalue(
    successes_with: int,
    failures_with: int,
    successes_without: int,
    failures_without: int,
) -> float:
    """Two-sided p-value for a 2x2 contingency table.

    Table layout::

                With pattern   Without pattern
        Success      a                 b
        Failure      c                 d

    Returns 1.0 when the table is degenerate (any margin is zero), which
    naturally pushes that pattern's confidence to 0 and filters it out.
    """
    a, b, c, d = successes_with, successes_without, failures_with, failures_without
    n = a + b + c + d
    if n == 0:
        return 1.0
    row1 = a + b  # successes_total
    col1 = a + c  # missions_with_pattern_total
    if row1 in (0, n) or col1 in (0, n):
        return 1.0

    log_denom = _log_binom(n, col1)
    log_p_obs = _log_binom(row1, a) + _log_binom(n - row1, c) - log_denom
    p_obs = exp(log_p_obs)

    total = 0.0
    extreme = 0.0
    k_min = max(0, col1 - (n - row1))
    k_max = min(row1, col1)
    for k in range(k_min, k_max + 1):
        log_p = _log_binom(row1, k) + _log_binom(n - row1, col1 - k) - log_denom
        p = exp(log_p)
        total += p
        if p <= p_obs * (1 + 1e-9):
            extreme += p
    if total <= 0:
        return 1.0
    return min(1.0, extreme / total)


def _log_odds_ratio(
    successes_with: int,
    failures_with: int,
    successes_without: int,
    failures_without: int,
) -> float:
    """Log-odds ratio with Haldane–Anscombe continuity correction.

    Positive values mean the pattern correlates with mission success;
    negative values mean it correlates with failure.  The +0.5 correction
    guarantees the ratio is finite and strictly positive even when any
    cell is zero, so the surrounding ``log`` is always defined.
    """
    a = successes_with + 0.5
    b = failures_with + 0.5
    c = successes_without + 0.5
    d = failures_without + 0.5
    return log((a * d) / (b * c))


def _score_pattern(raw: RawPattern, all_patterns: list[dict]) -> ScoredPattern:
    """Score a raw pattern by correlation with mission outcomes."""
    total = len(all_patterns)
    missions_with_set = set(raw.mission_ids)
    missions_with = len(missions_with_set)
    missions_without = total - missions_with

    successes_with = 0
    failures_with = 0
    successes_without = 0
    failures_without = 0
    for p in all_patterns:
        mission_id = p.get("mission_id")
        if not mission_id:
            continue
        achieved = bool(p.get("outcome_achieved"))
        if mission_id in missions_with_set:
            if achieved:
                successes_with += 1
            else:
                failures_with += 1
        elif achieved:
            successes_without += 1
        else:
            failures_without += 1

    p_value = _fisher_exact_pvalue(successes_with, failures_with, successes_without, failures_without)
    correlation = _log_odds_ratio(successes_with, failures_with, successes_without, failures_without)

    confidence = max(0.0, 1.0 - p_value)
    frequency = missions_with / total if total > 0 else 0.0

    return ScoredPattern(
        raw=raw,
        total_missions=total,
        missions_with=missions_with,
        missions_without=missions_without,
        successes_with=successes_with,
        failures_with=failures_with,
        successes_without=successes_without,
        failures_without=failures_without,
        p_value=p_value,
        correlation=correlation,
        confidence=confidence,
        frequency_score=frequency,
    )


def _correlate_with_outcomes(
    raw_patterns: list[RawPattern],
    all_patterns: list[dict],
) -> list[ScoredPattern]:
    """Score each raw pattern against mission outcomes."""
    return [_score_pattern(r, all_patterns) for r in raw_patterns]


# ---------------------------------------------------------------------------
# Stage 3: Novelty filter (drop patterns covered by existing orders)
# ---------------------------------------------------------------------------


def _load_existing_orders(
    standing_orders_dir: Path,
) -> list[tuple[str, str]]:
    """Return list of (filename_stem, full_text) for each .md in the directory."""
    if not standing_orders_dir.is_dir():
        return []
    out: list[tuple[str, str]] = []
    for path in sorted(standing_orders_dir.glob("*.md")):
        try:
            out.append((path.stem, path.read_text(encoding="utf-8")))
        except OSError as exc:
            _err(f"Warning: could not read {path}: {exc}")
    return out


def _novelty_score(
    raw: RawPattern,
    existing_orders: list[tuple[str, str]],
) -> float:
    """Return ``1 - max(token containment)`` against any existing order.

    Containment is the fraction of the pattern's tokens that appear in the
    order document.  A pattern whose tokens are entirely covered by an
    existing order yields novelty 0; a pattern with no token overlap yields
    novelty 1.  Containment is more appropriate than Jaccard for comparing
    short avoid-phrases against full standing-order documents.
    """
    pattern_tokens = _tokenize(raw.canonical_text)
    for v in raw.variants:
        pattern_tokens |= _tokenize(v)
    if not pattern_tokens:
        return 1.0

    max_containment = 0.0
    for name, content in existing_orders:
        order_tokens = _tokenize(name.replace("-", " ") + " " + content)
        c = _containment(pattern_tokens, order_tokens)
        max_containment = max(max_containment, c)
    return 1.0 - max_containment


# ---------------------------------------------------------------------------
# Stage 4: Synthesise (FM call with heuristic-stub fallback)
# ---------------------------------------------------------------------------


SYNTHESIS_PROMPT_TEMPLATE = """You are drafting a new Nelson Standing Order from observed mission data.

Style exemplar 1 (read first):
---
{exemplar1}
---

Style exemplar 2:
---
{exemplar2}
---

Detected anti-pattern (canonical phrasing): "{canonical}"

Variants across missions:
{variant_block}

Evidence: this pattern appeared in {missions_with} of {total_missions} missions.
Of those, {failures_with} failed and {successes_with} succeeded.
Statistical confidence: {confidence:.2f} (Fisher's exact, two-sided).
Log-odds ratio (positive = correlates with success): {correlation:.2f}.

Draft a new standing order in Nelson's style. Return ONLY a JSON object with this exact schema:
{{
  "title": "short kebab-case identifier (e.g. echoing-decks)",
  "trigger": "one sentence describing when this order applies",
  "anti_pattern": "one paragraph describing the anti-pattern (Royal Navy idiom welcome)",
  "symptoms": ["bullet describing a symptom", "another bullet", "..."],
  "remedy": "one paragraph remedy starting with an action verb",
  "related_orders": ["existing-order-slug", "..."]
}}

The title must be unique and not match any of the existing orders. No prose outside the JSON."""


def _build_synthesis_prompt(
    scored: ScoredPattern,
    existing: list[tuple[str, str]],
) -> str:
    """Build the FM synthesis prompt with two compact exemplars."""
    # Pick the two shortest standing orders as exemplars to keep prompt tight.
    exemplars = sorted(existing, key=lambda x: len(x[1]))[:2]
    e1 = exemplars[0][1] if exemplars else ""
    e2 = exemplars[1][1] if len(exemplars) > 1 else ""
    variant_lines = "\n".join(f'  - "{v}"' for v in scored.raw.variants[:5])
    return SYNTHESIS_PROMPT_TEMPLATE.format(
        canonical=scored.raw.canonical_text,
        variant_block=variant_lines,
        missions_with=scored.missions_with,
        total_missions=scored.total_missions,
        failures_with=scored.failures_with,
        successes_with=scored.successes_with,
        confidence=scored.confidence,
        correlation=scored.correlation,
        exemplar1=e1,
        exemplar2=e2,
    )


def _parse_fm_response(text: str) -> dict | None:
    """Parse FM JSON output, tolerating triple-fence wrappers."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _slugify(text: str) -> str:
    """Convert free text to a safe kebab-case slug."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:50] or "candidate-pattern"


def _heuristic_stub(scored: ScoredPattern) -> dict:
    """Fallback candidate fields when FM synthesis is unavailable or malformed.

    The fields are deliberately conservative — the candidate carries enough
    structure to be reviewed but flags itself as a stub via the ``source``
    field so reviewers know to flesh it out.
    """
    canonical = scored.raw.canonical_text
    slug = _slugify(canonical)
    return {
        "title": slug,
        "trigger": f"Conditions resembling: {canonical}.",
        "anti_pattern": (
            f"Recurring pattern '{canonical}' surfaced across "
            f"{scored.missions_with} of {scored.total_missions} missions but "
            f"is not yet codified as a standing order."
        ),
        "symptoms": list(scored.raw.variants[:5]),
        "remedy": (
            "Investigate this pattern manually and expand the trigger, "
            "anti-pattern, symptoms and remedy before promoting."
        ),
        "related_orders": [],
    }


def _synthesize_candidate(
    scored: ScoredPattern,
    existing: list[tuple[str, str]],
    fm_client: FMClient | None,
) -> Candidate:
    """Run FM synthesis (or fall back to heuristic stub) and return a Candidate."""
    data: dict | None = None
    source = "heuristic-stub"

    if fm_client is not None:
        prompt = _build_synthesis_prompt(scored, existing)
        try:
            response = fm_client(prompt)
        except Exception as exc:
            _err(f"FM synthesis raised {type(exc).__name__} for {scored.raw.cluster_id}: {exc}; using heuristic stub")
            response = None
        if response:
            data = _parse_fm_response(response)
            if data is None:
                _err(f"FM returned malformed output for {scored.raw.cluster_id}; using heuristic stub")
            else:
                source = "fm"

    if data is None:
        data = _heuristic_stub(scored)

    title = _slugify(str(data.get("title", "")) or _slugify(scored.raw.canonical_text))

    return Candidate(
        id=f"cand-{scored.raw.cluster_id}",
        title=title,
        pattern_fingerprint=scored.raw.cluster_id,
        trigger=str(data.get("trigger", "")).strip(),
        anti_pattern=str(data.get("anti_pattern", "")).strip(),
        symptoms=tuple(str(s).strip() for s in data.get("symptoms", []) if s),
        remedy=str(data.get("remedy", "")).strip(),
        related_orders=tuple(str(r).strip() for r in data.get("related_orders", []) if r),
        evidence_mission_ids=tuple(scored.raw.mission_ids),
        scores={
            "confidence": round(scored.confidence, 4),
            "novelty": round(scored.novelty, 4),
            "frequency": round(scored.frequency_score, 4),
            "correlation": round(scored.correlation, 4),
            "missions_with": scored.missions_with,
            "total_missions": scored.total_missions,
        },
        created_at=_now_iso(),
        source=source,
    )


# ---------------------------------------------------------------------------
# DGM-style ranking for the review queue
# ---------------------------------------------------------------------------


def _review_score(confidence: float, novelty: float) -> float:
    """DGM-style parent-selection score.

    ``confidence`` is already bounded to ``[0, 1]`` (it's ``1 - p_value``),
    so a sigmoid would only compress it into ``[0.5, 0.73]`` — too narrow
    to discriminate.  Multiplying directly by ``(1 + novelty)`` preserves
    the natural spread of confidence while still rewarding novel patterns
    as an exploration bonus (range ``[1, 2]``).
    """
    return confidence * (1.0 + novelty)


def rank_for_review(candidates: list[Candidate]) -> list[Candidate]:
    """Rank candidates so the highest-value reviews surface first.

    Score = confidence × (1 + novelty).  High confidence wins among
    candidates of similar novelty; high novelty acts as a tiebreaker so
    underexplored anti-patterns aren't buried beneath duplicates of
    near-existing orders.
    """

    def _key(c: Candidate) -> float:
        conf = float(c.scores.get("confidence", 0.0))
        nov = float(c.scores.get("novelty", 0.0))
        return -_review_score(conf, nov)

    return sorted(candidates, key=_key)


# ---------------------------------------------------------------------------
# Persistence — candidate queue and dismissed archive
# ---------------------------------------------------------------------------


def _candidates_path(memory_dir: Path) -> Path:
    return memory_dir / "candidate-standing-orders.json"


def _dismissed_path(memory_dir: Path) -> Path:
    return memory_dir / "dismissed-candidates.json"


def _load_candidates(path: Path) -> list[dict]:
    data = _read_json_optional(path)
    if data is None:
        return []
    return list(data.get("candidates", []))


def _save_candidates(path: Path, candidates: list[dict]) -> None:
    lock_path = path.with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(lock_path):
        _write_json(
            path,
            {
                "version": 1,
                "updated_at": _now_iso(),
                "candidate_count": len(candidates),
                "candidates": candidates,
            },
        )


def _load_dismissed(path: Path) -> list[dict]:
    data = _read_json_optional(path)
    if data is None:
        return []
    return list(data.get("dismissed", []))


def _save_dismissed(path: Path, dismissed: list[dict]) -> None:
    lock_path = path.with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(lock_path):
        _write_json(
            path,
            {
                "version": 1,
                "updated_at": _now_iso(),
                "dismissed_count": len(dismissed),
                "dismissed": dismissed,
            },
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_candidate_orders(  # noqa: PLR0913 -- public API; kwargs are CLI knobs (thresholds + max_candidates + injected FM client) with defaults. A DetectionConfig dataclass is the right refactor and is tracked in nelson-e6j.
    memory_dir: Path,
    *,
    standing_orders_dir: Path | None = None,
    min_missions: int = DEFAULT_MIN_MISSIONS,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    novelty_threshold: float = DEFAULT_NOVELTY_THRESHOLD,
    max_candidates: int = DEFAULT_MAX_CANDIDATES_PER_RUN,
    fm_client: FMClient | None = None,
) -> list[Candidate]:
    """Detect candidate standing orders from accumulated mission patterns.

    Pipeline: mine → score → filter (confidence + novelty + not-dismissed) →
    rank → synthesize top-N.  Returns the newly synthesized candidates;
    callers are responsible for merging with the existing queue and
    persisting.
    """
    if standing_orders_dir is None:
        standing_orders_dir = _default_standing_orders_dir()

    patterns_data = _read_json_optional(memory_dir / "patterns.json") or {}
    all_patterns = patterns_data.get("patterns", [])
    if len(all_patterns) < min_missions:
        return []

    existing_orders = _load_existing_orders(standing_orders_dir)
    dismissed = _load_dismissed(_dismissed_path(memory_dir))
    dismissed_fingerprints = {d.get("pattern_fingerprint") for d in dismissed if d.get("pattern_fingerprint")}

    raw_patterns = _mine_event_sequences(patterns_data)
    if not raw_patterns:
        return []

    scored: list[ScoredPattern] = []
    for raw in raw_patterns:
        if raw.cluster_id in dismissed_fingerprints:
            continue
        sp = _score_pattern(raw, all_patterns)
        sp = replace(sp, novelty=_novelty_score(raw, existing_orders))
        if sp.confidence < confidence_threshold:
            continue
        if sp.novelty < novelty_threshold:
            continue
        # Polarity guard: a standing order tells captains to AVOID the pattern,
        # so the pattern must correlate with failure (negative log-odds).
        # A success-correlated avoid-text passing this filter would surface a
        # candidate whose remedy is the inverse of what the data shows.
        if sp.correlation >= 0:
            continue
        scored.append(sp)

    # Pre-rank with the same heuristic the review queue uses, so synthesis
    # spends its FM budget on the most informative candidates first.
    scored.sort(key=lambda s: -_review_score(s.confidence, s.novelty))

    return [_synthesize_candidate(sp, existing_orders, fm_client) for sp in scored[:max_candidates]]


def promote_candidate(
    candidate_id: str,
    *,
    memory_dir: Path,
    standing_orders_dir: Path | None = None,
    skill_md_path: Path | None = None,
) -> Path:
    """Promote a candidate to a full standing order.

    Writes a new ``.md`` file under the standing-orders directory, appends a
    row to the SKILL.md lookup table, and removes the candidate from the
    pending queue.  Returns the path of the newly written file.

    Raises ``ValueError`` if the candidate is not found.  Raises
    ``FileExistsError`` if a standing order with the same title already
    exists (refuses to overwrite hand-written orders).
    """
    if standing_orders_dir is None:
        standing_orders_dir = _default_standing_orders_dir()
    if skill_md_path is None:
        skill_md_path = _default_skill_md_path()

    candidates_path = _candidates_path(memory_dir)
    candidates = _load_candidates(candidates_path)
    candidate = next((c for c in candidates if c.get("id") == candidate_id), None)
    if candidate is None:
        raise ValueError(f"Candidate {candidate_id!r} not found in queue")

    raw_title = candidate.get("title", "").strip()
    if not raw_title:
        raise ValueError(f"Candidate {candidate_id!r} has no title")
    # Re-slugify at the promotion boundary: the on-disk queue is data that may
    # have been hand-edited, so we cannot trust ``title`` to be a safe filename.
    # Without this, a title like "../../../tmp/pwn" would escape the
    # standing-orders directory.
    title = _slugify(raw_title)
    if title != raw_title:
        candidate = {**candidate, "title": title}

    standing_orders_dir.mkdir(parents=True, exist_ok=True)
    out_path = standing_orders_dir / f"{title}.md"
    if out_path.exists():
        raise FileExistsError(
            f"Standing order already exists at {out_path}; will not overwrite. "
            "Edit the candidate title to disambiguate."
        )

    # Pre-flight the SKILL.md edit before touching disk so a failed table
    # update doesn't leave an orphan .md alongside an unchanged SKILL.md.
    skill_md_lines = _prepare_skill_md_insertion(skill_md_path, candidate)

    _write_text_atomic(out_path, _render_standing_order(candidate))
    if skill_md_lines is not None:
        try:
            _write_text_atomic(skill_md_path, "\n".join(skill_md_lines))
        except Exception:
            # Roll back the standing-order .md so promote_candidate stays
            # transactional from the caller's perspective.
            try:  # noqa: SIM105 -- nested cleanup; the outer raise dominates the control flow
                out_path.unlink()
            except OSError:
                pass
            raise

    remaining = [c for c in candidates if c.get("id") != candidate_id]
    _save_candidates(candidates_path, remaining)
    return out_path


def dismiss_candidate(
    candidate_id: str,
    *,
    memory_dir: Path,
    reason: str,
) -> None:
    """Move a candidate from the pending queue to the dismissed archive.

    Subsequent ``detect_candidate_orders`` runs will not re-propose
    patterns with the same fingerprint — avoiding reviewer fatigue.
    """
    candidates_path = _candidates_path(memory_dir)
    dismissed_path = _dismissed_path(memory_dir)

    candidates = _load_candidates(candidates_path)
    candidate = next((c for c in candidates if c.get("id") == candidate_id), None)
    if candidate is None:
        raise ValueError(f"Candidate {candidate_id!r} not found in queue")

    dismissed = _load_dismissed(dismissed_path)
    dismissed.append(
        {
            "id": candidate_id,
            "reason": reason,
            "dismissed_at": _now_iso(),
            "pattern_fingerprint": candidate.get("pattern_fingerprint", ""),
            "title": candidate.get("title", ""),
        }
    )
    _save_dismissed(dismissed_path, dismissed)

    remaining = [c for c in candidates if c.get("id") != candidate_id]
    _save_candidates(candidates_path, remaining)


def count_pending_candidates(memory_dir: Path) -> int:
    """Return the number of candidates awaiting review."""
    return len(_load_candidates(_candidates_path(memory_dir)))


# ---------------------------------------------------------------------------
# Standing order rendering and SKILL.md update
# ---------------------------------------------------------------------------


_STANDING_ORDER_TEMPLATE = """# Standing Order: {title_human}

{anti_pattern}

**Trigger:** {trigger}

**Symptoms:**
{symptoms_block}

**Remedy:** {remedy}
{related_block}
<!-- audit-lineage: promoted from candidate {candidate_id}; evidence missions: {evidence} -->
"""


def _human_title(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("-") if w)


def _render_standing_order(candidate: dict) -> str:
    """Render a candidate dict as a standing-order .md document."""
    symptoms = candidate.get("symptoms") or []
    if symptoms:
        symptoms_block = "\n".join(f"- {s}" for s in symptoms)
    else:
        symptoms_block = "- (to be expanded by human reviewer before merge)"

    related = candidate.get("related_orders") or []
    if related:
        related_block = "\n**Related orders:** " + ", ".join(f"`{r}.md`" for r in related) + "\n"
    else:
        related_block = ""

    evidence_list = candidate.get("evidence_mission_ids") or []
    evidence = ", ".join(evidence_list) if evidence_list else "(none recorded)"

    return _STANDING_ORDER_TEMPLATE.format(
        title_human=_human_title(candidate.get("title", "Untitled")),
        anti_pattern=candidate.get("anti_pattern", "").strip()
        or "(no anti-pattern description supplied — expand before merge)",
        trigger=candidate.get("trigger", "").strip() or "(supply trigger)",
        symptoms_block=symptoms_block,
        remedy=candidate.get("remedy", "").strip() or "(supply remedy)",
        related_block=related_block,
        candidate_id=candidate.get("id", "unknown"),
        evidence=evidence,
    )


_SKILL_MD_SECTION_HEADING = "## Standing Orders"
_SKILL_MD_TABLE_ROW_RE = re.compile(
    r"^\|.*`references/standing-orders/[^`]+\.md`\s*\|\s*$",
)


def _sanitize_table_cell(text: str) -> str:
    """Render free-text safely into a single markdown table cell.

    Collapses any newline or carriage return into a space so that the cell
    cannot break out of its row and inject arbitrary markdown (headings,
    extra rows, prose) into SKILL.md.  Pipes are escaped so the cell does
    not split into multiple columns.
    """
    flattened = " ".join(text.split())  # collapses all whitespace incl. \n, \r, \t
    return flattened.replace("|", "\\|").strip()


def _prepare_skill_md_insertion(  # noqa: C901, PLR0912 -- skill.md insertion handler with many path branches; refactor tracked in nelson-e6j
    skill_md_path: Path,
    candidate: dict,
) -> list[str] | None:
    """Compute the SKILL.md line list with the new row inserted.

    Returns the new line list ready to be written, or ``None`` if no write is
    needed (row already present — idempotent re-promotion).

    Raises ``FileNotFoundError`` if SKILL.md is missing and ``ValueError`` if
    the Standing Orders table cannot be located inside the expected section.
    Pre-flighting the edit means ``promote_candidate`` does not write the
    standing order .md until we know the table mutation will succeed.
    """
    if not skill_md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found at {skill_md_path}; cannot update lookup table")

    text = skill_md_path.read_text(encoding="utf-8")
    title = candidate.get("title", "")
    target = f"`references/standing-orders/{title}.md`"
    if target in text:
        return None

    lines = text.split("\n")

    # Locate the "## Standing Orders" section so we never insert a row beneath
    # a similar-shape table elsewhere (e.g. Damage Control).
    section_start = -1
    section_end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == _SKILL_MD_SECTION_HEADING:
            section_start = i
            break
    if section_start == -1:
        raise ValueError(f"Could not locate '{_SKILL_MD_SECTION_HEADING}' heading in SKILL.md")
    for i in range(section_start + 1, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith("## "):
            section_end = i
            break

    last_row_idx = -1
    for i in range(section_start, section_end):
        if _SKILL_MD_TABLE_ROW_RE.match(lines[i]):
            last_row_idx = i
    if last_row_idx == -1:
        raise ValueError("Found Standing Orders heading but no lookup table rows below it")

    trigger = _sanitize_table_cell(candidate.get("trigger", ""))
    if not trigger:
        trigger = f"Auto-promoted candidate: {title}"
    new_row = f"| {trigger} | {target} |"
    new_lines = list(lines)
    new_lines.insert(last_row_idx + 1, new_row)
    return new_lines


# ---------------------------------------------------------------------------
# CLI handlers — wired into nelson-data.py
# ---------------------------------------------------------------------------


def _resolve_memory_dir(args: argparse.Namespace) -> Path:
    """Return the memory directory using the same rules as the rest of nelson-data.

    Precedence:
      1. ``--memory-dir`` if given explicitly.
      2. ``--missions-dir`` if given — derive ``{missions_dir}/../memory`` to
         match ``nelson_data_memory._resolve_memory_dir`` and ``cmd_brief``.
      3. Default to ``.nelson/missions/../memory``.

    Without this, ``detect-patterns`` and ``brief`` could disagree on where the
    candidate queue lives whenever the user runs Nelson outside the default
    ``.nelson/missions`` layout.
    """
    raw_memory = getattr(args, "memory_dir", None)
    if raw_memory:
        return Path(raw_memory)
    raw_missions = getattr(args, "missions_dir", None)
    if raw_missions:
        return Path(raw_missions).parent / "memory"
    return _default_memory_dir()


def cmd_detect_patterns(args: argparse.Namespace) -> None:
    """CLI: detect candidate standing orders and append them to the queue."""
    memory_dir = _resolve_memory_dir(args)
    standing_orders_dir = (
        Path(args.standing_orders_dir) if getattr(args, "standing_orders_dir", None) else _default_standing_orders_dir()
    )
    json_output = bool(getattr(args, "json_output", False))

    def _emit(status: str, detected: int, queue_size: int, message: str) -> None:
        if json_output:
            print(
                json.dumps(
                    {
                        "status": status,
                        "detected": detected,
                        "queue_size": queue_size,
                        "memory_dir": str(memory_dir),
                    },
                    indent=2,
                )
            )
        else:
            print(f"[nelson-data] {message}")

    if not (memory_dir / "patterns.json").exists():
        _emit(
            status="no-patterns",
            detected=0,
            queue_size=count_pending_candidates(memory_dir),
            message=(f"No patterns.json yet — nothing to detect. (Expected: {memory_dir / 'patterns.json'})"),
        )
        return

    new_candidates = detect_candidate_orders(
        memory_dir,
        standing_orders_dir=standing_orders_dir,
        min_missions=args.min_missions,
        confidence_threshold=args.confidence_threshold,
        fm_client=None,
    )

    existing_dicts = _load_candidates(_candidates_path(memory_dir))
    existing_fps = {c.get("pattern_fingerprint") for c in existing_dicts}

    appended: list[dict] = []
    for cand in new_candidates:
        if cand.pattern_fingerprint in existing_fps:
            continue
        appended.append(cand.to_dict())

    merged = existing_dicts + appended
    # Skip persistence if there's nothing on disk and nothing to add — avoids
    # littering the memory dir with empty queue files on first-runs.
    if not merged and not _candidates_path(memory_dir).exists():
        _emit(
            status="ok",
            detected=len(appended),
            queue_size=0,
            message=f"Detected {len(appended)} new candidate(s); queue is empty.",
        )
        return

    # Re-rank the whole queue so the highest-priority items surface first.
    ranked = [c.to_dict() for c in rank_for_review([Candidate.from_dict(c) for c in merged])]
    _save_candidates(_candidates_path(memory_dir), ranked)

    _emit(
        status="ok",
        detected=len(appended),
        queue_size=len(ranked),
        message=(f"Detected {len(appended)} new candidate(s); queue size: {len(ranked)}"),
    )


def cmd_promote_candidate(args: argparse.Namespace) -> None:
    """CLI: promote a candidate to a real standing order."""
    memory_dir = _resolve_memory_dir(args)
    try:
        out_path = promote_candidate(args.candidate_id, memory_dir=memory_dir)
    except (ValueError, FileExistsError) as exc:
        _die(f"Error: {exc}")
        return
    print(f"[nelson-data] Promoted {args.candidate_id} -> {out_path}")


def cmd_dismiss_candidate(args: argparse.Namespace) -> None:
    """CLI: dismiss a candidate with a reason."""
    memory_dir = _resolve_memory_dir(args)
    try:
        dismiss_candidate(
            args.candidate_id,
            memory_dir=memory_dir,
            reason=args.reason,
        )
    except ValueError as exc:
        _die(f"Error: {exc}")
        return
    print(f"[nelson-data] Dismissed {args.candidate_id}: {args.reason}")
