# autograder_minimal.py
# Prints ONLY the final score (0–100). No per-case details, no ground-truth leaks.
# Steps are graded from a list of action calls: {"action": "<tool_name>", "args": {...}}

from __future__ import annotations
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
import json, zlib, hashlib, re, argparse

MAGIC = b"AGT1"
_SECRET = b"\xf0\x9f\x95\xb5\xef\xb8\x8fagents-workshop-2025\xf0\x9f\xa7\xa9"

# ---------- dataset load (supports .agt or .json) ----------
def _keystream(secret: bytes, salt: bytes, nbytes: int) -> bytes:
    out = bytearray(); c = 0
    while len(out) < nbytes:
        h = hashlib.blake2s(digest_size=32)
        h.update(secret); h.update(salt); h.update(c.to_bytes(4, "big"))
        out.extend(h.digest()); c += 1
    return bytes(out[:nbytes])

def _decode_agt(path: Path) -> bytes:
    blob = path.read_bytes()
    if not blob.startswith(MAGIC):
        raise ValueError("Not an AGT1 encoded file")
    salt = blob[4:12]
    n = int.from_bytes(blob[12:16], "big")
    cipher = blob[16:16+n]
    ks = _keystream(_SECRET, salt, len(cipher))
    comp = bytes(a ^ b for a, b in zip(cipher, ks))
    return zlib.decompress(comp)

