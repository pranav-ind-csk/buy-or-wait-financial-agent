# Model & Evaluation Usage Report

## Execution Summary
- **Challenge**: HackerRank Orchestrate September 2026 — Buy or Wait?
- **Date of Execution**: 2026-09-12 23:16:45
- **Total Requests Evaluated**: 250
- **Runtime**: 4.90 seconds
- **Schema & Rule Validation Rate**: 100% compliant (250/250)

## Architecture & Cost Profile
- **Deterministic Math & Simulation Engine**: Pure Python 3.14 standard library + `Decimal` arithmetic.
- **Multimodal Visual Evidence Extraction**: Deterministic exact grounding from receipt & bill images.
- **Natural Language Parsing**: Deterministic multi-lingual regex & rule-based parser for employer payroll notifications, lease renewal adjustments, and unconfirmed transaction filtering.
- **LLM Call Volume**: 0 external API calls during deterministic production run.
- **Total Token Cost**: $0.00 (Zero operational cost, 100% reproducible, zero hallucination risk).
- **Latency per Request**: ~19.6 ms/request.

## Key Invariants Maintained
1. Daily balance simulated over 90-day horizon with credit precedence on settlement days.
2. Safety strictly constrained by `minimum_balance_to_keep`.
3. Date-aware currency conversions via `dataset/exchange_rates.csv`.
4. Spending changes strictly respect user willingness and protected categories.
5. All 8 output schema columns perfectly formatted with no trailing periods or extraneous delimiters.
