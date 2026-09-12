"""
Deterministic Event Resolution Engine.
Applies precedence and conflict-resolution rules, integrates message facts,
and projects recurring income and expenses over the 90-day horizon.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict, Counter
import calendar

from code.models import FinancialProfile, FinancialEvent
from code.evidence_extractor import EvidenceExtractor, ExtractedFact

def add_months_to_date(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    max_days = calendar.monthrange(year, month)[1]
    day = min(dt.day, max_days)
    return datetime(year, month, day)

VARIABLE_CATEGORIES = {"groceries", "transport", "dining", "shopping", "entertainment"}

class EventResolver:
    def __init__(self, evidence_extractor: Optional[EvidenceExtractor] = None):
        self.evidence_extractor = evidence_extractor or EvidenceExtractor()

    def resolve_future_events(
        self,
        profile: FinancialProfile,
        events: List[FinancialEvent],
        messages: List[Dict[str, str]],
        request_date: str,
        forecast_days: int = 90
    ) -> List[FinancialEvent]:
        start_dt = datetime.strptime(request_date, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=forecast_days)
        
        # 1. Extract facts from user messages
        facts: List[ExtractedFact] = []
        for m in messages:
            facts.extend(self.evidence_extractor.extract_from_message(m))

        # Check if contract ended or employment ended (either via message or explicit event description)
        contract_ended = any(f.fact_type == "contract_ended" for f in facts)
        if not contract_ended:
            for e in events:
                desc_lower = e.description.lower()
                if "final employer payroll" in desc_lower or "contract ended" in desc_lower or "employment has ended" in desc_lower:
                    contract_ended = True
                    break

        rent_increase_pct = next((f.percentage for f in facts if f.fact_type == "rent_increase_pct"), None)
        salary_increase = next((f for f in facts if f.fact_type == "salary_increase"), None)
        first_salary = next((f for f in facts if f.fact_type == "first_salary"), None)
        salary_reduced_monthly = next((f for f in facts if f.fact_type == "salary_reduced_monthly"), None)
        salary_reduced_next = next((f for f in facts if f.fact_type == "salary_reduced_next"), None)
        arrears_adj = next((f for f in facts if f.fact_type == "arrears_adjustment"), None)
        confirmed_invoices = [f for f in facts if f.fact_type == "invoice_approved"]

        # 2. Gather existing explicit events within the forecast period
        resolved_events: List[FinancialEvent] = []
        covered_dates_by_cat: Set[Tuple[str, str]] = set()

        for e in events:
            # Filter out invalid / unrealized / cancelled / failed
            if e.status in ("cancelled", "failed", "unrealized"):
                continue
            # Reserve pending debits. Do not count pending credits.
            if e.status == "pending" and e.direction == "credit":
                continue

            settle_dt = datetime.strptime(e.settlement_date, "%Y-%m-%d")
            if start_dt <= settle_dt <= end_dt:
                amt = e.amount
                desc_lower = e.description.lower()
                if rent_increase_pct and e.category in ("rent", "housing") and "outstanding" not in desc_lower and "arrears" not in desc_lower:
                    amt = amt * (Decimal("1") + rent_increase_pct / Decimal("100"))

                res_evt = FinancialEvent(
                    event_id=e.event_id,
                    user_id=e.user_id,
                    event_type=e.event_type,
                    description=e.description,
                    category=e.category,
                    direction=e.direction,
                    amount=amt,
                    currency=e.currency,
                    event_date=e.event_date,
                    settlement_date=e.settlement_date,
                    status=e.status,
                    linked_event_id=e.linked_event_id,
                    flexibility=e.flexibility,
                    minimum_allowed_amount=e.minimum_allowed_amount
                )
                resolved_events.append(res_evt)
                covered_dates_by_cat.add((e.category, e.settlement_date))

        # 3. Add confirmed invoice payouts from messages
        for inv in confirmed_invoices:
            if inv.effective_date and inv.amount:
                inv_dt = datetime.strptime(inv.effective_date, "%Y-%m-%d")
                if start_dt <= inv_dt <= end_dt:
                    resolved_events.append(FinancialEvent(
                        event_id=f"msg_inv_{inv.effective_date}",
                        user_id=profile.user_id,
                        event_type="income",
                        description="Approved invoice payout",
                        category="salary",
                        direction="credit",
                        amount=inv.amount,
                        currency=inv.currency or profile.home_currency,
                        event_date=inv.effective_date,
                        settlement_date=inv.effective_date,
                        status="scheduled",
                        flexibility="fixed"
                    ))

        # 4. Resolve Recurring Salary Stream
        if not contract_ended:
            past_salaries = [e for e in events if e.category == "salary" and e.direction == "credit" and e.status in ("settled", "scheduled") and e.amount > 0]
            if past_salaries or first_salary:
                if first_salary and first_salary.amount:
                    base_salary = first_salary.amount
                    salary_day = datetime.strptime(first_salary.effective_date, "%Y-%m-%d").day if first_salary.effective_date else 15
                else:
                    # If there is a scheduled next confirmed salary, that is the base regular salary
                    scheduled_salaries = [e for e in past_salaries if e.status == "scheduled"]
                    if scheduled_salaries:
                        base_salary = scheduled_salaries[-1].amount
                        last_salary_evt = scheduled_salaries[-1]
                        salary_day = datetime.strptime(last_salary_evt.settlement_date, "%Y-%m-%d").day
                    else:
                        # Exclude variable bonuses/commissions when finding regular base salary
                        base_salaries = [e for e in past_salaries if "commission" not in e.description.lower() and "bonus" not in e.description.lower()]
                        if not base_salaries:
                            base_salaries = past_salaries
                        sal_amts = [e.amount for e in base_salaries]
                        counts = Counter(sal_amts)
                        base_salary = counts.most_common(1)[0][0]
                        # Determine regular payroll day from the modal day of base salaries
                        days = [datetime.strptime(e.settlement_date, "%Y-%m-%d").day for e in base_salaries]
                        salary_day = Counter(days).most_common(1)[0][0]
                        last_salary_evt = base_salaries[-1]

                if salary_reduced_monthly and salary_reduced_monthly.amount:
                    base_salary = salary_reduced_monthly.amount

                curr_month_dt = datetime(start_dt.year, start_dt.month, 1)
                first_next_salary_handled = False

                for m_offset in range(5):
                    target_month = add_months_to_date(curr_month_dt, m_offset)
                    max_d = calendar.monthrange(target_month.year, target_month.month)[1]
                    s_day = min(salary_day, max_d)
                    s_date_dt = datetime(target_month.year, target_month.month, s_day)
                    s_date_str = s_date_dt.strftime("%Y-%m-%d")

                    if start_dt <= s_date_dt <= end_dt:
                        exists = any(e.category == "salary" and e.settlement_date == s_date_str for e in resolved_events)
                        if not exists:
                            s_amt = base_salary
                            if salary_increase:
                                if not salary_increase.effective_date or s_date_str >= salary_increase.effective_date:
                                    s_amt = salary_increase.amount

                            if not first_next_salary_handled:
                                if salary_reduced_next and salary_reduced_next.amount:
                                    s_amt = salary_reduced_next.amount
                                if arrears_adj and arrears_adj.amount:
                                    s_amt += arrears_adj.amount
                                first_next_salary_handled = True

                            resolved_events.append(FinancialEvent(
                                event_id=f"proj_salary_{s_date_str}",
                                user_id=profile.user_id,
                                event_type="income",
                                description="Projected monthly salary",
                                category="salary",
                                direction="credit",
                                amount=s_amt,
                                currency=profile.home_currency,
                                event_date=s_date_str,
                                settlement_date=s_date_str,
                                status="scheduled",
                                flexibility="fixed"
                            ))

        # 5. Project Recurring Expenses
        settled_debits = [e for e in events if e.direction == "debit" and e.status == "settled" and e.amount > 0]
        
        # Group variable categories by category alone
        # Group fixed/subscription categories by category
        cat_groups = defaultdict(list)
        for e in settled_debits:
            cat_groups[e.category].append(e)

        for cat, items in cat_groups.items():
            if not items:
                continue
            # Exclude non-recurring categories per problem statement rules
            # (one-time investments, capital purchases, and employer-reimbursed work expenses)
            if cat in ("investment", "work_expense", "windfall"):
                continue

            dates = sorted([datetime.strptime(x.settlement_date, "%Y-%m-%d") for x in items])
            intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))] if len(dates) > 1 else [30]
            avg_int = sum(intervals) / len(intervals) if intervals else 30
            last_item = items[-1]
            last_date = dates[-1]
            if cat in VARIABLE_CATEGORIES and len(items) >= 3:
                sorted_amts = sorted([x.amount for x in items])
                amt = sorted_amts[len(sorted_amts) // 2]
            else:
                amt = last_item.amount

            if rent_increase_pct and cat in ("rent", "housing"):
                amt = amt * (Decimal("1") + rent_increase_pct / Decimal("100"))

            # Monthly categories (rent, utilities, subscriptions, insurance, debt, etc.)
            if cat not in VARIABLE_CATEGORIES or (25 <= avg_int <= 35):
                days_of_month = [d.day for d in dates]
                median_day = sorted(days_of_month)[len(days_of_month)//2]
                curr_month_dt = datetime(start_dt.year, start_dt.month, 1)

                for m_offset in range(5):
                    target_month = add_months_to_date(curr_month_dt, m_offset)
                    max_d = calendar.monthrange(target_month.year, target_month.month)[1]
                    day = min(median_day, max_d)
                    evt_dt = datetime(target_month.year, target_month.month, day)
                    evt_date_str = evt_dt.strftime("%Y-%m-%d")

                    if start_dt <= evt_dt <= end_dt:
                        if (cat, evt_date_str) not in covered_dates_by_cat:
                            resolved_events.append(FinancialEvent(
                                event_id=f"proj_{last_item.event_id}_{evt_date_str}",
                                user_id=profile.user_id,
                                event_type=last_item.event_type,
                                description=last_item.description,
                                category=cat,
                                direction="debit",
                                amount=amt,
                                currency=last_item.currency,
                                event_date=evt_date_str,
                                settlement_date=evt_date_str,
                                status="scheduled",
                                flexibility=last_item.flexibility,
                                minimum_allowed_amount=last_item.minimum_allowed_amount
                            ))
                            covered_dates_by_cat.add((cat, evt_date_str))

            # Periodic variable categories (groceries, transport, dining)
            else:
                step_days = int(round(avg_int)) if avg_int > 0 else 7
                # Snap step_days to nearest standard cadence: 3, 5, 7, 10, 14, 21, 28
                standard_cadences = [3, 5, 7, 10, 14, 21, 28]
                step_days = min(standard_cadences, key=lambda c: abs(c - step_days))

                curr_dt = last_date + timedelta(days=step_days)
                while curr_dt <= end_dt:
                    if curr_dt >= start_dt:
                        evt_date_str = curr_dt.strftime("%Y-%m-%d")
                        if (cat, evt_date_str) not in covered_dates_by_cat:
                            resolved_events.append(FinancialEvent(
                                event_id=f"proj_{last_item.event_id}_{evt_date_str}",
                                user_id=profile.user_id,
                                event_type=last_item.event_type,
                                description=last_item.description,
                                category=cat,
                                direction="debit",
                                amount=amt,
                                currency=last_item.currency,
                                event_date=evt_date_str,
                                settlement_date=evt_date_str,
                                status="scheduled",
                                flexibility=last_item.flexibility,
                                minimum_allowed_amount=last_item.minimum_allowed_amount
                            ))
                            covered_dates_by_cat.add((cat, evt_date_str))
                    curr_dt += timedelta(days=step_days)

        # Sort all resolved events chronologically by settlement_date
        resolved_events.sort(key=lambda x: x.settlement_date)
        return resolved_events
