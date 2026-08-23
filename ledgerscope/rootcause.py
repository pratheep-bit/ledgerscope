"""
rootcause.py — Detect systemic patterns across a set of exceptions.

Row-by-row matching answers "what". This answers "why" and "how much".

HARD GUARDRAIL — never loosen:
    likely_root_cause  ⟺  support ≥ 2  AND  coverage > 0.50  AND  sign_consistent
    anything else      →  "possible_pattern — insufficient evidence"

Confidence labels (word, never a decimal — a decimal on a 62-row batch is
fabricated precision):
    high   support ≥ 5, coverage > 0.50, sign_consistent, cv < 0.05
    medium support ≥ 3, sign_consistent, cv < 0.20
    low    everything else that still clears the promotion bar
"""
import statistics
from itertools import combinations

CANDIDATE_ATTRS = ["payment_method", "card_network", "fee_plan_id",
                   "is_international", "is_refund", "settlement_batch",
                   "exception_code"]

MIN_SUPPORT = 2
MIN_COVERAGE = 0.50
CV_TIGHT, CV_LOOSE = 0.05, 0.20


def _group_key(exc, attrs):
    return tuple((a, getattr(exc, a)) for a in attrs)


def _informative_attr_sets(exceptions, attr_sets):
    """Drop any attribute or attribute-pair that has only one distinct value
    across the whole exception population. A group where every single
    exception shares the same value carries zero discriminating information —
    it cannot be a cause, because it doesn't separate affected from
    unaffected rows. This removes mega-groups at the source.
    """
    informative = []
    for attrs in attr_sets:
        distinct = {tuple((a, getattr(e, a)) for a in attrs) for e in exceptions}
        if len(distinct) > 1:
            informative.append(attrs)
    return informative


def detect(exceptions, batch_span_days: int) -> list:
    """Treat the exception set as a population and look for shared structure.
    Row-by-row matching answers "what". This answers "why" and "how much".
    """
    total = len(exceptions)
    if total == 0:
        return []

    candidates = []
    attr_sets = ([[a] for a in CANDIDATE_ATTRS] +
                 [list(p) for p in combinations(CANDIDATE_ATTRS, 2)])
    attr_sets = _informative_attr_sets(exceptions, attr_sets)

    for attrs in attr_sets:
        groups = {}
        for exc in exceptions:
            groups.setdefault(_group_key(exc, attrs), []).append(exc)

        for key, members in groups.items():
            if len(members) < MIN_SUPPORT:
                continue

            ratios = [e.deviation_ratio for e in members]
            mags = [abs(r) for r in ratios]
            sign_consistent = all(r > 0 for r in ratios) or all(r < 0 for r in ratios)
            mean_mag = statistics.fmean(mags)
            cv = (statistics.pstdev(mags) / mean_mag) if mean_mag else 0.0
            coverage = len(members) / total

            promoted = (len(members) >= MIN_SUPPORT
                        and coverage > MIN_COVERAGE
                        and sign_consistent)

            if promoted and len(members) >= 5 and cv < CV_TIGHT:
                confidence = "high"
            elif len(members) >= 3 and sign_consistent and cv < CV_LOOSE:
                confidence = "medium"
            else:
                confidence = "low"

            observed = sum(abs(e.total_delta_paise) for e in members)
            scale = 30 / max(batch_span_days, 1)

            candidates.append({
                "verdict": ("likely_root_cause" if promoted
                            else "possible_pattern — insufficient evidence"),
                "cause_type": _infer_cause_type(members),
                "shared_attributes": dict(key),
                "affected_txn_ids": [e.txn_id for e in members],
                "support_count": len(members),
                "coverage_ratio": round(coverage, 3),
                "deviation_summary": {
                    "sign": "positive" if ratios[0] > 0 else "negative",
                    "mean_deviation_ratio": round(statistics.fmean(ratios), 5),
                    "coefficient_of_variation": round(cv, 4),
                    "consistent": sign_consistent and cv < CV_LOOSE,
                },
                "rule_id": ("RC-RULE-02: shared attribute + sign consistency "
                            f"+ coverage>{MIN_COVERAGE}"),
                "confidence": confidence,
                "observed_batch_impact_paise": observed,
                "projected_monthly_impact": {
                    "value_paise": int(observed * scale),
                    "basis": (f"ASSUMPTION - batch spans {batch_span_days} day(s); "
                              f"scaled x{scale:.1f} to a 30-day month"),
                    "scaling_factor": round(scale, 2),
                    "is_estimate": True,
                },
                "controller_action": _action_for(_infer_cause_type(members),
                                                 dict(key), promoted),
            })

    candidates = _dedupe_identical_members(candidates)
    return _drop_subsumed(candidates)


