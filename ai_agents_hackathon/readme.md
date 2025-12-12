# AI Agents Hackathon

Short guide to run the cases, use the tools, and grade predictions.

---

## 1) Setup
- Python 3.9+ (no extra deps).
- Repo layout:
  - `agent_tools/` (library)
  - `autograder.py` (prints only a final score)
  - `tools_description.json` (tool names & args)
  - `reported_cases.json` (case id, case description, initial clue, suspects)
  - `preds.json` (sample predictions)

---

## 2) Use the tools in your own code
```python
from agent_tools import DetectiveTools

tools = DetectiveTools(
    case_id="canteen_cashbox_theft",
    match_mode="smart"  # or "exact"
)

print(tools.interview_witness("Nisha"))
print(tools.review_traffic_cctv("Parking B", "20:10-20:20"))
print(tools.interrogate_suspect("Neeraj the Volunteer"))
```

**Input rules (strict):**
- Names must include a full token ≥ 4 letters (e.g., “Neeraj”). Typos/short fragments don’t match.
- Timeframes like `HH:MM-HH:MM` or `h[:mm]am/pm-h[:mm]am/pm`.
- Plates/phones ignore spacing & punctuation.

---

## 3) Autograder (final score only)
Prepare `preds.json`:

```json
{
  "<case_id>": {
    "culprit": "<full name>",
    "steps": [
      { "action": "<tool_name>", "args": { /* arg_name: value */ } }
    ]
  }
}
```


Run:
```bash
python autograder_minimal.py  -p preds.json
```
The autograder prints **only** the final score (0–100). Scoring adds bonuses based on your step count vs. the reference.


Google form for submission:
https://forms.gle/cJWhTe3P9ygDhM6k7
---

## 4) Troubleshooting
- `ModuleNotFoundError: agent_tools` → run from the repo root or add it to `PYTHONPATH`.
- “Unknown action/case” → that tool may not be enabled for the current case or the case_id is wrong.
- No dataset found → ensure an `.agt` (or JSON) file is in the repo root.


