"""
90-Day Deterministic Cash-Flow Simulator.
Simulates daily balance trajectories, enforcing minimum balance constraints.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Set

from code.models import FinancialEvent, PaymentScheduleItem, SpendingChange
from code.currency import CurrencyConverter

@dataclass
class SimulationResult:
    is_safe: bool
    min_balance_reached: Decimal
    min_balance_date: str
    final_balance: Decimal
    deficit: Decimal = Decimal("0")

class CashFlowSimulator:
    def __init__(self, currency_converter: Optional[CurrencyConverter] = None):
        self.currency_converter = currency_converter or CurrencyConverter()

    def simulate(
        self,
        starting_balance: Decimal,
        minimum_balance: Decimal,
        home_currency: str,
        start_date: str,
        resolved_events: List[FinancialEvent],
        purchase_payments: Optional[List[PaymentScheduleItem]] = None,
        spending_changes: Optional[List[SpendingChange]] = None,
        forecast_days: int = 90
    ) -> SimulationResult:
        purchase_payments = purchase_payments or []
        spending_changes = spending_changes or []

        stopped_events: Set[str] = set()
        reduced_events: Dict[str, Decimal] = {}
        for sc in spending_changes:
            if sc.action == "stop":
                stopped_events.add(sc.event_id)
            elif sc.action == "reduce_to" and sc.new_amount is not None:
                reduced_events[sc.event_id] = sc.new_amount

        daily_flows: Dict[str, Dict[str, Decimal]] = {}

        def add_flow(dt_str: str, amount: Decimal, is_credit: bool):
            if dt_str not in daily_flows:
                daily_flows[dt_str] = {"credit": Decimal("0"), "debit": Decimal("0")}
            if is_credit:
                daily_flows[dt_str]["credit"] += amount
            else:
                daily_flows[dt_str]["debit"] += amount

        # Purchase payments
        for p in purchase_payments:
            add_flow(p.date, p.amount, is_credit=False)

        # Resolved events
        for e in resolved_events:
            amt = e.amount
            evt_id = e.event_id
            base_id = evt_id
            if evt_id.startswith("proj_"):
                parts = evt_id.split("_")
                if len(parts) >= 3:
                    base_id = f"{parts[1]}_{parts[2]}" if parts[1].startswith("event") else parts[1]

            if evt_id in stopped_events or base_id in stopped_events:
                continue
            if evt_id in reduced_events:
                amt = reduced_events[evt_id]
            elif base_id in reduced_events:
                amt = reduced_events[base_id]

            if e.currency and e.currency != home_currency:
                amt = self.currency_converter.convert(amt, e.currency, home_currency, e.settlement_date)

            is_cred = (e.direction == "credit")
            add_flow(e.settlement_date, amt, is_credit=is_cred)

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        curr_balance = starting_balance
        min_balance_reached = starting_balance
        min_balance_date = start_date

        for day_offset in range(forecast_days + 1):
            curr_dt = start_dt + timedelta(days=day_offset)
            curr_date_str = curr_dt.strftime("%Y-%m-%d")

            flows = daily_flows.get(curr_date_str)
            if flows:
                # Credits (incoming salary/settled income) are credited first on their settlement date
                curr_balance += flows["credit"]
                # Then debits are deducted
                curr_balance -= flows["debit"]

            if curr_balance < min_balance_reached:
                min_balance_reached = curr_balance
                min_balance_date = curr_date_str

        is_safe = (min_balance_reached >= minimum_balance)
        deficit = max(Decimal("0"), minimum_balance - min_balance_reached)

        return SimulationResult(
            is_safe=is_safe,
            min_balance_reached=min_balance_reached,
            min_balance_date=min_balance_date,
            final_balance=curr_balance,
            deficit=deficit
        )
