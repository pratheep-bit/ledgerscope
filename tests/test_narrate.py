"""
test_narrate.py — Tests for the narration module and hallucination guard.

CRITICAL test: the hallucinating client must be caught and fallen back to
template, not passed through. This is the test that proves the guardrail
actually fires, not just that the code exists.
"""
import pytest
from ledgerscope.narrate import narrate


# ---------------------------------------------------------------------------
# Minimal valid finding for use in tests
# ---------------------------------------------------------------------------

def _minimal_finding(verdict="likely_root_cause", support=10, coverage=0.556):
    return {
        "verdict": verdict,
        "cause_type": "RATE_MISCONFIGURATION",
        "shared_attributes": {"payment_method": "netbanking", "fee_plan_id": "PLN_ENT_2024"},
        "affected_txn_ids": [f"TXN_{i:03d}" for i in range(support)],
        "support_count": support,
        "coverage_ratio": round(coverage, 3),
        "deviation_summary": {
            "sign": "positive",
            "mean_deviation_ratio": 0.05263,
            "coefficient_of_variation": 0.004,
            "consistent": True,
        },
        "rule_id": "RC-RULE-02: shared attribute + sign consistency + coverage>0.50",
        "confidence": "high",
        "observed_batch_impact_paise": 124730,
        "projected_monthly_impact": {
            "value_paise": 1247300,
            "basis": "ASSUMPTION - batch spans 3 day(s); scaled x10.0 to a 30-day month",
            "scaling_factor": 10.0,
            "is_estimate": True,
        },
        "controller_action": (
            "Audit the netbanking rate on fee plan PLN_ENT_2024 — settlement is "
            "applying a rate inconsistent with the plan's configured rate."
        ),
    }


# ---------------------------------------------------------------------------
# Test 1: template fallback when client=None
# ---------------------------------------------------------------------------

def test_narrate_template_fallback_when_no_client():
    """narrate(finding, client=None) must return ("...", "template") with non-empty text."""
    finding = _minimal_finding()
    text, source = narrate(finding, client=None)

    assert source == "template", f"Expected 'template', got: {source!r}"
    assert text, "Template narration returned empty string"
    assert len(text) > 20, f"Template narration too short: {text!r}"


def test_narrate_template_content_likely_root_cause():
    """Template for likely_root_cause must mention support_count and deviation sign."""
    finding = _minimal_finding(verdict="likely_root_cause")
    text, source = narrate(finding, client=None)

    assert source == "template"
    assert "10" in text, "support_count not in template narration"
    assert "positive" in text, "deviation sign not in template narration"
    assert "confidence" in text.lower(), "confidence not in template narration"


def test_narrate_template_content_possible_pattern():
    """Template for possible_pattern must not assert a cause and must mention coverage."""
    finding = _minimal_finding(
        verdict="possible_pattern — insufficient evidence",
        support=3,
        coverage=0.167,
    )
    text, source = narrate(finding, client=None)

    assert source == "template"
    assert "3" in text, "support_count not in possible_pattern template"
    # Must not assert a definitive cause — should mention insufficient evidence or threshold
    assert any(word in text.lower() for word in ["threshold", "below", "insufficient", "17"]), (
        f"Template for possible_pattern should indicate insufficient evidence: {text!r}"
    )


# ---------------------------------------------------------------------------
# CRITICAL hallucination guard test
# ---------------------------------------------------------------------------

class _HallucinatingClient:
    """A fake LLM client that invents numbers not present in the finding."""
    def complete(self, system_prompt, finding_json):
        return "This pattern affects 47 transactions with 99.9% confidence."
        # both numbers (47, 99.9) are fabricated and not in the finding object


def test_narrate_falls_back_on_hallucination():
    """The hallucinating client introduces numbers not in the finding → must fall back."""
    finding = _minimal_finding()
    text, source = narrate(finding, client=_HallucinatingClient())

    assert source == "template", (
        f"Hallucination guard FAILED — accepted bad LLM output with source={source!r}.\n"
        f"Text: {text!r}"
    )
    # Text must be the template narration, not the hallucinated string.
    # The hallucinated text was: "This pattern affects 47 transactions with 99.9% confidence."
    # We verify the hallucinated phrase did not make it through.
    assert "affects 47 transactions" not in text, (
        f"Hallucinated phrase leaked into output: {text!r}"
    )
    assert "99.9%" not in text, (
        f"Hallucinated confidence percentage leaked into output: {text!r}"
    )
    # The template output must contain real finding data
    assert str(finding["support_count"]) in text, "Template should contain support_count"


# ---------------------------------------------------------------------------
# Test: good client output (no invented figures) should pass through
# ---------------------------------------------------------------------------

class _GoodClient:
    """A fake LLM client that only uses numbers from the finding."""
    def complete(self, system_prompt, finding_json):
        import json
        f = json.loads(finding_json)
        # Use only numbers already in the finding
        return (f"{f['support_count']} exceptions on {f['shared_attributes']['fee_plan_id']} "
                f"show a {f['deviation_summary']['sign']} deviation. "
                f"Batch impact: {f['observed_batch_impact_paise']} paise.")


def test_narrate_good_client_passes_through():
    """A well-behaved client that only uses finding numbers should return its text."""
    finding = _minimal_finding()
    text, source = narrate(finding, client=_GoodClient())

    assert source == "llm", f"Good client output should be accepted as 'llm', got {source!r}"
    assert "10" in text
    assert "PLN_ENT_2024" in text
