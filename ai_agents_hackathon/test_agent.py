import json
import subprocess
import sys
from pathlib import Path

from agent_tools.grader import ALLOWED_ACTIONS
import solution


REPO_ROOT = Path(__file__).parent
PREDS_PATH = REPO_ROOT / "preds.json"
DATASET_PATH = REPO_ROOT / "agent_tools" / "config.agt"

_PRED_CACHE = None


def run_solution():
    subprocess.run([sys.executable, str(REPO_ROOT / "solution.py")], check=True, cwd=REPO_ROOT)


def load_preds():
    assert PREDS_PATH.exists(), "preds.json was not generated."
    return json.loads(PREDS_PATH.read_text(encoding="utf-8"))


def ensure_preds():
    global _PRED_CACHE
    if _PRED_CACHE is None:
        run_solution()
        _PRED_CACHE = load_preds()
    return _PRED_CACHE


def test_solution_generates_predictions():
    preds = ensure_preds()
    assert isinstance(preds, dict) and preds, "preds.json must contain a mapping of cases."

    for case_id, payload in preds.items():
        assert isinstance(payload, dict), f"{case_id} prediction must be a dict."
        culprit = payload.get("culprit")
        assert isinstance(culprit, str) and culprit.strip(), f"{case_id} culprit must be non-empty."
        steps = payload.get("steps")
        assert isinstance(steps, list), f"{case_id} steps must be a list."
        for step in steps:
            assert "action" in step and "args" in step, f"{case_id} step is missing fields."


def test_steps_are_efficient_and_allowed():
    preds = ensure_preds()
    cases, _ = solution.load_cases()
    baseline_counts = {}
    for case_entry in cases:
        cid = case_entry["id"]
        full = case_entry["full"]
        entities = solution.extract_entities(full)
        baseline_counts[cid] = len(solution.build_full_plan(full, entities))

    for cid, payload in preds.items():
        steps = payload.get("steps", [])
        assert steps, f"{cid} must include executed steps."
        assert len(steps) < baseline_counts[cid], f"{cid} should use fewer steps than the baseline plan."
        for step in steps:
            action = step.get("action")
            assert action in ALLOWED_ACTIONS, f"{cid} has disallowed action {action}"


def test_autograder_score_is_perfect():
    preds = ensure_preds()  # ensure file exists
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "autograder_minimal.py"), "-p", str(PREDS_PATH)],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    score_text = result.stdout.strip()
    assert float(score_text) == 100.0, f"Autograder score should be 100.0, got {score_text}"


if __name__ == "__main__":
    # Allow running as a simple script without pytest.
    test_solution_generates_predictions()
    test_steps_are_efficient_and_allowed()
    test_autograder_score_is_perfect()
    print("All agent tests passed.")
