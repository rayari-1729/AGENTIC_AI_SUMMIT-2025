
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from .constants import FIELD_ALIAS_CATEGORY
from .matching import (
    ACTION_SCORERS, ACTION_THRESHOLDS, default_argwise_scorer,
    normalize_text
)
from .codec import decode_file

class CaseDB:
    def __init__(self, data: Dict[str, Any]):
        self.schema_version: str = data.get("schema_version", "")
        self.actions_catalog: Dict[str, Dict[str, List[str]]] = data["actions_catalog"]
        self.aliases: Dict[str, Dict[str, List[str]]] = data.get("aliases", {})

        self.cases_by_id: Dict[str, Dict[str, Any]] = {}
        for _difficulty, cases in (data.get("cases") or {}).items():
            for case in cases:
                self.cases_by_id[case["case_id"]] = case

        self.alias_reverse: Dict[str, Dict[str, str]] = {}
        for cat, mapping in self.aliases.items():
            rev = {}
            for canon, alist in mapping.items():
                rev[normalize_text(canon)] = canon
                for a in alist:
                    rev[normalize_text(a)] = canon
            self.alias_reverse[cat] = rev

        self.index: Dict[str, Dict[str, Dict[Tuple[str, ...], str]]] = {}
        for cid, case in self.cases_by_id.items():
            self.index[cid] = {}
            for action_name, spec in (case.get("actions") or {}).items():
                tuple_map: Dict[Tuple[str, ...], str] = {}
                arg_names = self.actions_catalog[action_name]["input_args"]
                for key_str, resp in (spec.get("responses") or {}).items():
                    try:
                        vals = [str(v) for v in json.loads(key_str)]
                    except Exception:
                        vals = [str(key_str)]
                    canon_vals = []
                    for name, val in zip(arg_names, vals):
                        cat = FIELD_ALIAS_CATEGORY.get(name)
                        canon_vals.append(self.canonicalize(cat, val) if cat else val)
                    tuple_map[tuple(canon_vals)] = resp
                self.index[cid][action_name] = tuple_map

    @classmethod
    def from_file(cls, path: str | Path):
        p = Path(path)
        # Prefer encoded dataset when extension is .agt or magic is present
        try:
            raw = p.read_bytes()
            if raw[:4] == b"AGT1" or p.suffix.lower() == ".agt":
                data = json.loads(decode_file(p))
                return cls(data)
        except FileNotFoundError:
            raise
        except Exception:
            # fall back to JSON loader if decoding fails
            pass
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    def case_exists(self, case_id: str) -> bool:
        return case_id in self.cases_by_id

    def get_case(self, case_id: str) -> Dict[str, Any]:
        return self.cases_by_id[case_id]

    def actions_for_case(self, case_id: str) -> List[str]:
        return list((self.get_case(case_id).get("actions") or {}).keys())

    def input_arg_order(self, action_name: str) -> List[str]:
        return self.actions_catalog[action_name]["input_args"]

    def canonicalize(self, category: Optional[str], value: str) -> str:
        if not category:
            return value
        rev = self.alias_reverse.get(category, {})
        return rev.get(normalize_text(value), value)

    def lookup_exact(self, case_id: str, action_name: str, args_in_order: List[str]) -> Optional[str]:
        action_map = self.index.get(case_id, {}).get(action_name, {})
        return action_map.get(tuple(str(v) for v in args_in_order))

    def lookup_fuzzy(self, case_id: str, action_name: str, args_in_order: List[str]) -> Tuple[Optional[str], str]:
        expected_order = self.input_arg_order(action_name)
        action_map = self.index.get(case_id, {}).get(action_name, {})
        if not action_map:
            return None, "No scripted calls for this action in this case."

        scorer = ACTION_SCORERS.get(action_name, default_argwise_scorer)

        best: List[Tuple[float, Tuple[str, ...], str]] = []
        for key_tuple, resp in action_map.items():
            score = scorer(action_name, expected_order, args_in_order, key_tuple)
            best.append((score, key_tuple, resp))
        best.sort(reverse=True, key=lambda x: x[0])

        th = ACTION_THRESHOLDS.get(action_name, 0.75)
        topk = [b for b in best if b[0] >= th][:3]

        if not topk:
            hints = "\n".join(
                f"  - {dict(zip(expected_order, kt))}   (score={sc:.2f})"
                for sc, kt, _ in best[:3]
            )
            return None, f"No close match. Closest scripted calls:\n{hints}"

        if len(topk) >= 2 and (topk[0][0] - topk[1][0]) < 0.05:
            options = "\n".join(
                f"  - {dict(zip(expected_order, kt))}   (score={sc:.2f})"
                for sc, kt, _ in topk
            )
            return None, f"[ambiguous] Multiple close matches:\n{options}"

        return topk[0][2], f"Matched approximately with score={topk[0][0]:.2f}."
