#!/usr/bin/env python3
"""
Eval harness — example (non-secret template)
============================================

How this organization knows an agent works BEFORE it ships.

This file is a SANITIZED, GENERIC example of the evaluation harness used
before any agent behavior is released. It demonstrates the three layers the
org relies on, with zero real data and zero credentials:

  1. GOLDEN DATASETS   — a labeled set of (input, expected) pairs that the
                         behavior must reproduce. Frozen per release.
  2. REGRESSION SUITE  — deterministic checks that must keep passing. A green
                         today must mean the same behavior as green last week.
  3. LLM-AS-JUDGE      — a rubric-scored grader for outputs that cannot be
                         checked by exact match (summaries, style, reasoning).

Principles wired into this example (see docs/decisions/0002-fail-loud.md):

  * FAIL LOUD — any failed check makes the harness exit non-zero. There is no
    path from "nothing ran" to "all green".
  * NO SILENT DEFAULTS — configuration is validated at import time. A missing
    required setting raises instead of silently running with a wrong default.
  * GENERIC ONLY — every ticket, category, and text below is synthetic and
    illustrative. Nothing in this file is a real client, task, or datum.

How to run (Python 3, no dependencies):

    python3 eval_harness.example.py

Exit code 0 = every check passed. Non-zero = something regressed or the
config was invalid. That is the entire contract.

Where the REAL judge call goes is marked inline with "REPLACE:". Copy this
file, wire your own model call there, and never commit real keys (see
examples/config/env.example and docs/sanitization.md).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

# ────────────────────────────────────────────────────────────────────────────
# 0. Resource manifest — expected inputs are declared up front.
#    Missing-but-unregistered is an ERROR (no silent defaults).
# ────────────────────────────────────────────────────────────────────────────

REQUIRED_FILES: dict[str, Path] = {
    # golden dataset the regression suite runs against (frozen per release)
    "golden": Path(__file__).with_name("golden.example.json"),
}

EXPECTED_GOLDEN_FIELDS: frozenset[str] = frozenset(
    {"id", "input", "expected_category", "expected_urgency"}
)


@dataclass
class EvalConfig:
    """Validated configuration. Unknown or empty settings are not allowed."""

    judge_rubric: str
    fail_on_regression: bool = True   # fail-loud: regression ⇒ exit 1
    fail_on_judge: bool = True        # fail-loud: judge rejects ⇒ exit 1
    max_judge_score: int = 5          # rubric scale, 1..5
    pass_threshold: int = 4           # judge verdict at/above this passes


def load_config() -> EvalConfig:
    """Validate required inputs at import-time. Never run unvalidated."""
    for name, path in REQUIRED_FILES.items():
        if not path.exists():
            raise RuntimeError(
                f"Missing required resource: {name} → {path}. "
                f"Expected per resource manifest; cannot run without it."
            )
    return EvalConfig(
        judge_rubric=(
            "1 = unusable, 3 = acceptable, 5 = excellent. "
            "Penalize invented facts (hallucination) hard: any made-up "
            "detail caps the score at 1."
        )
    )


# ────────────────────────────────────────────────────────────────────────────
# 1. Golden dataset — frozen labeled examples. Generic synthetic content only.
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class GoldenCase:
    id: str
    input: str
    expected_category: str
    expected_urgency: str


def load_golden(path: Path) -> list[GoldenCase]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    # Allow either a bare list or a wrapper dict with a "cases" key
    # (the wrapper form carries a _comment header for the sanitized dataset).
    rows = payload["cases"] if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Golden dataset is empty. Zero returned with no "
                           "alert is unacceptable — halt, do not report green.")
    cases: list[GoldenCase] = []
    for row in rows:
        missing = EXPECTED_GOLDEN_FIELDS - set(row.keys())
        if missing:
            raise RuntimeError(
                f"Golden case missing fields {sorted(missing)}: {row.get('id', '<no id>')}"
            )
        cases.append(GoldenCase(**{k: row[k] for k in EXPECTED_GOLDEN_FIELDS}))
    return cases


# ────────────────────────────────────────────────────────────────────────────
# 2. The behavior under test.
#    In the real system this is an agent call. Here it is a deterministic
#    stand-in so the example runs with no credentials. Swap the body for a
#    real seat call; keep the same signature so the suite is unchanged.
# ────────────────────────────────────────────────────────────────────────────

def triage_ticket(text: str) -> tuple[str, str]:
    """Stand-in for 'run this through the agent'. Returns (category, urgency)."""
    lowered = text.lower()
    if any(word in lowered for word in ("pay", "invoice", "billing", "refund")):
        category, urgency = "billing", "high"
    elif any(word in lowered for word in ("login", "password", "access", "locked")):
        category, urgency = "auth", "high"
    elif any(word in lowered for word in ("broken", "crash", "error", "fails")):
        category, urgency = "bug", "medium"
    elif any(word in lowered for word in ("how", "guide", "where", "steps")):
        category, urgency = "support", "low"
    else:
        category, urgency = "other", "medium"
    return category, urgency


# ────────────────────────────────────────────────────────────────────────────
# 3. Regression suite — exact, deterministic checks against the golden set.
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class RegressionResult:
    total: int = 0
    passed: int = 0
    failures: list[str] = field(default_factory=list)


def run_regression(cases: Iterable[GoldenCase]) -> RegressionResult:
    result = RegressionResult()
    for case in cases:
        result.total += 1
        got_cat, got_urg = triage_ticket(case.input)
        if got_cat == case.expected_category and got_urg == case.expected_urgency:
            result.passed += 1
        else:
            result.failures.append(
                f"{case.id}: expected ({case.expected_category}, "
                f"{case.expected_urgency}), got ({got_cat}, {got_urg})"
            )
    return result


# ────────────────────────────────────────────────────────────────────────────
# 4. LLM-as-judge — rubric-scored grader for non-exact outputs.
#    The judge shape is what matters: a rubric, a model call, a verdict.
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class JudgeVerdict:
    case_id: str
    score: int
    reasoning: str


def judge_case(case: GoldenCase, rubric: str) -> JudgeVerdict:
    """Grade one output against a rubric. Return (score 1..5, reasoning).

    REPLACE: in the real harness, `agent_output = <model call>(case.input)`
    and `score` comes from the judge model, e.g.:
        prompt = f"{rubric}\n\nINPUT: {case.input}\nOUTPUT: {agent_output}"
        verdict = <model call>(prompt)      # "3\n...reasoning"
    No credentials live in this file — resolve them from the shared auth
    source (ADR-0003) at runtime.
    """
    # Deterministic stand-in judge so the example is runnable offline:
    # reward outputs that reproduce the golden label, penalize silence.
    category, urgency = triage_ticket(case.input)
    if category == case.expected_category and urgency == case.expected_urgency:
        score, why = 5, "matches golden label; no fabricated detail"
    else:
        score, why = 1, "diverges from golden label (stand-in judge)"
    return JudgeVerdict(case_id=case.id, score=score, reasoning=why)


def run_judge(cases: Iterable[GoldenCase], cfg: EvalConfig) -> list[JudgeVerdict]:
    return [judge_case(case, cfg.judge_rubric) for case in cases]


# ────────────────────────────────────────────────────────────────────────────
# 5. Reporter — every number shown, nothing hidden.
# ────────────────────────────────────────────────────────────────────────────

def print_report(reg: RegressionResult, verdicts: list[JudgeVerdict],
                 cfg: EvalConfig) -> int:
    print("eval_harness — ASBURY SOLUTIONS (generic example)")
    print("=" * 60)
    print(f"regression: {reg.passed}/{reg.total} exact-match checks passed")
    for failure in reg.failures:
        print(f"  ✗ {failure}")
    print("-" * 60)
    judged = len(verdicts)
    passed_judge = sum(1 for v in verdicts if v.score >= cfg.pass_threshold)
    print(f"llm-as-judge: {passed_judge}/{judged} verdicts ≥ threshold "
          f"({cfg.pass_threshold}/{cfg.max_judge_score})")
    for v in verdicts:
        mark = "✓" if v.score >= cfg.pass_threshold else "✗"
        print(f"  {mark} {v.case_id}: {v.score}/{cfg.max_judge_score} — {v.reasoning}")

    reg_failed = bool(reg.failures)
    judge_failed = passed_judge < judged
    if (reg_failed and cfg.fail_on_regression) or (judge_failed and cfg.fail_on_judge):
        print("-" * 60)
        print("RESULT: FAILED — failing loud (exit 1). A green result must "
              "mean the same behavior as the last green result.")
        return 1
    print("-" * 60)
    print("RESULT: PASSED (exit 0)")
    return 0


def main() -> int:
    # Config and manifest validated before anything runs (no silent defaults).
    cfg = load_config()
    golden = load_golden(REQUIRED_FILES["golden"])
    print(f"loaded golden dataset: {len(golden)} cases "
          f"from {REQUIRED_FILES['golden'].name}")
    reg = run_regression(golden)
    verdicts = run_judge(golden, cfg)
    return print_report(reg, verdicts, cfg)


if __name__ == "__main__":
    sys.exit(main())
