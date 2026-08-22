"""
narrate.py — Plain-English narration of a root-cause finding.

Falls back to a deterministic template on any failure — unavailable client,
API error, or a figure that isn't in the evidence object. The report is complete
and correct either way; only the prose quality differs.

SYSTEM_PROMPT enforces the hard boundary: LLM may only use numbers already
present in the finding object. _assert_no_invented_figures enforces this at
runtime, not just as a README claim.
"""
import json
import re

SYSTEM_PROMPT = """You explain a finance reconciliation finding to a controller.

You are given a COMPLETE, ALREADY-COMPUTED finding object. Your only job is to
turn it into 2-3 sentences of plain English.

HARD RULES:
- Do NOT compute, infer, estimate, or adjust any number.
- Use ONLY figures present in the finding object, copied exactly.
- Do NOT change or soften the verdict. If verdict is "possible_pattern -
  insufficient evidence", your text must NOT assert a cause. Say what was
  observed and that the evidence is insufficient.
- Do NOT add recommendations beyond controller_action.
- No preamble, no hedging boilerplate. Just the explanation.
"""


def narrate(finding: dict, client=None) -> tuple:
    """Returns (text, source). Falls back to a deterministic template on any
    failure - unavailable client, API error, or a figure that isn't in the
    evidence object. The report is complete and correct either way; only the
    prose quality differs.
    """
    if client is None:
        return _template(finding), "template"
    try:
        text = client.complete(SYSTEM_PROMPT, json.dumps(finding, indent=2))
        _assert_no_invented_figures(text, finding)
        return text, "llm"
    except Exception:
        return _template(finding), "template"


def _template(finding: dict) -> str:
    """Deterministic fallback narration. Must exist and must be used whenever
    client is None or the LLM path fails for any reason, including a
    hallucinated figure."""
    if finding["verdict"] == "likely_root_cause":
        return (f"{finding['support_count']} exceptions sharing "
                f"{finding['shared_attributes']} show a consistent "
                f"{finding['deviation_summary']['sign']} deviation "
                f"(confidence: {finding['confidence']}). "
                f"Observed batch impact: {finding['observed_batch_impact_paise']} paise. "
                f"{finding['controller_action']}")
    return (f"{finding['support_count']} exceptions share "
            f"{finding['shared_attributes']}, covering "
            f"{finding['coverage_ratio']*100:.0f}% of exceptions in this batch — "
            f"below the threshold to confirm a cause. {finding['controller_action']}")


def _assert_no_invented_figures(text: str, finding: dict) -> None:
    """Every numeric token in the narration must already exist in the finding.
    This enforces the deterministic-computation/LLM-explanation boundary at
    runtime rather than leaving it as an unverified README claim."""
    allowed = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(finding)))
    for ratio_key in ("mean_deviation_ratio", "coefficient_of_variation"):
        v = finding["deviation_summary"].get(ratio_key)
        if v is not None:
            allowed |= {str(round(v * 100, 2)), str(round(v * 100, 1))}
    for token in re.findall(r"\d+(?:\.\d+)?", text):
        if token not in allowed:
            raise ValueError(f"narration introduced unverified figure: {token}")
