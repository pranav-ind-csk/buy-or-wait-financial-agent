"""
Decision Explanation Generator.
Generates concise, factual, grounded financial explanations based strictly on calculated results.
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional
from code.models import CandidatePlan, EvaluationRequest, FinancialProfile, SpendingChange

def format_date_human(dt_str: str) -> str:
    if not dt_str:
        return ""
    dt = datetime.strptime(dt_str, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%B %Y')}"

def format_currency_amount(amount: Decimal, currency: str) -> str:
    if amount == int(amount):
        return f"{currency} {int(amount):,}"
    else:
        return f"{currency} {amount:,.2f}"

class DecisionExplainer:
    def __init__(self):
        pass

    def explain(
        self,
        request: EvaluationRequest,
        profile: FinancialProfile,
        amount_safe_to_pay: Decimal,
        plan: Optional[CandidatePlan]
    ) -> str:
        curr = profile.home_currency
        min_bal_str = format_currency_amount(profile.minimum_balance_to_keep, curr)
        req_amt_str = format_currency_amount(request.requested_amount, curr)

        # 1. Not recommended
        if plan is None or plan.payment_method == "not_recommended":
            deadline_str = format_date_human(request.desired_completion_date)
            safe_str = format_currency_amount(amount_safe_to_pay, curr)
            if amount_safe_to_pay > Decimal("0") and amount_safe_to_pay < request.requested_amount / Decimal("2"):
                return f"Do not proceed with the {req_amt_str} request. Although {safe_str} is available today, the full amount cannot be completed safely within 90 days."
            return f"Do not make this payment by {deadline_str}. None of the available options keeps the {min_bal_str} minimum protected."

        # 2. Full payment today
        if plan.payment_method == "full_payment":
            if not plan.spending_changes:
                return f"Pay {req_amt_str} today. This leaves at least {min_bal_str} available over the next 90 days."
            else:
                # With spending changes
                changes = plan.spending_changes
                if len(changes) == 1:
                    sc = changes[0]
                    desc = sc.description.lower() or sc.category
                    if sc.action == "stop":
                        action_text = f"Stop the {desc}"
                    else:
                        red_str = format_currency_amount(sc.new_amount, curr)
                        action_text = f"Reduce the {desc} to {red_str}"
                else:
                    parts = []
                    for sc in changes:
                        desc = sc.description.lower() or sc.category
                        if sc.action == "stop":
                            parts.append(f"stop the {desc}")
                        else:
                            red_str = format_currency_amount(sc.new_amount, curr)
                            parts.append(f"reduce the {desc} to {red_str}")
                    action_text = f"{parts[0].capitalize()} and {parts[1]}"
                return f"{action_text}, then pay {req_amt_str} today. This leaves at least {min_bal_str} available."

        # 3. Installments
        if plan.payment_method == "installments":
            inst_amt = plan.schedule[0].amount if plan.schedule else Decimal("0")
            inst_str = format_currency_amount(inst_amt, curr)
            start_date_str = format_date_human(plan.first_payment_date)
            return f"Use {plan.number_of_payments} installments of {inst_str}, starting {start_date_str}. This leaves at least {min_bal_str} available."

        # 4. Partial Payment
        if plan.payment_method == "partial_payment":
            p1_str = format_currency_amount(plan.schedule[0].amount, curr)
            p2_str = format_currency_amount(plan.schedule[1].amount, curr)
            p2_date_str = format_date_human(plan.schedule[1].date)
            return f"Pay {p1_str} today and the remaining {p2_str} on {p2_date_str}. This completes the full request and keeps the {min_bal_str} minimum protected."

        # 5. Wait
        if plan.payment_method == "wait":
            wait_date_str = format_date_human(plan.earliest_date_for_full_payment)
            return f"Pay {req_amt_str} in full on {wait_date_str}. Paying earlier would take the balance below the {min_bal_str} minimum."

        return f"Pay {req_amt_str} today. This keeps the {min_bal_str} minimum available over the next 90 days."
