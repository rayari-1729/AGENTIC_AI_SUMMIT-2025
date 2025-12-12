# agent_tools/actions.py
from __future__ import annotations
from typing import Optional, Union
from pathlib import Path

# DB stays internal; students never import it
from .db import CaseDB
from .constants import FIELD_ALIAS_CATEGORY

class DetectiveTools:
    """
    Student-facing API.
    Loads the dataset internally and never reveals scripted tuples or answers.
    """
    def __init__(self, case_id: str, match_mode: str = "smart", dataset_path: Union[str, Path] = "agent_tools/config.agt"):
        self._db = CaseDB.from_file(dataset_path)
        self.case_id = case_id
        self.match_mode = match_mode

    def set_case(self, case_id: str):
        self.case_id = case_id

    # ---------- Core call wrapper (ground-truth safe) ----------
    def _call(self, action_name: str, **kwargs) -> str:
        if not self._db.case_exists(self.case_id):
            return "[error] Unknown case_id."

        # Validate action exists in catalog
        try:
            expected_order = self._db.input_arg_order(action_name)
        except KeyError:
            return "[error] Unknown action."

        # Validate action is enabled for this case (do not list enabled actions)
        if action_name not in self._db.actions_for_case(self.case_id):
            return "No useful information found. Time wasted."
            # return "[error] This action is not available for the current case."

        # Build ordered args (with alias canonicalization)
        try:
            args_in_order = []
            for name in expected_order:
                v = str(kwargs[name])
                cat = FIELD_ALIAS_CATEGORY.get(name)
                args_in_order.append(self._db.canonicalize(cat, v) if cat else v)
        except KeyError as e:
            # Arg names are not ground-truth; safe to show
            return f"[error] Missing required argument '{e.args[0]}'. Required args: {expected_order}"

        # 1) Exact match
        resp = self._db.lookup_exact(self.case_id, action_name, args_in_order)
        if resp is not None or self.match_mode == "exact":
            if resp is None:
                # Do NOT print known tuples/examples
                return "[no-match] Inputs not recognized. Check spelling, use full names, and standard time ranges (e.g., '20:10-20:20')."
            return resp

        # 2) Smart (fuzzy) fallback — do NOT surface debug info
        resp, _dbg = self._db.lookup_fuzzy(self.case_id, action_name, args_in_order)
        if resp is None:
            # Keep generic; no hints that expose candidates
            return "[no-match] Could not confidently match your inputs. Try exact location names and full person names."
        return resp

    # ---------- Allowed tool functions ----------
    def interview_witness(self, witness_name: str) -> str:
        return self._call("interview_witness", witness_name=witness_name)

    def review_traffic_cctv(self, location: str, timeframe: str) -> str:
        return self._call("review_traffic_cctv", location=location, timeframe=timeframe)

    def check_vehicle_registration(self, vehicle_number: str) -> str:
        return self._call("check_vehicle_registration", vehicle_number=vehicle_number)

    def collect_evidence(self, location: str, evidence_type: str) -> str:
        return self._call("collect_evidence", location=location, evidence_type=evidence_type)

    def analyze_fingerprints(self, sample_id: str) -> str:
        return self._call("analyze_fingerprints", sample_id=sample_id)

    def trace_mobile_number(self, mobile_number: str) -> str:
        return self._call("trace_mobile_number", mobile_number=mobile_number)

    def review_access_logs(self, facility_or_room: str, timeframe: str) -> str:
        return self._call("review_access_logs", facility_or_room=facility_or_room, timeframe=timeframe)

    def review_wifi_logs(self, area: str, timeframe: str) -> str:
        return self._call("review_wifi_logs", area=area, timeframe=timeframe)

    def check_upi_transactions(self, party_name: str, timeframe: str) -> str:
        return self._call("check_upi_transactions", party_name=party_name, timeframe=timeframe)

    def interrogate_suspect(self, suspect_name: str) -> str:
        return self._call("interrogate_suspect", suspect_name=suspect_name)

    def interrogate_suspect_final(self, suspect_name: str) -> str:
        return self._call("interrogate_suspect_final", suspect_name=suspect_name)
    
    def interrogate_suspect_3rd_degree(self, suspect_name: str) -> str:
        return self._call("interrogate_suspect_3rd_degree", suspect_name=suspect_name)

