# Failures and how they were resolved

(Append an entry every time something breaks. Write it when it happens, not
reconstructed afterward — the buildathon's judging criteria explicitly score
"failure recovery," and a real, specific failure is worth more than a clean
narrative invented on the last day.)

---

## Failure 1 — 2026-08-22: test_rounding_boundary_just_below_dot5 arithmetic error

**Step**: 5 (engine tests)
**What broke**: `test_rounding_boundary_just_below_dot5` asserted `round_half_up(1000*1800, 10000) == 18` but got `180`.
**Root cause**: Arithmetic error in the test itself. I wrote the docstring claiming `1000*1800 = 180,000` but the actual value is `1,800,000`. The denominator is `10,000`, so `1,800,000 / 10,000 = 180`, not 18.
**Fix**: Replaced with `amount=27778` paise → `fee=556` → `GST = round_half_up(556*1800, 10000) = round_half_up(1,000,800, 10000) = 100.08 → 100`. This correctly demonstrates a "just below .5" rounding case.
**Lesson**: Always verify arithmetic in test docstrings with a calculator, not just mental math. The engine code was correct throughout.

---

## Failure 2 — 2026-08-22: The Step 8 Subsumption Patching Spiral & The True General Fix

**Step**: 8 & 12 (rootcause analysis / end-to-end run)
**What broke**:
In the initial build, `pytest tests/test_rootcause.py -v` failed because broad non-discriminating attribute groupings (e.g. `settlement_batch=STL_2026_08`, `is_international=False`) with 100% coverage were swallowing specific findings in `_drop_subsumed`.

In response, I applied three sequential, case-by-case patches to `_drop_subsumed`:
1. Exempted promoted findings from being subsumed by non-promoted findings.
2. Exempted promoted findings from subsuming other promoted findings.
3. Exempted `exception_code` findings from being subsumed by non-exception_code findings.

While these three patches made the specific test assertions pass, they effectively disabled subsumption almost entirely. When executed end-to-end on the 62-record synthetic dataset with 18 exceptions, the engine reported **17 findings out of 18 exceptions** — 13 of which were redundant duplicate reports of the same 10-row netbanking cluster under different attribute permutations (`is_refund=False + E01`, `fee_plan_id=PLN_ENT_2024`, `payment_method=netbanking`, etc.).

**Root cause**:
The problem was attacking the symptom in `_drop_subsumed` rather than the two underlying causes:
1. **Non-discriminating attributes generated noise groups**: Attributes with only 1 unique value across all exceptions (e.g., `settlement_batch=STL_2026_08`, `is_international=False`) carry zero variance to separate causes, yet generated numerous candidate query groups.
2. **Missing candidate-level identity deduplication**: Multiple candidate attribute queries covering the *identical* set of transaction IDs were treated as separate discoveries rather than one discovery with multiple attributes.

**Fix**:
Instead of adding a fourth special-case exemption, we stepped back and implemented the proper two-part structural fix:
1. Added `_informative_attr_sets()`: Prunes any attribute or attribute-pair with only 1 distinct value across the exception population before generating candidate groups.
2. Added `_dedupe_identical_members()`: Groups candidates by `frozenset(affected_txn_ids)` and collapses exact duplicates into a single finding with merged shared attributes.
3. Restored `_drop_subsumed()` to a clean, simple overlap check with promoted findings prioritized.
4. Added `test_no_duplicate_member_sets` and `test_finding_count_is_reasonable` to enforce the invariant that identical discoveries must be collapsed.

**Lesson**:
When test fixes require stacking case-by-case exemptions on an algorithm, stop and look at the input space. Fixing non-discriminating inputs at the source and deduplicating exact member sets eliminated the need for complex subsumption rules and reduced 17 noisy report blocks to 2 clean, actionable findings.

---

## Failure 3 — 2026-08-22: E06 (refund) records classified as MATCHED

