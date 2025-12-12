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


## 5) Understanding agent_tools and config.agt

This hackathon uses a custom dataset and tool framework designed so that the agent interacts with a simulated environment, similar to real LLM agent architecture.

1. config.agt is the Hidden Ground-Truth Dataset

  - It is NOT a normal JSON file.
  - It is encoded using a custom AGT1 format (compressed + XOR-encrypted using Blake2s keystream).
  - The dataset contains:
      - Full case definitions
      - Canonical suspect/witness names & aliases
      - All actions & valid tool call combinations 
      - Expected tool responses
      - Ground truth perpetrators
      - Reference step counts
  - Students cannot and should not decode the dataset directly.
  - The autograder uses the same .agt file to compute correctness.

2. How CaseDB Loads the Dataset

CaseDB.from_file() automatically loads the .agt dataset via:
  - ecode_file() from codec.py
  - JSON parsing of the decoded content
  - Creation of internal indexes:
    - For each action, maps (args_tuple) → response

This ensures that the agent calls tools instead of inspecting the raw dataset.

3. DetectiveTools API

DetectiveTools is the only allowed interface between your agent and the dataset.

Each function:
  - interview_witness
  - review_traffic_cctv
  - analyze_fingerprints
  - interrogate_suspect
  - review_access_logs
  - etc.

wraps an internal call:

``` python 
self._call(action_name, **args)
```

The call pipeline:
  1. Validate case_id and action availability
  2. Canonicalize inputs (names, plates, locations
  3. Exact match lookup
  4. Optional fuzzy match (if match_mode="smart")
  5. Return scripted response text

No leakage, no ground truth exposure.

4. Why You Cannot Reverse Engineer the Ground Truth

Even though decoding logic exists for tool execution:

The dataset is encrypted & compressed.

Code does not expose raw data to the student.

CaseDB provides only:

Available actions

Canonicalization helpers

Tool-returned response strings

Culprits, correct inputs, and ground truth responses are never accessible directly.

This ensures fairness and prevents cheating.

5. How Your Agent Should Work

The agent must:

Infer from tool responses

Reason using evidence

Call tools selectively

Produce:

culprit

ordered tool steps

The grader checks only predictions, not agent internals


