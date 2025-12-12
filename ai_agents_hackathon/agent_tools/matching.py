# agent_tools/matching.py
from __future__ import annotations
import re
from typing import List, Tuple, Optional

# ---------------------------
# Normalization & text similarity
# ---------------------------
_ws_re = re.compile(r"\s+")
_punct_re = re.compile(r"[^\w]+", re.UNICODE)

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = s.strip().lower()
    s = _ws_re.sub(" ", s)
    return s

def normalize_token_set(s: str, *, drop_stopwords: bool = False) -> List[str]:
    s = normalize_text(s)
    s = _punct_re.sub(" ", s)
    toks = [t for t in s.split() if t]
    if drop_stopwords:
        toks = [t for t in toks if t not in STOPWORDS]
    return sorted(set(toks))

def jaccard_token_set(a: str, b: str) -> float:
    A = set(normalize_token_set(a))
    B = set(normalize_token_set(b))
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

def levenshtein_ratio(a: str, b: str) -> float:
    # classic DP; good enough for short strings
    a, b = normalize_text(a), normalize_text(b)
    la, lb = len(a), len(b)
    if la == 0 and lb == 0:
        return 1.0
    dp = list(range(lb + 1))
    for i in range(1, la + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, lb + 1):
            cur = min(
                dp[j] + 1,                 # deletion
                dp[j-1] + 1,               # insertion
                prev + (a[i-1] != b[j-1])  # substitution
            )
            prev, dp[j] = dp[j], cur
    dist = dp[lb]
    return 1.0 - dist / max(la, lb)

def text_similarity(a: str, b: str) -> float:
    # Blend token-set & edit distance for robustness
    return 0.6 * jaccard_token_set(a, b) + 0.4 * levenshtein_ratio(a, b)