**Step**: 12 (end-to-end run)
**What broke**: End-to-end run showed `Exceptions: 16` instead of expected 18. Two E06 refund records were showing as MATCHED.
**Root cause**: `run.py` only called `classify()` on records already marked `EXCEPTION` by the engine (non-zero total_delta). But E06 fires when `is_refund=True and fee_delta >= 0` — the refund settlement *matches* the expected fee (delta=0), but that's wrong *because it's a refund* (fee should have been reversed). Engine correctly says MATCHED (delta=0), classify correctly fires E06, but classify was never being called.
**Fix**: Run `classify()` on EXCEPTION records AND on all refund transactions, then re-mark as EXCEPTION if a non-E09 code fires.
**Lesson**: The engine and classifier have orthogonal responsibilities. The engine detects arithmetic discrepancies; the classifier detects semantic violations (like a refund with a non-reversed fee). Both must run on every candidate record.

---

## Failure 4 — 2026-08-22: test_narrate_falls_back_on_hallucination false assertion

**Step**: 9 (narrate tests — CRITICAL)
**What broke**: Test asserted `"47" not in text` but `47` is a substring of `124730` (the `observed_batch_impact_paise` in the template output).
**Root cause**: The hallucination guard correctly fired and returned the template. But the test assertion was checking for the digit substring `47` in the output string, which appears embedded in `124730`.
**Fix**: Changed assertion to check for the specific hallucinated phrase `"affects 47 transactions"` and `"99.9%"` instead of bare digits, and added a positive assertion that the real support_count appears.
**Lesson**: When testing for absence of specific values, check for the *exact phrase* not bare digit substrings, since numbers like `124730` contain common small digit sequences.

---

## Failure 5 — 2026-08-23: Conflation of Distinct Causes under Default Plan (RC_002 Subsumption Bug)

**Step**: 8 & 12 (rootcause analysis / end-to-end report inspection)
**What broke**:
In the 62-record synthetic dataset, 8 residual exceptions on the default fee plan `PLN_STD` (spanning 2 E03 GST errors, 3 E04 rounding errors, 1 E05 missing tax, and 2 E06 refund errors) were merged into a single confusing finding `RC_002` labeled `fee_plan_id=PLN_STD` with `direction inconsistent` and `CV 1.709`. This broad, low-quality grouping claimed all 8 transactions and suppressed the smaller, genuinely diagnostic `exception_code`-keyed groupings underneath it.

**Root cause**:
1. **Fixture Homogeneity Masked the Problem**: Unit test fixtures like `_build_other_exceptions` used only a single fee plan (`PLN_STD`) across all exceptions. As a result, `_informative_attr_sets()` stripped `fee_plan_id` out in unit tests (since it had only 1 distinct value), so the conflation never occurred in tests. In the real dataset, however, two fee plans existed (`PLN_ENT_2024` and `PLN_STD`), giving `fee_plan_id=PLN_STD` high coverage across the non-enterprise records.
2. **Greedy Coverage Pruning Buried Ground Truth**: `exception_code` is a deterministic diagnosis produced by `classify.py`, whereas attributes like `fee_plan_id` are correlative configuration fields. Greedy "highest coverage wins" pruning allowed coincidental shared membership on the default plan to bury the deterministic exception codes.

**Fix**:
1. Protected `exception_code` in `_drop_subsumed`: Deterministic exception code findings are never dropped for coincidental overlap with broader configuration attributes.
2. Added `test_heterogeneous_default_plan_does_not_merge_distinct_causes` in `tests/test_rootcause.py`: Uses a realistic fixture with two fee plans and enforces that disparate exception codes under a default plan remain individually visible.
3. Updated `_dedupe_identical_members` to merge attributes across identical member sets so findings retain full context (`fee_plan_id`, `payment_method`, `exception_code`).

**Lesson**:
Deterministic classifications computed by earlier pipeline stages represent ground truth, not correlative hypotheses. Pruning must protect diagnostic ground truth from being swallowed by coincidental configuration attributes. Unit tests must also test heterogeneous multi-group populations to avoid artificial fixture bias.

