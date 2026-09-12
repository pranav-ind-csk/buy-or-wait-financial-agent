"""
Candidate Plan Generator, Affordability Evaluator, and Plan Ranking Engine.
"""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Tuple, Optional, Set
import calendar

from code.models import (
    FinancialProfile, FinancialEvent, PaymentOption, EvaluationRequest,
    SpendingChange, PaymentScheduleItem, CandidatePlan, DecisionResult
)
from code.simulator import CashFlowSimulator, SimulationResult
from code.currency import CurrencyConverter

def format_date_human(dt_str: str) -> str:
    dt = datetime.strptime(dt_str, "%Y-%m-%d")
    # e.g. "8 August 2025" or "15 November 2019"
    return f"{dt.day} {dt.strftime('%B %Y')}"

def format_currency_amount(amount: Decimal, currency: str) -> str:
    # Format with comma separators and proper decimal places
    # If integer, no decimals, else 2 decimals
    if amount == int(amount):
        return f"{currency} {int(amount):,}"
    else:
        return f"{currency} {amount:,.2f}"

class AffordabilityEngine:
    def __init__(self, simulator: Optional[CashFlowSimulator] = None, currency_converter: Optional[CurrencyConverter] = None):
        self.currency_converter = currency_converter or CurrencyConverter()
        self.simulator = simulator or CashFlowSimulator(self.currency_converter)

    def calculate_amount_safe_to_pay(
        self,
        profile: FinancialProfile,
        resolved_events: List[FinancialEvent],
        request_date: str,
        requested_amount: Decimal,
        forecast_days: int = 90
    ) -> Decimal:
        """
        Calculates the maximum amount the user can safely pay today (request_date)
        before optional spending changes, capped at requested_amount.
        """
        # Simulate base trajectory without purchase
        base_res = self.simulator.simulate(
            starting_balance=profile.current_available_balance,
            minimum_balance=profile.minimum_balance_to_keep,
            home_currency=profile.home_currency,
            start_date=request_date,
            resolved_events=resolved_events,
            forecast_days=forecast_days
        )

        if not base_res.is_safe:
            return Decimal("0")

        # Headroom above minimum balance
        headroom = base_res.min_balance_reached - profile.minimum_balance_to_keep
        if headroom <= Decimal("0"):
            return Decimal("0")

        # Binary search between 0 and min(headroom, requested_amount)
        low = Decimal("0")
        high = min(headroom, requested_amount)

        # Check if high is safe directly
        high_res = self.simulator.simulate(
            starting_balance=profile.current_available_balance,
            minimum_balance=profile.minimum_balance_to_keep,
            home_currency=profile.home_currency,
            start_date=request_date,
            resolved_events=resolved_events,
            purchase_payments=[PaymentScheduleItem(request_date, high)],
            forecast_days=forecast_days
        )
        if high_res.is_safe:
            return high

        for _ in range(40):
            mid = (low + high) / Decimal("2")
            res = self.simulator.simulate(
                starting_balance=profile.current_available_balance,
                minimum_balance=profile.minimum_balance_to_keep,
                home_currency=profile.home_currency,
                start_date=request_date,
                resolved_events=resolved_events,
                purchase_payments=[PaymentScheduleItem(request_date, mid)],
                forecast_days=forecast_days
            )
            if res.is_safe:
                low = mid
            else:
                high = mid

        # Precision rounding
        if low == int(low):
            return low
        return low.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_earliest_date_for_full_payment(
        self,
        profile: FinancialProfile,
        resolved_events: List[FinancialEvent],
        request_date: str,
        requested_amount: Decimal,
        forecast_days: int = 90
    ) -> str:
        """
        Finds the first conservative projected date when the full requested amount
        can be paid as a single payment without optional spending changes.
        """
        start_dt = datetime.strptime(request_date, "%Y-%m-%d")

        for d_offset in range(forecast_days + 1):
            cand_dt = start_dt + timedelta(days=d_offset)
            cand_date_str = cand_dt.strftime("%Y-%m-%d")

            res = self.simulator.simulate(
                starting_balance=profile.current_available_balance,
                minimum_balance=profile.minimum_balance_to_keep,
                home_currency=profile.home_currency,
                start_date=request_date,
                resolved_events=resolved_events,
                purchase_payments=[PaymentScheduleItem(cand_date_str, requested_amount)],
                forecast_days=forecast_days
            )
            if res.is_safe:
                return cand_date_str

        return ""

    def generate_candidate_plans(
        self,
        request: EvaluationRequest,
        profile: FinancialProfile,
        resolved_events: List[FinancialEvent],
        payment_options: List[PaymentOption],
        amount_safe_to_pay: Decimal,
        earliest_full_date: str
    ) -> List[CandidatePlan]:
        candidates: List[CandidatePlan] = []
        user_methods = set(profile.payment_methods_user_will_consider)

        # 1. Full Payment Now (today)
        if "full_payment" in user_methods:
            is_safe_now = (amount_safe_to_pay >= request.requested_amount)
            plan = CandidatePlan(
                payment_method="full_payment",
                affordability_status="affordable_now" if is_safe_now else "not_affordable",
                schedule=[PaymentScheduleItem(request.request_date, request.requested_amount)],
                total_amount_paid=request.requested_amount,
                number_of_payments=1,
                first_payment_date=request.request_date,
                completion_date=request.request_date,
                is_safe=is_safe_now,
                earliest_date_for_full_payment=request.request_date if is_safe_now else earliest_full_date
            )
            if is_safe_now:
                candidates.append(plan)

        # 2. Installment Plans from supplied options
        if "installments" in user_methods:
            for opt in payment_options:
                if opt.payment_method != "installments":
                    continue
                # Check max_installment_months if specified
                if profile.max_installment_months is not None:
                    # Estimate months: number of payments or duration
                    duration_days = (opt.number_of_payments - 1) * (opt.payment_frequency_days or 30)
                    duration_months = (duration_days // 30) + 1
                    if duration_months > profile.max_installment_months:
                        continue

                # Build schedule
                first_dt = datetime.strptime(opt.first_payment_date, "%Y-%m-%d")
                freq_days = opt.payment_frequency_days or 30
                schedule = []
                for i in range(opt.number_of_payments):
                    p_dt = first_dt + timedelta(days=i * freq_days)
                    schedule.append(PaymentScheduleItem(p_dt.strftime("%Y-%m-%d"), opt.payment_amount))

                completion_date = schedule[-1].date
                # Simulate safety
                res = self.simulator.simulate(
                    starting_balance=profile.current_available_balance,
                    minimum_balance=profile.minimum_balance_to_keep,
                    home_currency=profile.home_currency,
                    start_date=request.request_date,
                    resolved_events=resolved_events,
                    purchase_payments=schedule
                )

                plan = CandidatePlan(
                    payment_method="installments",
                    affordability_status="affordable_with_plan" if res.is_safe else "not_affordable",
                    schedule=schedule,
                    total_amount_paid=opt.total_payable_amount,
                    number_of_payments=opt.number_of_payments,
                    first_payment_date=opt.first_payment_date,
                    completion_date=completion_date,
                    is_safe=res.is_safe,
                    payment_option_id=opt.payment_option_id,
                    min_balance_reached=res.min_balance_reached,
                    min_balance_date=res.min_balance_date,
                    earliest_date_for_full_payment=earliest_full_date
                )
                if res.is_safe:
                    candidates.append(plan)

        # 3. Partial Payment
        if request.allows_partial_payment and "partial_payment" in user_methods:
            if Decimal("0") < amount_safe_to_pay < request.requested_amount and earliest_full_date:
                if earliest_full_date <= request.desired_completion_date:
                    rem_amount = request.requested_amount - amount_safe_to_pay
                    part_schedule = [
                        PaymentScheduleItem(request.request_date, amount_safe_to_pay),
                        PaymentScheduleItem(earliest_full_date, rem_amount)
                    ]
                    res = self.simulator.simulate(
                        starting_balance=profile.current_available_balance,
                        minimum_balance=profile.minimum_balance_to_keep,
                        home_currency=profile.home_currency,
                        start_date=request.request_date,
                        resolved_events=resolved_events,
                        purchase_payments=part_schedule
                    )
                    if res.is_safe:
                        candidates.append(CandidatePlan(
                            payment_method="partial_payment",
                            affordability_status="affordable_with_plan",
                            schedule=part_schedule,
                            total_amount_paid=request.requested_amount,
                            number_of_payments=2,
                            first_payment_date=request.request_date,
                            completion_date=earliest_full_date,
                            is_safe=True,
                            min_balance_reached=res.min_balance_reached,
                            min_balance_date=res.min_balance_date,
                            earliest_date_for_full_payment=earliest_full_date
                        ))

        # 4. Wait (Full Payment on Earliest Full Date)
        if "full_payment" in user_methods and earliest_full_date and earliest_full_date > request.request_date:
            wait_schedule = [PaymentScheduleItem(earliest_full_date, request.requested_amount)]
            res = self.simulator.simulate(
                starting_balance=profile.current_available_balance,
                minimum_balance=profile.minimum_balance_to_keep,
                home_currency=profile.home_currency,
                start_date=request.request_date,
                resolved_events=resolved_events,
                purchase_payments=wait_schedule
            )
            if res.is_safe:
                candidates.append(CandidatePlan(
                    payment_method="wait",
                    affordability_status="affordable_later",
                    schedule=wait_schedule,
                    total_amount_paid=request.requested_amount,
                    number_of_payments=1,
                    first_payment_date=earliest_full_date,
                    completion_date=earliest_full_date,
                    is_safe=True,
                    min_balance_reached=res.min_balance_reached,
                    min_balance_date=res.min_balance_date,
                    earliest_date_for_full_payment=earliest_full_date
                ))

        # 5. Plans with Spending Changes (if needed)
        # Find adjustable flexible recurring expenses
        stop_candidates: List[FinancialEvent] = []
        reduce_candidates: List[FinancialEvent] = []

        seen_cats = set()
        for e in resolved_events:
            cat = e.category
            if cat in profile.expense_categories_to_protect:
                continue
            if cat in seen_cats:
                continue
            seen_cats.add(cat)

            if cat in profile.expense_categories_user_is_willing_to_stop and e.flexibility in ("stoppable", "reducible_or_stoppable"):
                stop_candidates.append(e)
            if cat in profile.expense_categories_user_is_willing_to_reduce and e.flexibility in ("reducible", "reducible_or_stoppable") and e.minimum_allowed_amount is not None:
                reduce_candidates.append(e)

        # Test spending change combinations (1 or 2 changes)
        spending_combos: List[List[SpendingChange]] = []
        for s in stop_candidates:
            base_id = s.event_id.replace("proj_", "").split("_20")[0]
            spending_combos.append([SpendingChange("stop", base_id, description=s.description, category=s.category)])
        for r in reduce_candidates:
            base_id = r.event_id.replace("proj_", "").split("_20")[0]
            spending_combos.append([SpendingChange("reduce_to", base_id, new_amount=r.minimum_allowed_amount, description=r.description, category=r.category)])
        # 2 changes
        for s in stop_candidates:
            for r in reduce_candidates:
                if s.category != r.category and s.event_id != r.event_id:
                    s_base = s.event_id.replace("proj_", "").split("_20")[0]
                    r_base = r.event_id.replace("proj_", "").split("_20")[0]
                    spending_combos.append([
                        SpendingChange("stop", s_base, description=s.description, category=s.category),
                        SpendingChange("reduce_to", r_base, new_amount=r.minimum_allowed_amount, description=r.description, category=r.category)
                    ])

        if "full_payment" in user_methods:
            for combo in spending_combos:
                res = self.simulator.simulate(
                    starting_balance=profile.current_available_balance,
                    minimum_balance=profile.minimum_balance_to_keep,
                    home_currency=profile.home_currency,
                    start_date=request.request_date,
                    resolved_events=resolved_events,
                    purchase_payments=[PaymentScheduleItem(request.request_date, request.requested_amount)],
                    spending_changes=combo
                )
                if res.is_safe:
                    candidates.append(CandidatePlan(
                        payment_method="full_payment",
                        affordability_status="affordable_with_plan",
                        schedule=[PaymentScheduleItem(request.request_date, request.requested_amount)],
                        spending_changes=combo,
                        total_amount_paid=request.requested_amount,
                        number_of_payments=1,
                        first_payment_date=request.request_date,
                        completion_date=request.request_date,
                        is_safe=True,
                        earliest_date_for_full_payment=earliest_full_date,
                        min_balance_reached=res.min_balance_reached,
                        min_balance_date=res.min_balance_date
                    ))

        return candidates

    def rank_plans(
        self,
        candidates: List[CandidatePlan],
        desired_completion_date: str
    ) -> Optional[CandidatePlan]:
        """
        Ranks eligible safe candidate plans strictly by HackerRank precedence:
        1. Complete the full request by desired_completion_date.
        2. Require no spending changes.
        3. Minimize the total amount paid.
        4. Start payment earlier.
        5. Use fewer payments.
        6. Use the lowest payment_option_id as final tie-breaker.
        """
        if not candidates:
            return None

        def sort_key(p: CandidatePlan):
            meets_deadline = 0 if p.completion_date <= desired_completion_date else 1
            num_changes = len(p.spending_changes)
            total_cost = p.total_amount_paid
            first_date = p.first_payment_date
            num_payments = p.number_of_payments
            opt_id = p.payment_option_id or "zzzzzz"
            return (meets_deadline, num_changes, total_cost, first_date, num_payments, opt_id)

        sorted_plans = sorted(candidates, key=sort_key)
        return sorted_plans[0]