def _dedupe_identical_members(cands):
    """If two candidates cover the exact same set of transaction IDs, they are
    the same discovery wearing two labels. Merge their shared attributes so
    the controller gets full context (fee_plan_id, payment_method, exception_code)
    and keep exactly one finding per unique member set.
    """
    groups = {}
    for c in cands:
        key = frozenset(c["affected_txn_ids"])
        groups.setdefault(key, []).append(c)

    deduped = []
    for members_key, group in groups.items():
        merged_attrs = {}
        for c in group:
            merged_attrs.update(c["shared_attributes"])

        base = max(group, key=lambda c: (
            1 if c["verdict"] == "likely_root_cause" else 0,
            1 if "exception_code" in c["shared_attributes"] else 0,
            len(c["shared_attributes"]),
            str(sorted(c["shared_attributes"].items())),
        ))
        merged = dict(base)
        merged["shared_attributes"] = merged_attrs
        merged["controller_action"] = _action_for(
            merged["cause_type"],
            merged_attrs,
            merged["verdict"] == "likely_root_cause"
        )
        deduped.append(merged)
    return deduped


def _drop_subsumed(cands):
    """Standard overlap-based pruning, with one protected exception:
    exception_code-keyed findings are never dropped for coincidental overlap
    with a broader, less diagnostic attribute grouping. exception_code is not
    a correlative signal like fee_plan_id or payment_method - it's the
    deterministic diagnosis classify.py already computed. Letting a vaguer,
    coincidentally-shared configuration attribute (e.g. "everyone not on the
    special plan defaults to PLN_STD") bury that diagnosis defeats the point
    of running classify.py at all.
    """
    protected = [c for c in cands if "exception_code" in c["shared_attributes"]]

    rest = [c for c in cands if c not in protected]
    rest.sort(key=lambda c: (
        0 if c["verdict"] == "likely_root_cause" else 1,
        -c["coverage_ratio"],
        -c["support_count"]
    ))

    kept = list(protected)
    claimed = set()
    for c in protected:
        claimed |= set(c["affected_txn_ids"])

    for c in rest:
        ids = set(c["affected_txn_ids"])
        if len(ids & claimed) / len(ids) > 0.5:
            continue
        kept.append(c)
        claimed |= ids

    kept.sort(key=lambda c: (
        0 if c["verdict"] == "likely_root_cause" else 1,
        -c["coverage_ratio"],
        -c["support_count"]
    ))
    return kept


def _infer_cause_type(members) -> str:
    """Map the majority exception_code in a group to a human-readable label."""
    from collections import Counter
    codes = [getattr(e, "exception_code", None) for e in members]
    if not codes:
        return "UNCLASSIFIED_PATTERN"
    majority_code = Counter(codes).most_common(1)[0][0]
    return {
        "E01": "RATE_MISCONFIGURATION",
        "E02": "GST_RATE_ERROR",
        "E03": "GST_BASE_ERROR",
        "E04": "ROUNDING_CONVENTION_MISMATCH",
        "E05": "MISSING_TAX_LINE",
        "E06": "REFUND_FEE_NOT_REVERSED",
        "E07": "SETTLEMENT_TIMING_ERROR",
        "E08": "DUPLICATE_DEDUCTION",
    }.get(majority_code, "UNCLASSIFIED_PATTERN")


def _action_for(cause_type: str, shared_attrs: dict, promoted: bool) -> str:
    """Produce one concrete action sentence per cause type.

    If not promoted, prefix with a monitoring recommendation instead of asserting
    a cause.
    """
    prefix = "" if promoted else (
        "Monitor across the next 2-3 settlement batches before treating this as "
        "confirmed. If the pattern persists: "
    )

    plan   = shared_attrs.get("fee_plan_id", "the affected plan")
    method = shared_attrs.get("payment_method", "affected")
    batch  = shared_attrs.get("settlement_batch", "the affected batch")

    actions = {
        "RATE_MISCONFIGURATION": (
            f"Audit the {method} rate on fee plan {plan} — settlement is applying "
            f"a rate inconsistent with the plan's configured rate."
        ),
        "GST_BASE_ERROR": (
            f"Review the GST computation logic for {method} transactions on plan "
            f"{plan} — tax appears to be computed on the gross transaction amount "
            f"rather than on the platform fee."
        ),
        "ROUNDING_CONVENTION_MISMATCH": (
            f"Check the rounding mode used in the settlement system — expected "
            f"half-up (Indian financial standard), but truncation appears to be "
            f"applied on plan {plan}."
        ),
        "MISSING_TAX_LINE": (
            f"Investigate why settlement batch {batch} is omitting the GST line "
            f"while still deducting a platform fee."
        ),
        "REFUND_FEE_NOT_REVERSED": (
            f"Confirm whether the refund fee-reversal step is configured on plan "
            f"{plan} — refund transactions are being settled without crediting back "
            f"the original platform fee."
        ),
        "GST_RATE_ERROR": (
            f"Audit the GST rate applied on plan {plan} for {method} — the implied "
            f"GST rate differs from the expected 18%."
        ),
        "SETTLEMENT_TIMING_ERROR": (
            f"Review the settlement cycle window for batch {batch} — transactions "
            f"appear to be settling outside the expected T+1/T+2 window."
        ),
        "DUPLICATE_DEDUCTION": (
            f"Investigate duplicate settlement rows in batch {batch} — two "
            f"deduction records exist for the same transaction ID."
        ),
    }
    sentence = actions.get(
        cause_type,
        f"Investigate the shared attributes {shared_attrs} for an unclassified pattern."
    )
    return prefix + sentence