# ---------------------------
# Plates & phones
# ---------------------------
def normalize_plate(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()

def plate_similarity(a: str, b: str) -> float:
    na, nb = normalize_plate(a), normalize_plate(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    # Reward suffix match strongly (spacing/dashes vary)
    suffix_len = min(6, len(na), len(nb))
    suf_match = 1.0 if na[-suffix_len:] == nb[-suffix_len:] else 0.0
    base = levenshtein_ratio(na, nb)
    return 0.5 * base + 0.5 * suf_match

def normalize_phone(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def phone_similarity(a: str, b: str) -> float:
    na, nb = normalize_phone(a), normalize_phone(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    # Match by last N digits (tolerate country codes)
    for k in (8, 6, 4):
        if len(na) >= k and len(nb) >= k and na[-k:] == nb[-k:]:
            return 0.9 if k == 8 else (0.8 if k == 6 else 0.6)
    return 0.0


# ---------------------------
# Timeframe parsing & scoring
# ---------------------------
_time_re = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.IGNORECASE)

def _to_minutes(h: int, m: int, ampm: Optional[str]) -> int:
    if ampm:
        ampm = ampm.lower()
        if ampm == "am":
            if h == 12:
                h = 0
        elif ampm == "pm":
            if h != 12:
                h += 12
    return (h % 24) * 60 + (m % 60)

def parse_clock(token: str) -> Optional[int]:
    m = _time_re.match(token)
    if not m:
        return None
    h = int(m.group(1))
    mm = int(m.group(2) or 0)
    ampm = m.group(3)
    if not (0 <= h <= 24 and 0 <= mm <= 59):
        return None
    return _to_minutes(h, mm, ampm)

def parse_timeframe(s: str) -> Optional[Tuple[int, int]]:
    # supports "20:10-20:20", "8pm–8:20pm", "20:10 to 20:20"
    s = s.strip().lower().replace("—", "-").replace("–", "-")
    if " to " in s:
        parts = s.split(" to ")
    elif "-" in s:
        parts = s.split("-")
    else:
        return None
    if len(parts) != 2:
        return None
    start = parse_clock(parts[0].strip())
    end = parse_clock(parts[1].strip())
    if start is None or end is None:
        return None
    # wrap-around (e.g., 23:50-00:10)
    if end < start:
        end += 24 * 60
    return start, end

def overlap_minutes(a: Tuple[int,int], b: Tuple[int,int]) -> int:
    (a1, a2), (b1, b2) = a, b
    # also compare against b shifted by 24h to handle wrap-around
    candidates = [(b1, b2), (b1 + 1440, b2 + 1440)]
    best = 0
    for x1, x2 in candidates:
        best = max(best, max(0, min(a2, x2) - max(a1, x1)))
    return best

def timeframe_score(input_tf: str, cand_tf: str, grace_min: int = 10) -> float:
    A = parse_timeframe(input_tf)
    B = parse_timeframe(cand_tf)
    if not A or not B:
        # fallback to fuzzy text if unparsable
        return text_similarity(input_tf, cand_tf)
    ov = overlap_minutes(A, B)
    lenA = max(1, A[1] - A[0])
    lenB = max(1, B[1] - B[0])
    start_delta = min(
        abs(A[0]-B[0]),
        abs((A[0]+1440)-B[0]),
        abs(A[0]-(B[0]+1440))
    )
    if ov > 0:
        return min(1.0, 0.5 + 0.5 * ov / max(lenA, lenB))
    if start_delta <= grace_min:
        return 0.7
    return 0.0


# ---------------------------
# Person-name similarity (STRICT: no prefixes, no typos)
# ---------------------------
STOPWORDS = {"the", "mr", "mrs", "ms", "sir", "maam", "ma'am"}

def person_name_similarity(a: str, b: str) -> float:
    """
    Only accept if any input token (len >= 4) matches a token in the canonical
    name EXACTLY. No prefixes, no typos.
    Examples:
      'Imran'  ~ 'Imran the Vendor' -> OK
      'imr'    ~ 'Imran the Vendor' -> NO
      'the'    ~ 'Imran the Vendor' -> NO
      'Niraj'  ~ 'Neeraj the Volunteer' -> NO
    """
    a_tokens = normalize_token_set(a, drop_stopwords=True)
    b_tokens = normalize_token_set(b, drop_stopwords=True)
    if not a_tokens or not b_tokens:
        return 0.0
    for t in a_tokens:
        if len(t) >= 4 and t in b_tokens:
            return 1.0  # strong accept on exact token match
    return 0.0


# ---------------------------
# Per-action scorers
# ---------------------------
def default_argwise_scorer(action: str, names: List[str], inp: List[str], key: Tuple[str, ...]) -> float:
    sims = []
    for v_in, v_key in zip(inp, key):
        sims.append(text_similarity(v_in, v_key))
    return sum(sims) / max(1, len(sims))

def scorer_location_time(action: str, names: List[str], inp: List[str], key: Tuple[str, ...]) -> float:
    # names expected like ["location", "timeframe"] or facility/timeframe
    try:
        loc_i = names.index("location") if "location" in names else names.index("facility_or_room")
    except ValueError:
        loc_i = 0
    try:
        tf_i = names.index("timeframe")
    except ValueError:
        tf_i = len(names) - 1
    loc_sim = text_similarity(inp[loc_i], key[loc_i])
    tf_sim = timeframe_score(inp[tf_i], key[tf_i], grace_min=10)
    return 0.55 * loc_sim + 0.45 * tf_sim

def scorer_wifi(action: str, names: List[str], inp: List[str], key: Tuple[str, ...]) -> float:
    area_sim = text_similarity(inp[0], key[0])
    tf_sim = timeframe_score(inp[1], key[1], grace_min=10)
    return 0.5 * area_sim + 0.5 * tf_sim

def scorer_plate(action: str, names: List[str], inp: List[str], key: Tuple[str, ...]) -> float:
    return plate_similarity(inp[0], key[0])

def scorer_phone(action: str, names: List[str], inp: List[str], key: Tuple[str, ...]) -> float:
    return phone_similarity(inp[0], key[0])

def scorer_party_time(action: str, names: List[str], inp: List[str], key: Tuple[str, ...]) -> float:
    # e.g., check_upi_transactions(party_name, timeframe)
    name_sim = text_similarity(inp[0], key[0])
    tf_sim = timeframe_score(inp[1], key[1], grace_min=60)  # ledgers often queried with looser windows
    return 0.6 * name_sim + 0.4 * tf_sim

def scorer_person(action: str, names: List[str], inp: List[str], key: Tuple[str, ...]) -> float:
    # Person-only actions (first arg is a name)
    return person_name_similarity(inp[0], key[0])


# ---------------------------
# Registry: scorers & thresholds
# ---------------------------
ACTION_SCORERS = {
    "review_traffic_cctv": scorer_location_time,
    "review_access_logs":  scorer_location_time,
    "review_wifi_logs":    scorer_wifi,
    "check_vehicle_registration": scorer_plate,
    "trace_mobile_number": scorer_phone,
    "check_upi_transactions": scorer_party_time,
    # Strict person-name scorers
    "interrogate_suspect": scorer_person,
    "interrogate_suspect_final": scorer_person,
    "interview_witness": scorer_person,
    "verify_alibi": scorer_person,
    "interrogate_suspect_3rd_degree": scorer_person,  # use strict name matching
}

ACTION_THRESHOLDS = {
    "review_traffic_cctv": 0.75,
    "review_access_logs":  0.75,
    "review_wifi_logs":    0.75,
    "check_vehicle_registration": 0.85,
    "trace_mobile_number": 0.85,
    "check_upi_transactions": 0.75,
    # Strict: require exact token match (>=4 chars)
    "interrogate_suspect": 0.85,
    "interrogate_suspect_final": 0.85,
    "interview_witness": 0.85,
    "verify_alibi": 0.85,
    "interrogate_suspect_3rd_degree": 0.85,
}
