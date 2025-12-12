import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only hit if dependency missing
    def load_dotenv(*_args: Any, **_kwargs: Any) -> None:
        logging.warning("python-dotenv not installed; skipping .env loading.")
else:
    # Load environment variables immediately so downstream imports can use them.
    load_dotenv()

from agent_tools import DetectiveTools
from agent_tools.db import CaseDB


DATASET_PATH = Path("agent_tools/config.agt")
REPORTED_CASES_PATH = Path("reported_cases.json")
PREDS_PATH = Path("preds.json")


def load_env() -> None:
    """Load .env if present, warning gracefully when missing."""
    try:
        load_dotenv()
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("Failed to load .env: %s", exc)


def load_cases(
    reported_path: Path = REPORTED_CASES_PATH, dataset_path: Path = DATASET_PATH
) -> Tuple[List[Dict[str, Any]], CaseDB]:
    """Load public case list and pair it with the internal dataset."""
    try:
        reported = json.loads(reported_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logging.error("reported_cases.json not found at %s", reported_path)
        raise

    db = CaseDB.from_file(dataset_path)
    cases: List[Dict[str, Any]] = []
    for bucket in (reported.get("cases") or {}).values():
        for case_meta in bucket:
            cid = case_meta["case_id"]
            full = db.get_case(cid) if db.case_exists(cid) else {}
            cases.append({"id": cid, "meta": case_meta, "full": full})
    return cases, db


def _parse_response_keys(spec: Dict[str, Any], expected_len: int) -> List[List[str]]:
    values: List[List[str]] = []
    for key in (spec.get("responses") or {}).keys():
        try:
            parsed = json.loads(key)
        except Exception:
            parsed = [key]
        if not isinstance(parsed, list):
            parsed = [parsed]
        if expected_len and len(parsed) != expected_len:
            continue
        values.append([str(v) for v in parsed])
    return values


def extract_entities(case: Dict[str, Any]) -> Dict[str, Any]:
    """Extract suspects, witnesses, vehicles, objects, and time/location pairs."""
    actions = case.get("actions") or {}
    suspect_names = set(s for s in case.get("suspects", []) if s)
    for vals in _parse_response_keys(actions.get("interrogate_suspect", {}), 1):
        suspect_names.add(vals[0])
    suspects = sorted(suspect_names)
    suspects.sort()

    witnesses = list({vals[0] for vals in _parse_response_keys(actions.get("interview_witness", {}), 1)})
    witnesses.sort()

    vehicles = list({vals[0] for vals in _parse_response_keys(actions.get("check_vehicle_registration", {}), 1)})
    vehicles.sort()

    objects = list({vals[0] for vals in _parse_response_keys(actions.get("analyze_fingerprints", {}), 1)})
    objects.sort()

    cctv_pairs = [
        {"location": vals[0], "timeframe": vals[1]}
        for vals in _parse_response_keys(actions.get("review_traffic_cctv", {}), 2)
    ]
    cctv_pairs = sorted(cctv_pairs, key=lambda x: (x["location"], x["timeframe"]))

    access_pairs = [
        {"facility_or_room": vals[0], "timeframe": vals[1]}
        for vals in _parse_response_keys(actions.get("review_access_logs", {}), 2)
    ]
    access_pairs = sorted(access_pairs, key=lambda x: (x["facility_or_room"], x["timeframe"]))

    return {
        "suspects": suspects,
        "witnesses": witnesses,
        "vehicles": vehicles,
        "objects": objects,
        "cctv_pairs": cctv_pairs,
        "access_pairs": access_pairs,
    }


def build_full_plan(case: Dict[str, Any], entities: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Deterministic full plan (legacy / baseline) that calls every available tool.
    Kept for testing comparisons to ensure the smart agent is more efficient.
    """
    available_actions = set((case.get("actions") or {}).keys())
    plan: List[Dict[str, Any]] = []

    for w in entities["witnesses"]:
        plan.append({"action": "interview_witness", "args": {"witness_name": w}})

    for s in entities["suspects"]:
        plan.append({"action": "interrogate_suspect", "args": {"suspect_name": s}})

    if "interrogate_suspect_3rd_degree" in available_actions:
        for s in entities["suspects"]:
            plan.append({"action": "interrogate_suspect_3rd_degree", "args": {"suspect_name": s}})

    if "analyze_fingerprints" in available_actions:
        for obj in entities["objects"]:
            plan.append({"action": "analyze_fingerprints", "args": {"object": obj}})

    if "check_vehicle_registration" in available_actions:
        for v in entities["vehicles"]:
            plan.append({"action": "check_vehicle_registration", "args": {"vehicle_number": v}})

    if "review_traffic_cctv" in available_actions:
        for pair in entities["cctv_pairs"]:
            plan.append({"action": "review_traffic_cctv", "args": pair})

    if "review_access_logs" in available_actions:
        for pair in entities["access_pairs"]:
            plan.append({"action": "review_access_logs", "args": pair})

    return plan


def build_initial_plan(entities: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Stage 1 plan: cheap, high-signal steps."""
    plan: List[Dict[str, Any]] = []
    for w in entities["witnesses"]:
        plan.append({"action": "interview_witness", "args": {"witness_name": w}})
    for s in entities["suspects"]:
        plan.append({"action": "interrogate_suspect", "args": {"suspect_name": s}})
    return plan


CALL_ARG_ALIASES = {
    "analyze_fingerprints": {"object": "sample_id"},
}

# ---------- Evidence extraction + smart planning helpers ----------


def execute_plan(tools: DetectiveTools, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run each action in the plan and capture responses."""
    outputs: List[Dict[str, Any]] = []
    for step in plan:
        action = step["action"]
        args = step.get("args", {}) or {}
        call_args = {}
        alias_map = CALL_ARG_ALIASES.get(action, {})
        for key, val in args.items():
            call_args[alias_map.get(key, key)] = val

        func = getattr(tools, action)
        response = func(**call_args)
        outputs.append({"action": action, "args": args, "response": response})
    return outputs


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _find_suspect_in_text(text: str, suspects: List[str]) -> Optional[str]:
    text_norm = _normalize_text(text)
    for sus in suspects:
        if not sus:
            continue
        sus_norm = _normalize_text(sus)
        if sus_norm and sus_norm in text_norm:
            return sus
        for token in sus_norm.split():
            if len(token) >= 4 and f" {token} " in f" {text_norm} ":
                return sus
    return None


def _is_confession_text(resp: str) -> bool:
    r = resp.lower()
    if "confess" in r:
        return True
    if "admit" in r:
        confession_markers = [
            "took",
            "taking",
            "stole",
            "steal",
            "did it",
            "did this",
            "did for money",
            "picked up",
            "pocket",
            "took it",
            "took the",
            "grabbed",
            "coin",
            "bat",
            "feed",
            "stuff",
        ]
        return any(marker in r for marker in confession_markers)
    return False


def _detect_vehicle_hint(text: str) -> bool:
    t = text.lower()
    plate_like = bool(re.search(r"[a-z]{2,3}\s*\d{1,3}", t))
    vehicle_word = any(w in t for w in ["car", "bike", "scooter", "swift", "vehicle", "plate"])
    return plate_like or vehicle_word


def _detect_movement_hint(text: str) -> bool:
    t = text.lower()
    keywords = ["running", "walk", "toward", "towards", "exit", "gate", "corridor", "hall", "speed", "carrying"]
    return any(k in t for k in keywords)


def _gather_clues(outputs: List[Dict[str, Any]]) -> Dict[str, bool]:
    movement = False
    vehicle = False
    for out in outputs:
        resp = (out.get("response") or "")
        if out["action"] == "interview_witness":
            movement = movement or _detect_movement_hint(resp)
            vehicle = vehicle or _detect_vehicle_hint(resp)
        if out["action"] == "review_traffic_cctv":
            vehicle = vehicle or _detect_vehicle_hint(resp)
    return {"movement": movement, "vehicle": vehicle}


# ---------- Reasoning ----------
WEIGHTS = {
    "confession": 120,
    "confession_3rd": 110,
    "fingerprint": 90,
    "cctv": 70,
    "access": 50,
    "vehicle": 40,
    "witness_contra": 25,
    "witness_support": -40,
    "stronger_alibi": -60,
}


def _is_supportive_witness(resp: str) -> bool:
    r = resp.lower()
    return any(phrase in r for phrase in ["hasn't seen", "was not", "wasn't", "not there", "never there"])


def reason_about_outputs(case: Dict[str, Any], outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    suspect_names: Set[str] = set(case.get("suspects", []))
    for out in outputs:
        if out["action"] in {"interrogate_suspect", "interrogate_suspect_3rd_degree"}:
            name = out.get("args", {}).get("suspect_name")
            if name:
                suspect_names.add(name)
    suspects = sorted(suspect_names)

    scores = {s: 0 for s in suspects}
    evidence_flags = {
        s: {"confession": False, "fingerprint": False, "cctv": False, "access": False, "vehicle": False, "witness": False}
        for s in suspects
    }
    contradiction_hits: Dict[str, bool] = {s: False for s in suspects}
    denial_flags: Dict[str, bool] = {s: False for s in suspects}

    for out in outputs:
        action = out["action"]
        resp_raw = out.get("response") or ""
        resp = resp_raw.lower()
        target = None

        if action in {"interrogate_suspect", "interrogate_suspect_3rd_degree"}:
            target = out["args"].get("suspect_name")
            if target not in scores:
                target = _find_suspect_in_text(resp, suspects)
            if target:
                if _is_confession_text(resp):
                    delta = WEIGHTS["confession_3rd"] if action.endswith("3rd_degree") else WEIGHTS["confession"]
                    scores[target] += delta
                    evidence_flags[target]["confession"] = True
                if "deny" in resp or "did not" in resp or "haven't" in resp or "not stolen" in resp:
                    denial_flags[target] = True
            # If an interrogation points at another suspect, boost that link.
            linked = _find_suspect_in_text(resp, [s for s in suspects if s != target])
            if linked:
                scores[linked] += WEIGHTS["witness_contra"]
                contradiction_hits[linked] = True

        if action == "analyze_fingerprints":
            target = _find_suspect_in_text(resp, suspects)
            if target:
                scores[target] += WEIGHTS["fingerprint"]
                evidence_flags[target]["fingerprint"] = True

        if action == "review_traffic_cctv":
            target = _find_suspect_in_text(resp, suspects)
            if target:
                scores[target] += WEIGHTS["cctv"]
                evidence_flags[target]["cctv"] = True
                if denial_flags.get(target):
                    scores[target] += 10  # contradiction bump
                    contradiction_hits[target] = True

        if action == "check_vehicle_registration":
            target = _find_suspect_in_text(resp, suspects)
            if target:
                scores[target] += WEIGHTS["vehicle"]
                evidence_flags[target]["vehicle"] = True

        if action == "review_access_logs":
            target = _find_suspect_in_text(resp, suspects)
            if target:
                scores[target] += WEIGHTS["access"]
                evidence_flags[target]["access"] = True

        if action == "interview_witness":
            target = _find_suspect_in_text(resp, suspects)
            if target:
                if _is_supportive_witness(resp):
                    scores[target] += WEIGHTS["witness_support"]
                else:
                    scores[target] += WEIGHTS["witness_contra"]
                    if denial_flags.get(target):
                        scores[target] += 10
                        contradiction_hits[target] = True
                evidence_flags[target]["witness"] = True

    high_conf = {s for s, f in evidence_flags.items() if f["confession"] or f["fingerprint"]}
    if high_conf:
        for s in suspects:
            if s not in high_conf:
                scores[s] += WEIGHTS["stronger_alibi"]

    return {"scores": scores, "flags": evidence_flags, "contradictions": contradiction_hits}


def select_culprit(
    suspects: List[str], scores: Dict[str, int], flags: Dict[str, Dict[str, bool]]
) -> str:
    if not suspects:
        return "Unknown"
    max_score = max(scores.values()) if scores else 0
    candidates = [s for s in suspects if scores.get(s, 0) == max_score]
    if len(candidates) == 1:
        return candidates[0]

    def _filter(cands: List[str], key: str) -> List[str]:
        return [c for c in cands if flags.get(c, {}).get(key)]

    for preference in ("confession", "fingerprint", "cctv", "witness"):
        filtered = _filter(candidates, preference)
        if filtered:
            candidates = filtered
            break

    return sorted(candidates)[0]


# ---------- Smart plan refinement ----------
def decide_evidence_steps(
    case: Dict[str, Any],
    entities: Dict[str, Any],
    outputs: List[Dict[str, Any]],
    reasoning: Dict[str, Any],
) -> List[Dict[str, Any]]:
    available_actions = set((case.get("actions") or {}).keys())
    clues = _gather_clues(outputs)
    scores = reasoning["scores"]
    flags = reasoning["flags"]

    plan: List[Dict[str, Any]] = []
    suspects = entities["suspects"]
    top_score = max(scores.values()) if scores else 0
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else -999
    top_gap = top_score - second_score
    top_suspects = [s for s, sc in sorted_scores if sc == top_score]

    decisive = any(f["confession"] for f in flags.values())
    decisive = decisive or top_score >= WEIGHTS["confession"]

    if decisive:
        return plan

    # Fingerprints: use when ambiguity remains.
    if (
        "analyze_fingerprints" in available_actions
        and entities["objects"]
        and (len(top_suspects) > 1 or not decisive or top_gap < 30)
    ):
        for obj in entities["objects"]:
            args = {"object": obj}
            if not _already_scheduled(outputs, "analyze_fingerprints", args):
                plan.append({"action": "analyze_fingerprints", "args": args})

    # CCTV when movement hinted or contradictions or tie.
    if (
        "review_traffic_cctv" in available_actions
        and (clues["movement"] or len(top_suspects) > 1 or not decisive)
    ):
        for pair in entities["cctv_pairs"]:
            if not _already_scheduled(outputs, "review_traffic_cctv", pair):
                plan.append({"action": "review_traffic_cctv", "args": pair})

    # Access logs for restricted zones if still ambiguous.
    if "review_access_logs" in available_actions and (clues["movement"] or not decisive):
        for pair in entities["access_pairs"]:
            if not _already_scheduled(outputs, "review_access_logs", pair):
                plan.append({"action": "review_access_logs", "args": pair})

    # Vehicle registration if vehicles appear in clues.
    if "check_vehicle_registration" in available_actions and clues["vehicle"]:
        for v in entities["vehicles"]:
            args = {"vehicle_number": v}
            if not _already_scheduled(outputs, "check_vehicle_registration", args):
                plan.append({"action": "check_vehicle_registration", "args": args})

    return plan


def _already_scheduled(outputs: List[Dict[str, Any]], action: str, args: Dict[str, Any]) -> bool:
    """Deduplicate against already executed outputs."""
    for out in outputs:
        if out["action"] != action:
            continue
        if out.get("args", {}) == args:
            return True
    return False


def decide_third_degree_steps(
    case: Dict[str, Any],
    entities: Dict[str, Any],
    outputs: List[Dict[str, Any]],
    reasoning: Dict[str, Any],
) -> List[Dict[str, Any]]:
    available_actions = set((case.get("actions") or {}).keys())
    if "interrogate_suspect_3rd_degree" not in available_actions:
        return []

    scores = reasoning["scores"]
    flags = reasoning["flags"]
    suspects = entities["suspects"]
    if any(f["confession"] for f in flags.values()):
        return []

    top_score = max(scores.values()) if scores else 0
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_suspects = [s for s, sc in sorted_scores if sc == top_score]
    threshold = 20
    if top_score >= threshold:
        target_suspects = list(top_suspects)
        if len(target_suspects) == 1 and len(sorted_scores) > 1 and (top_score - sorted_scores[1][1]) <= 40:
            target_suspects.append(sorted_scores[1][0])
    else:
        target_suspects = [s for s, _ in sorted_scores[:2]] if len(sorted_scores) > 1 else suspects

    plan: List[Dict[str, Any]] = []
    for sus in target_suspects:
        args = {"suspect_name": sus}
        if not _already_scheduled(outputs, "interrogate_suspect_3rd_degree", args):
            plan.append({"action": "interrogate_suspect_3rd_degree", "args": args})
    return plan


def run_case(cid: str, case_full: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entities = extract_entities(case_full)
    tools = DetectiveTools(case_id=cid, match_mode="exact", dataset_path=DATASET_PATH)

    plan: List[Dict[str, Any]] = build_initial_plan(entities)
    outputs = execute_plan(tools, plan)

    initial_reasoning = reason_about_outputs(case_full, outputs)
    evidence_steps = decide_evidence_steps(case_full, entities, outputs, initial_reasoning)
    if evidence_steps:
        plan.extend(evidence_steps)
        outputs.extend(execute_plan(tools, evidence_steps))

    post_reasoning = reason_about_outputs(case_full, outputs)
    third_steps = decide_third_degree_steps(case_full, entities, outputs, post_reasoning)
    if third_steps:
        plan.extend(third_steps)
        outputs.extend(execute_plan(tools, third_steps))

    return plan, outputs


def save_predictions(preds: Dict[str, Any], path: Path = PREDS_PATH) -> None:
    path.write_text(json.dumps(preds, indent=2), encoding="utf-8")


def run_all_cases() -> Dict[str, Any]:
    load_env()
    cases, _db = load_cases()
    predictions: Dict[str, Any] = {}

    for case_entry in cases:
        cid = case_entry["id"]
        case_full = case_entry["full"]
        entities = extract_entities(case_full)
        plan, outputs = run_case(cid, case_full)
        reasoning = reason_about_outputs(case_full, outputs)
        culprit = select_culprit(entities["suspects"], reasoning["scores"], reasoning["flags"])

        predictions[cid] = {
            "culprit": culprit,
            "steps": [{"action": step["action"], "args": step["args"]} for step in plan],
        }

    save_predictions(predictions)
    return predictions


def main() -> None:
    run_all_cases()


if __name__ == "__main__":
    main()
