"""
Safety Verifier and Output Validator.
Ensures every generated decision satisfies all HackerRank rules and constraints.
"""
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set

from code.models import DecisionResult, EvaluationRequest, FinancialProfile, PaymentOption

VALID_STATUSES = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
VALID_METHODS = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}

class SafetyValidator:
    def __init__(self):
        pass

    def validate_row(
        self,
        decision: DecisionResult,
        request: EvaluationRequest,
        profile: FinancialProfile,
        payment_options: List[PaymentOption]
    ) -> Tuple[bool, List[str]]:
        errors = []

        # 1. Bounds check on amount_safe_to_pay
        if not (Decimal("0") <= decision.amount_safe_to_pay <= request.requested_amount):
            errors.append(f"amount_safe_to_pay {decision.amount_safe_to_pay} not in [0, {request.requested_amount}]")

        # 2. Status and Method allowed values
        if decision.affordability_status not in VALID_STATUSES:
            errors.append(f"Invalid status: {decision.affordability_status}")
        if decision.recommended_payment_method not in VALID_METHODS:
            errors.append(f"Invalid method: {decision.recommended_payment_method}")

        # 3. Earliest date for full payment
        if decision.affordability_status == "affordable_now":
            if decision.earliest_date_for_full_payment != request.request_date:
                errors.append(f"For affordable_now, earliest_date must equal request_date ({request.request_date}), got {decision.earliest_date_for_full_payment}")
        elif decision.affordability_status == "not_affordable":
            if decision.earliest_date_for_full_payment != "":
                errors.append(f"For not_affordable, earliest_date must be empty, got {decision.earliest_date_for_full_payment}")

        # 4. Payment plan checks
        if decision.recommended_payment_method == "not_recommended":
            if decision.payment_plan != "none":
                errors.append(f"For not_recommended, payment_plan must be 'none', got {decision.payment_plan}")
        else:
            if decision.payment_plan == "none":
                errors.append(f"Payment plan cannot be 'none' for method {decision.recommended_payment_method}")
            else:
                # Parse schedule items
                items = decision.payment_plan.split("|")
                total_plan_amt = Decimal("0")
                prev_dt = None
                for it in items:
                    parts = it.split(":")
                    if len(parts) != 2:
                        errors.append(f"Malformed payment item: {it}")
                        continue
                    dt_str, amt_str = parts[0], parts[1]
                    try:
                        p_dt = datetime.strptime(dt_str, "%Y-%m-%d")
                        if prev_dt and p_dt < prev_dt:
                            errors.append(f"Payments not in chronological order: {prev_dt} then {p_dt}")
                        prev_dt = p_dt
                        total_plan_amt += Decimal(amt_str)
                    except Exception as ex:
                        errors.append(f"Failed to parse item {it}: {ex}")

                # Partial payment specific check
                if decision.recommended_payment_method == "partial_payment":
                    if len(items) != 2:
                        errors.append(f"Partial payment must have exactly 2 payments, got {len(items)}")
                    if abs(total_plan_amt - request.requested_amount) > Decimal("0.05"):
                        errors.append(f"Partial payment sum {total_plan_amt} != requested_amount {request.requested_amount}")

        # 5. Spending changes check
        if decision.spending_changes_needed != "none":
            changes = decision.spending_changes_needed.split("|")
            if len(changes) > 3:
                errors.append(f"Max 3 spending changes allowed, got {len(changes)}")
            seen_events = set()
            for ch in changes:
                parts = ch.split(":")
                action = parts[0]
                if action not in ("stop", "reduce_to"):
                    errors.append(f"Invalid spending action: {action}")
                if len(parts) >= 2:
                    evt_id = parts[1]
                    if evt_id in seen_events:
                        errors.append(f"Mutually exclusive / duplicate event in spending changes: {evt_id}")
                    seen_events.add(evt_id)

        # 6. Explanation
        if not decision.decision_explanation.strip():
            errors.append("Explanation is empty")

        is_valid = (len(errors) == 0)
        return is_valid, errors
