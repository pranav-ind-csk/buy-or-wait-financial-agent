"""
Evaluation pipeline for the Buy or Wait? financial decision agent.
Evaluates agent predictions against dataset/sample_requests.csv ground truth.
"""
import sys
import os
import csv
from decimal import Decimal
from typing import Dict, List, Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from code.data_loader import DataLoader
from code.event_resolver import EventResolver
from code.affordability import AffordabilityEngine
from code.explainer import DecisionExplainer
from code.validator import SafetyValidator
from code.models import EvaluationRequest, DecisionResult

def evaluate():
    print("==================================================")
    print("HACKERRANK ORCHESTRATE — BUY OR WAIT EVALUATION")
    print("==================================================")

    dl = DataLoader()
    dl.load_all()
    sample_rows = dl.load_sample_requests()
    print(f"Loaded {len(sample_rows)} solved sample requests.")

    resolver = EventResolver()
    engine = AffordabilityEngine()
    explainer = DecisionExplainer()
    validator = SafetyValidator()

    metrics = {
        "status_match": 0,
        "method_match": 0,
        "earliest_date_match": 0,
        "spending_changes_match": 0,
        "plan_match": 0,
        "safe_amt_close": 0,
        "validated_ok": 0
    }

    results = []

    for row in sample_rows:
        req_id = row["request_id"]
        uid = row["user_id"]
        req_date = row["request_date"]
        req_amt = Decimal(row["requested_amount"])
        desired_date = row["desired_completion_date"]
        allows_partial = row["allows_partial_payment"].lower() == "true"
        req_text = row["request_text"]

        request = EvaluationRequest(
            request_id=req_id,
            user_id=uid,
            request_date=req_date,
            request_type=row["request_type"],
            requested_amount=req_amt,
            desired_completion_date=desired_date,
            allows_partial_payment=allows_partial,
            request_text=req_text
        )

        profile = dl.profiles[uid]
        user_events = dl.events_by_user.get(uid, [])
        user_msgs = dl.messages_by_user.get(uid, [])
        options = dl.payment_options_by_request.get(req_id, [])

        # 1. Resolve events
        resolved_evts = resolver.resolve_future_events(profile, user_events, user_msgs, req_date)

        # 2. Compute safe amount
        safe_amt = engine.calculate_amount_safe_to_pay(profile, resolved_evts, req_date, req_amt)

        # 3. Compute earliest full date
        earliest_full = engine.calculate_earliest_date_for_full_payment(profile, resolved_evts, req_date, req_amt)

        # 4. Generate candidate plans
        candidates = engine.generate_candidate_plans(request, profile, resolved_evts, options, safe_amt, earliest_full)

        # 5. Rank plans
        best_plan = engine.rank_plans(candidates, desired_date)

        # 6. Build decision
        if best_plan is None:
            # Fallback not recommended
            status = "not_affordable"
            method = "not_recommended"
            plan_str = "none"
            earliest_str = ""
            spending_str = "none"
        else:
            status = best_plan.affordability_status
            method = best_plan.payment_method
            plan_str = best_plan.payment_plan_str()
            earliest_str = best_plan.earliest_date_for_full_payment
            spending_str = best_plan.spending_changes_str()

        explanation = explainer.explain(request, profile, safe_amt, best_plan)

        decision = DecisionResult(
            request_id=req_id,
            amount_safe_to_pay=safe_amt,
            affordability_status=status,
            recommended_payment_method=method,
            payment_plan=plan_str,
            earliest_date_for_full_payment=earliest_str,
            spending_changes_needed=spending_str,
            decision_explanation=explanation
        )

        # Validation
        is_valid, errors = validator.validate_row(decision, request, profile, options)
        if is_valid:
            metrics["validated_ok"] += 1
        else:
            print(f"[{req_id}] Validation errors: {errors}")

        # Ground truth comparison
        exp_status = row["affordability_status"]
        exp_method = row["recommended_payment_method"]
        exp_earliest = row["earliest_date_for_full_payment"]
        exp_spending = row["spending_changes_needed"]
        exp_plan = row["payment_plan"]
        exp_safe = Decimal(row["amount_safe_to_pay"])

        status_ok = (status == exp_status)
        method_ok = (method == exp_method)
        earliest_ok = (earliest_str == exp_earliest)
        spending_ok = (spending_str == exp_spending)
        plan_ok = (plan_str == exp_plan)
        safe_close = (abs(safe_amt - exp_safe) <= Decimal("100.0"))

        if status_ok: metrics["status_match"] += 1
        if method_ok: metrics["method_match"] += 1
        if earliest_ok: metrics["earliest_date_match"] += 1
        if spending_ok: metrics["spending_changes_match"] += 1
        if plan_ok: metrics["plan_match"] += 1
        if safe_close: metrics["safe_amt_close"] += 1

        results.append({
            "request_id": req_id,
            "status_ok": status_ok,
            "method_ok": method_ok,
            "earliest_ok": earliest_ok,
            "spending_ok": spending_ok,
            "plan_ok": plan_ok,
            "calc_safe": safe_amt,
            "exp_safe": exp_safe,
            "calc_method": method,
            "exp_method": exp_method,
            "calc_earliest": earliest_str,
            "exp_earliest": exp_earliest
        })

    total = len(sample_rows)
    print("\n--- EVALUATION SUMMARY ---")
    print(f"Validation Pass Rate:           {metrics['validated_ok']}/{total} ({metrics['validated_ok']/total*100:.1f}%)")
    print(f"Affordability Status Accuracy:  {metrics['status_match']}/{total} ({metrics['status_match']/total*100:.1f}%)")
    print(f"Payment Method Accuracy:        {metrics['method_match']}/{total} ({metrics['method_match']/total*100:.1f}%)")
    print(f"Earliest Full Date Accuracy:    {metrics['earliest_date_match']}/{total} ({metrics['earliest_date_match']/total*100:.1f}%)")
    print(f"Spending Changes Match:         {metrics['spending_changes_match']}/{total} ({metrics['spending_changes_match']/total*100:.1f}%)")
    print(f"Payment Plan Exact Match:       {metrics['plan_match']}/{total} ({metrics['plan_match']/total*100:.1f}%)")
    print(f"Safe Amount Close:              {metrics['safe_amt_close']}/{total} ({metrics['safe_amt_close']/total*100:.1f}%)")

    print("\nDetailed breakdown:")
    for r in results:
        flag = "PASS" if (r['status_ok'] and r['method_ok']) else "FAIL"
        print(f"  [{flag}] {r['request_id']}: method: {r['calc_method']} vs {r['exp_method']}, earliest: {r['calc_earliest']!r} vs {r['exp_earliest']!r}, safe: {r['calc_safe']} vs {r['exp_safe']}")

if __name__ == "__main__":
    evaluate()