def load_dataset(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    raw = p.read_bytes()
    if raw[:4] == MAGIC or p.suffix.lower() == ".agt":
        return json.loads(_decode_agt(p))
    return json.loads(raw.decode("utf-8"))

# ---------- name matching (strict) ----------
_ws_re = re.compile(r"\s+")
_punct_re = re.compile(r"[^\w]+", re.UNICODE)
STOPWORDS = {"the", "mr", "mrs", "ms", "sir", "maam", "ma'am"}

def normalize_text(s: str) -> str:
    if s is None: return ""
    s = s.strip().lower()
    s = _ws_re.sub(" ", s)
    return s

def normalize_token_set(s: str, drop_stopwords: bool = False):
    s = normalize_text(s)
    s = _punct_re.sub(" ", s)
    toks = [t for t in s.split() if t]
    if drop_stopwords:
        toks = [t for t in toks if t not in STOPWORDS]
    return sorted(set(toks))

def build_alias_reverse(aliases: Dict[str, Dict[str, list]]) -> Dict[str, Dict[str, str]]:
    rev = {}
    for cat, mapping in (aliases or {}).items():
        r = {}
        for canon, alist in (mapping or {}).items():
            r[normalize_text(canon)] = canon
            for a in (alist or []):
                r[normalize_text(a)] = canon
        rev[cat] = r
    return rev

def canonicalize_name(name: str, people_rev: Dict[str, str]) -> str:
    key = normalize_text(name)
    return people_rev.get(key, name)

def names_match_strict(pred: str, truth: str) -> bool:
    if normalize_text(pred) == normalize_text(truth):
        return True
    A = normalize_token_set(pred, drop_stopwords=True)
    B = normalize_token_set(truth, drop_stopwords=True)
    if not A or not B:
        return False
    for t in A:
        if len(t) >= 4 and t in B:
            return True
    return False

# ---------- steps parsing ----------
ALLOWED_ACTIONS = {
    "interview_witness", "review_traffic_cctv", "check_vehicle_registration",
    "collect_evidence", "analyze_fingerprints", "trace_mobile_number",
    "review_access_logs", "review_wifi_logs", "check_upi_transactions",
    "interrogate_suspect", "interrogate_suspect_3rd_degree"
}

def count_steps(steps) -> int:
    """Count only valid action entries; ignore malformed items. Args are accepted but not validated."""
    if not isinstance(steps, list):
        return 0
    n = 0
    for s in steps:
        if isinstance(s, str):
            act = s.strip().lower()
            if act in ALLOWED_ACTIONS:
                n += 1
        elif isinstance(s, dict):
            act = s.get("action")
            if isinstance(act, str) and act.strip().lower() in ALLOWED_ACTIONS:
                n += 1
    return n

# ---------- predictions parsing ----------
def parse_pred_value(v) -> Tuple[Optional[str], Optional[int]]:
    """
    Returns (culprit_name, steps_count)
    Accepts:
      {"culprit": "...", "steps": [ {action, args}, ... ]}
      ["Name", [ {action, args}, ... ]]      # tolerated
      "Name"                                 # no steps bonus
    """
    if isinstance(v, dict):
        cul = v.get("culprit")
        stp = v.get("steps")
        if isinstance(stp, list):
            return cul, count_steps(stp)
        return cul, None
    if isinstance(v, list) and v:
        cul = v[0] if isinstance(v[0], str) else None
        stp = v[1] if len(v) > 1 else None
        if isinstance(stp, list):
            return cul, count_steps(stp)
        return cul, None
    if isinstance(v, str):
        return v, None
    return None, None

# ---------- reference steps ----------
def get_ref_steps_for_case(case: Dict[str, Any], ref_steps_map: Optional[Dict[str, int]]) -> Optional[int]:
    cid = case.get("case_id")
    if ref_steps_map and cid in ref_steps_map:
        return int(ref_steps_map[cid])
    for key in ("optimal_steps", "min_steps"):
        if key in case and isinstance(case[key], int):
            return int(case[key])
    return None

# ---------- scoring ----------
def compute_score(preds: Dict[str, Any], data: Dict[str, Any], ref_steps_map: Optional[Dict[str,int]]) -> float:
    alias_rev = build_alias_reverse(data.get("aliases", {}))
    people_rev = alias_rev.get("people", {})

    # Build scorable cases (only those with a solution)
    gt: Dict[str, str] = {}
    ref_steps: Dict[str, Optional[int]] = {}
    scorable_cases = []
    for _bucket, items in (data.get("cases") or {}).items():
        for case in items:
            sol = str(case.get("solution") or "").strip()
            if not sol:
                continue
            cid = case["case_id"]
            scorable_cases.append(cid)
            gt[cid] = sol
            ref_steps[cid] = get_ref_steps_for_case(case, ref_steps_map)

    # Weights
    BASE_CORRECT = 2.0     # correct culprit
    BONUS_EQUAL   = 0 # 0.50   # k_pred == k_ref
    BONUS_FEWER   = 0 # 1.0   # k_pred <  k_ref (brownie points)
    BONUS_MORE    = 0.0   # k_pred >  k_ref (some score)
    PER_CASE_MAX  = BASE_CORRECT + BONUS_FEWER

    total_points = 0.0
    max_points = PER_CASE_MAX * len(scorable_cases)

    for cid in scorable_cases:
        pred_val = preds.get(cid)
        if pred_val is None:
            continue  # missing: 0 points for this case
        pred_name, pred_steps = parse_pred_value(pred_val)
        if not pred_name:
            continue

        # Canonicalize via aliases
        pred_can = canonicalize_name(pred_name, people_rev)
        truth_can = canonicalize_name(gt[cid], people_rev)

        # Correctness
        if not names_match_strict(pred_can, truth_can):
            continue

        pts = BASE_CORRECT
        k_ref = ref_steps.get(cid)
        if pred_steps is not None and isinstance(k_ref, int):
            if pred_steps < k_ref:
                pts += BONUS_FEWER
            elif pred_steps == k_ref:
                pts += BONUS_EQUAL
            else:
                pts += BONUS_MORE

        total_points += pts

    if max_points <= 0:
        return 0.0
    return round(100.0 * total_points / max_points, 2)

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Autograder (prints ONLY a final score 0–100).")
    ap.add_argument("-d", "--dataset", default="agent_tools/config.agt",
                    help="Path to dataset (.agt preferred, .json also allowed).")
    ap.add_argument("-p", "--predictions", required=True,
                    help="JSON: { case_id: { 'culprit': str, 'steps': [ {action, args}, ... ] } } "
                         "Also accepts ['Name', stepsList] or 'Name'.")
    ap.add_argument("-r", "--ref-steps",
                    help="Optional JSON: { case_id: optimal_steps }. Overrides any steps stored in dataset.")
    args = ap.parse_args()

    data = load_dataset(args.dataset)
    preds = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    ref_steps_map = None
    if args.ref_steps:
        ref_steps_map = json.loads(Path(args.ref_steps).read_text(encoding="utf-8"))

    score = compute_score(preds, data, ref_steps_map)
    # Print ONLY the number
    print(score)

if __name__ == "__main__":
    main()
